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


def path_to_key(path):
    """Convert a path to an appropiate key."""
    path = path.split(os.sep)
    if path[0] == 'build':
        path = path[2:]
    return os.path.join(*path)


@TaskGen.feature('*')
@TaskGen.before_method('process_source')
def get_data(self):
    """
    Read past build statistics.

    Before processing any sources read the past build statistics.
    """
    global old_build_statistics

    if old_build_statistics is None:
        old_build_statistics = {}

        f = os.path.join(self.bld.bldnode.nice_path(), filename)
        if os.path.exists(f):
            with open(f) as data_file:
                old_build_statistics = json.load(data_file) or {}

    # collect sources
    for source in self.source if type(self.source) is list else [self.source]:
        if not source:
            continue
        if hasattr(source, 'nice_path'):
            source = source.nice_path()
        else:
            # Assume it's a string
            source = os.path.join(self.path.nice_path(), source)

        new_build_statistics[path_to_key(source)] = {
            'stats': {
                'size': {
                    'value': os.path.getsize(source) / 1024.0,
                    'unit': 'kb'
                }
            }
        }


@TaskGen.feature('*')
@TaskGen.after_method('process_source')
def collect_data_from_tasks(self):
    """
    Wrap tasks to collect information from them.

    This function wraps each task with the collect_data_from_run function so
    that the needed data is collected.
    """
    tasks = []
    if hasattr(self, 'compiled_tasks'):
        tasks = self.compiled_tasks

    if hasattr(self, 'link_task'):
        tasks.append(self.link_task)

    for task in tasks:
        task.run = collect_data_from_run(task.run, task)
        for output in task.outputs:
            key = path_to_key(output.nice_path())
            new_build_statistics[key] = {
                'sources': [path_to_key(i.nice_path()) for i in task.inputs]
            }

    if 'post_funs' not in dir(self.bld) or save_data not in self.bld.post_funs:
        self.bld.add_post_fun(save_data)


def collect_data_from_run(f, task):
    """Collect compile time and the resulting file size from task."""
    def wrap_run():
        start = time.time()
        return_value = f()
        stop = time.time()
        for output in task.outputs:
            key = path_to_key(output.nice_path())
            new_build_statistics[key]['stats'] = {
                'time': {
                    'value': (stop - start),
                    'unit': 's'
                },
                'size': {
                    'value': os.path.getsize(output.nice_path()) / 1024.0,
                    'unit': 'kb'
                }
            }
        return return_value
    return wrap_run


def save_data(self):
    """
    Save the collected data to a json file.

    This function writes all the collected data to a file, and, if any changes
    happened, writes summary.
    """
    build_statistics = {}
    for k in new_build_statistics:
        if k not in old_build_statistics:
            build_statistics[k] = new_build_statistics[k]
            continue
        build_statistics[k] = old_build_statistics[k].copy()
        build_statistics[k].update(new_build_statistics[k])

    compare_stats = old_build_statistics
    compare_with = 'previous build'

    if self.has_tool_option('compare_with'):
        compare_with = self.get_tool_option('compare_with')
        if os.path.exists(compare_with):
            with open(compare_with) as data_file:
                compare_stats = json.load(data_file)
        else:
            compare_stats = {}
            Logs.warn('{} does not exists.'.format(compare_with))

    if compare_stats:

        total_summary, summaries = \
            generate_summaries(compare_stats, build_statistics)

        print_summaries(total_summary, summaries)

    f = os.path.join(self.bldnode.nice_path(), filename)
    with open(f, 'w') as outfile:
        json.dump(build_statistics, outfile)


