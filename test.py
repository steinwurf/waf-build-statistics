#!/usr/bin/env python
# encoding: utf-8

"""Unit test for tool.py."""

from __future__ import print_function

import sys
import imp
import importlib
import unittest
import mock
import subprocess
import os
import json


def load_tool():
    """Mock waflib and load the tool module."""
    # create a new empty moduel using the imp module
    waflib = imp.new_module('waflib')

    # create a new mock which is to mock the waflib's TaskGen
    MockTaskGen = mock.Mock()

    def side_effect(wild_card):
        m = mock.Mock(side_effect=lambda func: func)
        return m

    # using the side_effect function, mock the various decoratores used in
    # tool.py
    MockTaskGen.feature = mock.Mock(side_effect=side_effect)
    MockTaskGen.before_method = mock.Mock(side_effect=side_effect)
    MockTaskGen.after_method = mock.Mock(side_effect=side_effect)

    # set the MockTaskGen as an attribute called TaskGen on the fake waflib
    # module
    setattr(waflib, 'TaskGen', MockTaskGen)

    # do the same for the Logs attribute
    MockLogs = mock.Mock()
    setattr(waflib, 'Logs', MockLogs)

    # add the fake waflib to sys.modules - when doing so any later imports of
    # the waflib will not happen.
    # This allows us to import files which imports the waflib even though that
    # module is normally only available through waf.
    sys.modules['waflib'] = waflib

    # use imp to find and load the tool module.
    return importlib.import_module('tool')


