# coding=utf-8

"""
The CephCollector collects utilization info from the Ceph storage system.

Documentation for ceph perf counters:
http://ceph.com/docs/master/dev/perf_counters/

#### Dependencies

 * ceph [http://ceph.com/]

"""

try:
    import json
except ImportError:
    import simplejson as json
import glob
import os
#与子进程相关的模块
import subprocess

import diamond.collector


def flatten_dictionary(input, sep='.', prefix=None):
    """Produces iterator of pairs where the first value is
    the joined key names and the second value is the value
    associated with the lowest level key. For example::

      {'a': {'b': 10},
       'c': 20,
       }

    produces::

      [('a.b', 10), ('c', 20)]
    """
    
    #最后返回dir格式的字符串
    for name, value in sorted(input.items()):
        fullname = sep.join(filter(None, [prefix, name]))
        if isinstance(value, dict):
            for result in flatten_dictionary(value, sep, fullname):
                yield result
        else:
            yield (fullname, value)


class CephCollector(diamond.collector.Collector):
    latency_tmp=[(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0),(0,0)]
    def get_default_config_help(self):
        config_help = super(CephCollector, self).get_default_config_help()
        config_help.update({
            'socket_path': 'The location of the ceph monitoring sockets.'
                           ' Defaults to "/var/run/ceph"',
            'socket_prefix': 'The first part of all socket names.'
                             ' Defaults to "ceph-"',
            'socket_ext': 'Extension for socket filenames.'
                          ' Defaults to "asok"',
            'ceph_binary': 'Path to "ceph" executable. '
                           'Defaults to /usr/bin/ceph.',
        })
        return config_help

    #因此通过这个类调用get_fefault_config的时候会更新config文件 并返回
    def get_default_config(self):
        """
        Returns the default collector settings
        """
        #这里的配置时在collector中的get_default_config中，它是以字典形式保存的
        config = super(CephCollector, self).get_default_config()
        #dict.update(dict2)     将字典dict2的键-值对添加到字典dict
        config.update({
            'socket_path': '/var/run/ceph',
            'socket_prefix': 'ceph-',
            'socket_ext': 'asok',
            'ceph_binary': '/usr/bin/ceph',
        })
        return config

    def _get_socket_paths(self):
        """Return a sequence of paths to sockets for communicating
        with ceph daemons.
        """
        #合并路径
        #例如  ：  /var/run/ceph/ceph-osd01.asok
        socket_pattern = os.path.join(self.config['socket_path'],
                                      (self.config['socket_prefix'] +
                                       '*.' + self.config['socket_ext']))
        #返回符合规则的文件路径
        return glob.glob(socket_pattern)