def generate_summaries(old, new):
    """Generate data summarising the changes between the new and old dict."""
    summaries = []
    total_old = {}
    total_new = {}

    def zero_stats(template):
        for k in template:
            template[k]['value'] = 0
        return template

    for build in sorted(set(old) | set(new)):
        if build in old:
            old_stats = old[build]['stats']
        else:
            old_stats = zero_stats(new[build]['stats'])

        if build in old:
            new_stats = new[build]['stats']
        else:
            new_stats = zero_stats(old[build]['stats'])

        for key in sorted(set(old_stats) & set(new_stats)):
            summary = generate_summary(build, old_stats, new_stats, key)
            if not summary:
                continue
            else:
                summaries.append(summary)

        for key in old_stats:
            if key not in total_old:
                total_old[key] = old_stats[key].copy()
            else:
                assert total_old[key]['unit'] == old_stats[key]['unit']
                total_old[key]['value'] += old_stats[key]['value']

        for key in new_stats:
            if key not in total_new:
                total_new[key] = new_stats[key].copy()
            else:
                assert total_new[key]['unit'] == new_stats[key]['unit']
                total_new[key]['value'] += new_stats[key]['value']

    total_summary = []
    for key in set(total_old) & set(total_new):
        summary = generate_summary('total', total_old, total_new, key)
        total_summary.append(summary)

    return total_summary, summaries


def generate_summary(build, old_stats, new_stats, stat):
    """Compare two build tasks and generate a summary."""
    assert old_stats[stat]['unit'] == new_stats[stat]['unit']

    summary = {'build': build, 'stat': stat}
    summary['unit'] = old_stats[stat]['unit']
    old_stat = old_stats[stat]['value']
    summary['old_stat'] = old_stat
    new_stat = new_stats[stat]['value']
    summary['new_stat'] = new_stat
    diff = (new_stat - old_stat)
    summary['diff'] = diff

    # avoid dividing with zero in case a new file has been added.
    if old_stat != 0:
        summary['percent'] = diff / old_stat * 100

    return summary


def print_summaries(total_summary, summaries, max_space=70, precision=0):
    """Print total and general summaries nicely."""
    max_values = {}
    for summary in summaries + total_summary:
        for key in summary:
            element = summary[key]
            if type(element) is float:
                element = ('{:0,.%sf}' % precision).format(element)
            length = len(str(element))
            max_values[key] = max(max_values.get(key, length), length)
            max_values[key] = min(max_values[key], max_space)

    line = (
        '{build:<{buildl}}  '
        '{stat:<{statl}}  '
        '{new_stat:>{new_statl}} / '
        '{old_stat:>{old_statl}}  '
        '{diff:>{diffl}}  '
        '{percent:>{percentl}}%')

    def gen_line(build, stat, new_stat, old_stat, diff, percent):
        short_build = '(...)' + build[-(max_space - 5):]
        return line.format(
            build=build if len(build) < max_space else short_build,
            buildl=max_values['build'],
            stat=stat,
            statl=max_values['stat'],
            new_stat=new_stat,
            new_statl=max_values['new_stat'] + max_values['unit'],
            old_stat=old_stat,
            old_statl=max_values['old_stat'] + max_values['unit'],
            diff=diff,
            diffl=max_values['diff'] + max_values['unit'],
            percent=percent,
            percentl=max_values['percent'] + 1)

    headings = ['build', 'stat', 'new stat', 'old stat', 'diff', '']

    new_stat = '{new_stat:0,.%sf}{unit:<%s}' % (precision, max_values['unit'])
    old_stat = '{old_stat:0,.%sf}{unit:<%s}' % (precision, max_values['unit'])
    diff = '{diff:0,.%sf}{unit:<%s}' % (precision, max_values['unit'])
    percent = '{percent:0,.%sf}' % precision

    def gen_messages(summaries):
        messages = []
        for summary in summaries:

            if abs(summary['percent']) < 0.5:
                continue

            color = 'CYAN' if summary['percent'] < 0 else 'PINK'

            messages.append((color, gen_line(
                build=summary['build'],
                stat=summary['stat'],
                new_stat=new_stat.format(**summary),
                old_stat=old_stat.format(**summary),
                diff=diff.format(**summary),
                percent=percent.format(**summary))))
        return messages

    messages = gen_messages(sorted(summaries, key=lambda a: abs(a['percent'])))
    if not messages:
        return

    heading = gen_line(*headings)

    Logs.pprint('BOLD', heading)
    footer = '-' * len(heading)

    for message in messages:
        Logs.pprint(*message)

    Logs.pprint('BLUE', footer)

    Logs.pprint('BOLD', heading)
    for message in gen_messages(total_summary):
        Logs.pprint(*message)