class TestTool(unittest.TestCase):

    """Test tool."""

    def test_complete(self):
        """Test the overall functionality."""
        tool = load_tool()

        mock_self = mock.Mock()
        mock_self.bld.bldnode.srcpath = lambda: '.'

        old_build_statistics = {
            'output_old_1': {
                'time': {'value': 3, 'unit': 's'},
                'size': {'value': 3, 'unit': 'kb'},
            },
            'output_1_1': {
                'time': {'value': 10, 'unit': 's'},
                'size': {'value': 5, 'unit': 'kb'},

            },
            'output_2_1': {
                'time': {'value': 5, 'unit': 's'},
                'size': {'value': 10, 'unit': 'kb'},

            },
        }

        # monkey patch and call get_data
        builtins = '__builtin__' if sys.version[0] == '2' else 'builtins'
        open_module = '{}.open'.format(builtins)
        with \
                mock.patch('os.path.exists', lambda path: True), \
                mock.patch(open_module, mock.mock_open()), \
                mock.patch('json.load', lambda datafile: old_build_statistics):
            tool.get_data(mock_self)

        # check result of get_data
        self.assertEqual(old_build_statistics, tool.old_build_statistics)

        # setup task mocks
        mock_compiled_tasks = [mock.Mock(), mock.Mock()]
        mock_self.compiled_tasks = mock_compiled_tasks
        mock_link_task = mock.Mock()
        mock_self.link_task = mock_link_task

        mock_tasks = mock_compiled_tasks + [mock_link_task]

        i = 1
        for task in mock_tasks:
            task.run = lambda: True
            task.outputs = []
            for j in range(1, i + 1):
                mock_output = mock.Mock()
                mock_output.bldpath = mock.Mock(
                    return_value='output_{}_{}'.format(i, j))
                mock_output.srcpath = mock.Mock(
                    return_value='build/' + mock_output.bldpath())
                task.outputs.append(mock_output)
            i += 1

        # call collect_data_from_tasks
        tool.collect_data_from_tasks(mock_self)

        # check that a add_post_fun has been called
        mock_self.bld.add_post_fun.assert_has_calls(
            [mock.call(tool.get_sizes), mock.call(tool.save_data)])

        # check that all tasks has been created
        self.assertEqual(
            set([o.bldpath() for t in mock_tasks for o in t.outputs]),
            set(tool.new_build_statistics.keys()))

        mock_group = mock.Mock()
        mock_group.tasks = mock_tasks
        mock_self.groups = [[mock_group]]

        with mock.patch('os.path.getsize', lambda path: 1024 * 10):
            tool.get_sizes(mock_self)

        # check that a size is now present for all outputs
        for key, value in tool.new_build_statistics.items():
            self.assertTrue('size' in value)

        # implicitly call collect_data_from_run by calling task.run
        mock_time = mock.Mock(side_effect=range(0, len(mock_tasks * 2) * 5, 5))
        with mock.patch('time.time', mock_time):
            for task in mock_tasks:
                self.assertEqual(True, task.run())

        # check results
        expected_new_build_statistics = {
            'output_1_1': {
                'time': {'value': 5, 'unit': 's'},
                'size': {'value': 10, 'unit': 'kb'}},
            'output_2_1': {
                'time': {'value': 5, 'unit': 's'},
                'size': {'value': 10, 'unit': 'kb'}},
            'output_2_2': {
                'time': {'value': 5, 'unit': 's'},
                'size': {'value': 10, 'unit': 'kb'}},
            'output_3_1': {
                'time': {'value': 5, 'unit': 's'},
                'size': {'value': 10, 'unit': 'kb'}},
            'output_3_2': {
                'time': {'value': 5, 'unit': 's'},
                'size': {'value': 10, 'unit': 'kb'}},
            'output_3_3': {
                'time': {'value': 5, 'unit': 's'},
                'size': {'value': 10, 'unit': 'kb'}}
        }

        self.assertEqual(
            expected_new_build_statistics,
            tool.new_build_statistics)

        # setup mocks for save_data
        mock_self.bld.has_tool_option = lambda option: False
        # call save_data
        mock_json_dump = mock.Mock()
        mock_Logs = mock.Mock()
        with \
                mock.patch(open_module, mock.mock_open()), \
                mock.patch('tool.Logs', mock_Logs), \
                mock.patch('json.dump', mock_json_dump):
            tool.save_data(mock_self.bld)

        # collect what's been written to stdout
        stdout = ''
        # check state of the various outputs.
        for call in mock_Logs.pprint.mock_calls:
            # for some reason this is needed to access the calls parameters
            call = call[1]
            message = call[1]
            stdout += message
            if 'output_1_1' in message:
                # the only output which has been changed is output_1_1
                self.assertIn('changed', message)
                # the only output which has been removed is output_old_1
            elif 'output_old_1' in message:
                self.assertIn('removed', message)
            elif 'output' in message:
                # the rest is added
                self.assertIn('added', message)

            # check that the time uses s as a unit (not the best test)
            if 'time' in message:
                self.assertIn('s', message)

            # check that the time uses kb as a unit (not the best test)
            if 'size' in message:
                self.assertIn('kb', message)

        # check that all
        for t in mock_tasks:
            for o in t.outputs:
                key = o.bldpath()
                # output_2_1 hasn't changed hence we don't want to see
                # information about it.
                if key == 'output_2_1':
                    self.assertTrue(key not in stdout)
                else:
                    self.assertIn(key, stdout)


