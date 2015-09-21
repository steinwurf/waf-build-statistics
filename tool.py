#!/usr/bin/env python
# encoding: utf-8

"""
File containing functionality related to build statistics.

This file injects itself into the waf build process and extract various data.
This data is located in the root of the build folder as a json file named
build_statistics.json.
Finally a summary is printed if any non-trivial changes occured.
"""

from waflib import TaskGen
from waflib import Logs
import time
import json
import os

filename = 'build_statistics.json'

old_build_statistics = None
new_build_statistics = {}


@TaskGen.feature('*')
@TaskGen.before_method('process_source')
def get_data(self):
    """
    Read past build statistics.

    Before processing any sources read the past build statistics.
    """
    global old_build_statistics
    if old_build_statistics:
        return
    f = os.path.join(self.bld.bldnode.nice_path(), filename)

    if old_build_statistics is None:
        old_build_statistics = {}
        if os.path.exists(f):
            with open(f) as data_file:
                old_build_statistics = json.load(data_file) or {}


@TaskGen.feature('*')
@TaskGen.after_method('process_source')
def time_compiled_tasks(self):
    """
    Wrap tasks to collect information from them.

    This function wraps each task with the collect_data_from_run function so
    that the needed data is collected.
    """
    if hasattr(self, 'compiled_tasks'):
        for t in self.compiled_tasks:
            t.run = collect_data_from_run(t.run, t)
    if hasattr(self, 'link_task'):
        t = self.link_task
        t.run = collect_data_from_run(t.run, t)

    if 'post_funs' not in dir(self.bld) or save_data not in self.bld.post_funs:
        self.bld.add_post_fun(save_data)


def collect_data_from_run(f, task):
    """Collect compile time and the resulting file size from task."""
    def wrap_run():
        new_build_statistics
        start = time.time()
        return_value = f()
        stop = time.time()
        for output in task.outputs:
            filesize = os.path.getsize(task.outputs[0].nice_path()) / 1024.0
            new_build_statistics[output.nice_path()] = {
                'file_size': filesize,
                'compile_time': (stop - start)
            }
        return return_value
    return wrap_run


def save_data(self):
    """
    Save the collected data to a json file.

    This function writes all the collected data to a file, and, if any changes
    happened, writes summary.
    """
    if new_build_statistics and old_build_statistics:
        # Description of the color codes.
        explaination = \
            "\x1b[0m (\x1b[36mdecrease\x1b[32m/\x1b[35mincrease\x1b[32m)"
        Logs.pprint('BOLD', "Build statistics:" + explaination)
        print_summary(old_build_statistics, new_build_statistics)

    f = os.path.join(self.bldnode.nice_path(), filename)
    with open(f, 'w') as outfile:
        d = old_build_statistics.copy()
        d.update(new_build_statistics)
        json.dump(d, outfile)


def print_summary(old, new):
    """Print a summary of the changes between the new and old dictionary."""
    total_old = {}
    total_new = {}
    for build in set(old) & set(new):
        old_stats = old[build]
        new_stats = new[build]

        for key in set(old_stats) & set(new_stats):
            compare_build(build, old_stats, new_stats, key)
            if key not in total_old:
                total_old[key] = 0
            total_old[key] += old_stats[key]
            if key not in total_new:
                total_new[key] = 0
            total_new[key] += new_stats[key]

    total_keys = set(total_old) & set(total_new)
    if total_keys:
        Logs.pprint('BLUE', '  ' + '-' * 80)
    for key in total_keys:
        compare_build('total', total_old, total_new, key)


def compare_build(build, old_stats, new_stats, key):
    """Compare two build tasks and print a description."""
    old_stat = old_stats[key]
    new_stat = new_stats[key]

    if old_stat == new_stat:
        return

    percent = (new_stat - old_stat) / old_stat * 100
    if abs(percent) < 0.5:
        return
    color = None
    if percent < 0:
        color = 'CYAN'
    else:
        color = 'PINK'
    Logs.pprint(color, '  {build:<55} {key:<12} {percent:>6.2f}%'.format(
        build=build,
        key=key,
        percent=percent))
