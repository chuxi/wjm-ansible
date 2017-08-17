#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2016 John R. Busch Consulting LLC.  All rights reserved.

import subprocess

class Spark():
    def get_spark_stats(self):
        stats = {}
        executors = self._grep_executor_info()
        for key, value in executors.items():
            cmd = "top -bn 1 -p %s 2>/dev/null | grep java" % value
            output = subprocess.check_output(cmd, shell=True)
            parts = output.split()
            mem_res = parts[5]
            if mem_res.endswith("m"):
                mem_res_bytes = float(mem_res[:-1]) * 1024
            elif mem_res.endswith("g"):
                mem_res_bytes = float(mem_res[:-1]) * 1024 * 1024
            elif mem_res.endswith("t"):
                mem_res_bytes = float(mem_res[:-1]) * 1024 * 1024 * 1024
            else:
                mem_res_bytes = float(mem_res)

            stats[key] = (parts[8], parts[9], int(mem_res_bytes))
        return stats

    def _grep_executor_info(self):
        executors = {}
        try:
            cmd = "/home/wjm/svr/java/bin/jps -m | grep CoarseGrainedExecutorBackend"
            output = subprocess.check_output(cmd, shell=True)
            lines = output.split('\n')
            for line in lines:
                parts = line.split(' ')
                pid = parts[0]
                i = 0
                part_len = len(parts)
                e_id = ""
                app_id = ""
                while i < part_len:
                    if parts[i] == "--executor-id":
                        i = i + 1
                        e_id = parts[i]
                    elif parts[i] == "--app-id":
                        i = i + 1
                        app_id = parts[i]
                    else:
                        i = i + 1
                if app_id != "" and e_id != "":
                    executors[app_id + ":" + e_id] = pid
        except subprocess.CalledProcessError as e:
            pass
        return executors


# wrap the spark as collectd plugin
class SparkCollectd():
    def __init__(self):
        self.interval = 10.0
        self.verbose_logging = False
        self.plugin_name = "spark"
        self.spark = Spark()

    def log_verbose(self, msg):
        if not self.verbose_logging:
            return
        collectd.info('%s plugin [verbose]: %s' % (self.plugin_name, msg))

    def configure_callback(self, conf):
        for node in conf.children:
            val = str(node.values[0])

            if node.key == "Interval":
                self.interval = float(val)
            elif node.key == "Verbose":
                self.verbose_logging = val in ['True', 'true']
            else:
                collectd.warning(
                    '%s plugin: Unknown config key: %s.' % (
                        self.plugin_name,
                        node.key))
        self.log_verbose("Configured with interval=%s" % self.interval)

        collectd.register_read(self.read_callback, self.interval)

    def dispatch_value(self, plugin_instance, val_type, type_instance, value):
        """
        Dispatch a value to collectd
        """
        self.log_verbose(
            'Sending value: %s-%s.%s=%s' % (
                self.plugin_name,
                plugin_instance,
                '-'.join([val_type, type_instance]),
                value))

        val = collectd.Values()
        val.plugin = self.plugin_name
        val.plugin_instance = plugin_instance
        val.type = val_type
        if len(type_instance) > 0:
            val.type_instance = type_instance
        val.values = value
        val.meta = {'0': True}
        val.dispatch()

    def read_callback(self):
        spark_stats = self.spark.get_spark_stats()
        try:
            for key, value in spark_stats.items():
                parts = key.split(':')
                self.dispatch_value(parts[0], "spark", parts[1], value)
        except IndexError:
            pass

if __name__ == '__main__':
    spark = Spark()
    stats = spark.get_spark_stats()
    for key, (cpu, mem_ratio, mem_res) in stats.items():
        print "executor %s: cpu ratio=%s, memory ratio=%s, memory res=%s" % (
            key, cpu, mem_ratio, mem_res)
else:
    import collectd

    spark = SparkCollectd()

    collectd.register_config(spark.configure_callback)