class TestToolLive(unittest.TestCase):

    """Test on test project using the most current version of the tool."""

    file_to_create = os.path.join('src', 'test_project', 'test.cpp')

    @classmethod
    def setUpClass(cls):
        """Setup and configure test-project."""
        cls.bundle_dependencies = 'bundle_dependencies'
        test_project_name = 'test-project'
        test_project_path = os.path.join(
            os.path.dirname(__file__), test_project_name)

        # setup
        cls.old_cwd = os.getcwd()
        os.chdir(test_project_path)

        # remove test file if it already exists. This may happen due to test
        # failure.
        if os.path.exists(cls.file_to_create):
            os.remove(cls.file_to_create)

        subprocess.check_output([
            sys.executable,
            'waf',
            'configure',
            '--bundle-path={bundle_dependencies}'.format(
                bundle_dependencies=cls.bundle_dependencies),
            '--bundle=ALL,-waf-build-statistics',
            '--waf-build-statistics-path=..'])

    @classmethod
    def tearDownClass(cls):
        """Clean up after tests has been done on the test project."""
        subprocess.check_output([sys.executable, 'waf', 'clean'])
        subprocess.check_output([sys.executable, 'waf', 'distclean'])
        subprocess.check_output(['rm', '-rf', cls.bundle_dependencies])
        subprocess.check_output(['rm', '-rf', 'build'])

        os.chdir(cls.old_cwd)

    def assert_regex(self, output, expected_output):
        """Handle deprecated regex check."""
        if sys.version[0] == '2':
            self.assertRegexpMatches(output, expected_output)
        else:
            pass

    def test_on_live_project(self):
        """Test tool on a live test project."""
        output = subprocess.check_output([sys.executable, 'waf', 'build'])

        # Make sure we are not printing anything since nothing has changed.
        expected_output = (
            "Waf: Entering directory `.*'\n"
            "\[\d\/3\] Compiling .*main\.cpp\n"
            "\[\d\/3\] Compiling .*some\.cpp\n"
            "\[\d\/3\] Linking .*test-project.*\n"
            "Waf: Leaving directory `.*'\n"
            "'build' finished successfully \(.*\)")

        self.assert_regex(output, expected_output)

        build_statistics_path = \
            os.path.join('build', 'linux', 'build_statistics.json')
        build_stats = None
        with open(build_statistics_path) as build_statistics:
            build_stats = json.load(build_statistics)

        self.assertIsNotNone(build_stats)
        expect_outputs = [
            'src/test_project/some.cpp.1.o',
            'src/test_project/main.cpp.1.o',
            'src/test_project/test-project']

        self.assertSetEqual(set(expect_outputs), set(build_stats.keys()))

        expected_results = ['time', 'size']
        for output, results in build_stats.items():
            self.assertSetEqual(set(expected_results), set(results.keys()))
            for result in results:
                self.assertNotEqual(0, results[result]['value'])

        # add a file and rebuild to check that we register the event
        with open(TestToolLive.file_to_create, 'a+'):
            pass

        output = subprocess.check_output([sys.executable, 'waf', 'build'])
        # the file is removed now since it doesn't affect the results and more
        # importantly ensures that the state of the test project is not
        # invalidated by left over files if a test fails.
        os.remove(TestToolLive.file_to_create)

        build_stats = None
        with open(build_statistics_path) as build_statistics:
            build_stats = json.load(build_statistics)

        self.assertIsNotNone(build_stats)
        expect_outputs.append('src/test_project/test.cpp.1.o')
        self.assertSetEqual(set(expect_outputs), set(build_stats.keys()))

        expected_output = (
            "(.|\n)*\[ FILE   \] src/test_project/test\.cpp\.1\.o \(added\)"
            "(.|\n)*\[ FILE   \] src/test_project/test-project \(changed\)"
            "(.|\n)*")

        self.assert_regex(output, expected_output)

        # test run after file has been removed.
        output = subprocess.check_output([sys.executable, 'waf', 'build'])

        build_stats = None
        with open(build_statistics_path) as build_statistics:
            build_stats = json.load(build_statistics)

        self.assertIsNotNone(build_stats)
        expect_outputs.remove('src/test_project/test.cpp.1.o')
        self.assertSetEqual(set(expect_outputs), set(build_stats.keys()))

        expected_output = (
            "(.|\n)*\[ FILE   \] src/test_project/test\.cpp\.1\.o \(removed\)"
            "(.|\n)*\[ FILE   \] src/test_project/test-project \(changed\)"
            "(.|\n)*")

        self.assert_regex(output, expected_output)


def main():
    """Main function."""
    unittest.main()


if __name__ == "__main__":
    main()