#前缀
    def _get_counter_prefix_from_socket_name(self, name):
        """Given the name of a UDS socket, return the prefix
        for counters coming from that source.
        """
        # os.path.splitext(ceph-osd01.asok)
        
        base = os.path.splitext(os.path.basename(name))[0]
        if base.startswith(self.config['socket_prefix']):
            base = base[len(self.config['socket_prefix']):]
        #ceph.osd01
        return 'ceph.' + base

    def _get_stats_from_socket(self, name):
        """Return the parsed JSON data returned when ceph is told to
        dump the stats from the named socket.

        In the event of an error error, the exception is logged, and
        an empty result set is returned.
        """
        try:
            #这里执行了命令
            json_blob = subprocess.check_output(
                [self.config['ceph_binary'],
                 '--admin-daemon',
                 name,
                 'perf',
                 'dump',
                 ])
        except subprocess.CalledProcessError, err:
            self.log.info('Could not get stats from %s: %s',
                          name, err)
            self.log.exception('Could not get stats from %s' % name)
            return {}

        try:
            #转化为json格式
            json_data = json.loads(json_blob)
        except Exception, err:
            self.log.info('Could not parse stats from %s: %s',
                          name, err)
            self.log.exception('Could not parse stats from %s' % name)
            return {}

        return json_data
    
    
    
    
    def find_latency_data(self,counter_prefix,json_perfdata):
        #perf dump中所有的latency  不包含recovery过程
        latency_list =['filestore.journal_latency.avgcount',
                                   'filestore.journal_latency.sum',
                                   'filestore.commitcycle_interval.avgcount',
                                   'filestore.commitcycle_interval.sum',
                                   'filestore.commitcycle_latency.avgcount',
                                   'filestore.commitcycle_latency.sum',
                                   'filestore.apply_latency.avgcount',
                                   'filestore.apply_latency.sum',
                                   'filestore.queue_transaction_latency_avg.avgcount',
                                   'filestore.queue_transaction_latency_avg.sum',
                                   'osd.op_latency.avgcount',
                                   'osd.op_latency.sum',
                                   'osd.op_process_latency.avgcount',
                                   'osd.op_process_latency.sum',
                                   'osd.op_r_latency.avgcount',
                                   'osd.op_r_latency.sum',
                                   'osd.op_r_process_latency.avgcount',
                                   'osd.op_r_process_latency.sum',
                                   'osd.op_w_latency.avgcount',
                                   'osd.op_w_latency.sum',
                                   'osd.op_w_process_latency.avgcount',
                                   'osd.op_w_process_latency.sum',
                                   'osd.op_rw_rlat.avgcount',
                                   'osd.op_rw_rlat.sum',
                                   'osd.subop_latency.avgcount',
                                   'osd.subop_latency.sum',
                                   'osd.subop_w_latency.avgcount',
                                   'osd.subop_w_latency.sum'                         
                                   ]
        #num = 0
        #初始化一个list ， 最后格式为 [(k,v),[k,v]]
        #fo = open("/home/nsq/1.txt","w+")
        latency_list_with_tuple = []
        #根据传过来的所有perf data 调用flatten_dictionary转换
        for lat_name,value in flatten_dictionary(json_perfdata,prefix=counter_prefix):
            #去掉prefix进行比较
            tem_lat_name = lat_name[len(counter_prefix)+1:] 
            #查看每个元素是否在latency_list
            if tem_lat_name in latency_list:
                #print lat_name,value
                tmp = (lat_name,value)
              #   fo.write(lat_name+"--"+str(value)+'\n')
                #加入到list中
                latency_list_with_tuple.append(tmp)
        #num=num+1
        #print "add_num:",num 
        # print "length of latency list:",len(latency_list)
        # for test in latency_list_with_tuple:
        #   print test
        latency_list_with_tuple_2=[]
        index=0
        #fo.write( str (index )+'\n')
        for item in latency_list_with_tuple:
            if(index % 2 == 0): 
                string= item[0][0:len(item[0])-9]
                
                if(latency_list_with_tuple[index][1]-CephCollector.latency_tmp[index][1]!=0):
                    tmp=(string,float(latency_list_with_tuple[index+1][1]-CephCollector.latency_tmp[index+1][1])/(latency_list_with_tuple[index][1]-CephCollector.latency_tmp[index][1]))
                elif (latency_list_with_tuple[index+1][1]!=0):
                    tmp=(string,float(latency_list_with_tuple[index+1][1])/latency_list_with_tuple[index][1])
                else:
                    tmp=(string,0)
         #       fo.write(string+"--"+str(tmp[1])+'\n')
                latency_list_with_tuple_2.append(tmp)
            index=index+1
            if(index==len(latency_list_with_tuple)):
                break
        #latency_list_with_tuple_2.append((latency_list_with_tuple_2[0][0]+"test",500))
        #for item in latency_list_with_tuple_2: 
        #    fo.write(item[0]+"-----"+str(item[1])+'\n')               
        CephCollector.latency_tmp=latency_list_with_tuple
	#fo.close()
        #latency_list_with_tuple_2.append((latency_list_with_tuple_2[0][0]+"test",0.05))
        return latency_list_with_tuple_2
    
    

    def _publish_stats(self, counter_prefix, stats):
        """Given a stats dictionary from _get_stats_from_socket,
        publish the individual values.
        
        in here stats are  json format
        """
        #prefix可能是 ceph.osd01 ，stats为性能数据
        latencydata = self.find_latency_data(counter_prefix, stats)
        for stat_name, stat_value in latencydata:  #最后时这里发布，
            self.publish_gauge(stat_name, stat_value,5)

    def collect(self):
        """
        Collect stats
        """
         #例如这种  /var/run/ceph/ceph-osd01.asok
        for path in self._get_socket_paths():   
            self.log.debug('checking %s', path)
            #这里返回的时ceph.osd01  类似这种的
            counter_prefix = self._get_counter_prefix_from_socket_name(path)
            #每一个osd的perf dump  这里会成为json格式
            stats = self._get_stats_from_socket(path)
            #Publish Metric,  counter_prefix is Metric Name, stats is Metric Value
            self._publish_stats(counter_prefix, stats)
        return
if __name__=='__main__':
    test = CephCollector()
    for path in test._get_socket_paths():
        print path
        counter_prefix = test._get_counter_prefix_from_socket_name(path)
        print counter_prefix
        stats = test._get_stats_from_socket(path) 
        latencydata = test.find_latency_data(counter_prefix, stats)
        for stat_name, stat_value in latencydata:  #最后时这里发布，
            print stat_name, stat_value
