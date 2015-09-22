#!/usr/bin/env python
# encoding: utf-8

"""Unit test for tool.py."""

import sys
import imp
import os
import unittest
import mock


def load_tool():
    """Mock waflib and load the tool module."""
    waflib = imp.new_module('waflib')
    MockTaskGen = mock.Mock()

    def side_effect(wild_card):
        m = mock.Mock(side_effect=lambda func: func)
        return m

    MockTaskGen.feature = mock.Mock(side_effect=side_effect)
    MockTaskGen.before_method = mock.Mock(side_effect=side_effect)
    MockTaskGen.after_method = mock.Mock(side_effect=side_effect)

    setattr(waflib, 'TaskGen', MockTaskGen)

    MockLogs = mock.Mock()
    setattr(waflib, 'Logs', MockLogs)

    sys.modules['waflib'] = waflib

    return imp.load_module('tool', *imp.find_module('tool'))


class TestTool(unittest.TestCase):

    """Test tool."""

    def setUp(self):
        """Setup test."""
        # reload tool after each test to reset monkey patches
        self.tool = load_tool()

    def test_get_data(self):
        """Test the tool module's get_data function."""
        tool = self.tool

        mock_self = mock.Mock()
        # Set old_build_statistics to something so that the get_data assumes
        # that the data has already been read.
        tool.old_build_statistics = {'test': True}
        tool.get_data(mock_self)

        # Set old_build_statistics to something so that the get_data assumes
        # that the data has already been read.
        tool.old_build_statistics = None
        mock_self.bld = mock.Mock()
        mock_self.bld.bldnode = mock.Mock()
        mock_self.bld.bldnode.nice_path = mock.Mock(
            return_value='/non/existing/path')
        tool.get_data(mock_self)

        self.assertEqual(tool.old_build_statistics, {})

    def test_time_compiled_tasks(self):
        """Test the tool module's time_compiled_tasks function."""
        tool = self.tool

        # setup mocks
        mock_self = mock.Mock()
        mock_self.compiled_tasks = [mock.Mock(), mock.Mock(), mock.Mock()]
        mock_self.link_task = mock.Mock()

        # monkey patch collect_data_from_run
        tool.collect_data_from_run = lambda m1, m2: True

        # call function to test
        tool.time_compiled_tasks(mock_self)

        # make sure we've wrapped all the tasks.
        for m in mock_self.compiled_tasks:
            self.assertTrue(m.run is True)
        self.assertTrue(mock_self.link_task.run is True)

        # make sure we set the save_data function as a post_fun
        mock_self.bld.add_post_fun.assert_called_once_with(tool.save_data)

    def test_collect_data_from_run(self):
        """Test the tool module's collect_data_from_run function."""
        tool = self.tool

        # setup mocks
        mock_task = mock.Mock()
        mock_output = mock.Mock()
        mock_output.nice_path = lambda: "/nice/path"
        mock_task.outputs = [mock_output]
        mock_func = mock.Mock()

        # monkey patch used functions
        with mock.patch('os.path.getsize', lambda path: 1024), \
                mock.patch('time.time', lambda: 100):
            # call functions
            tool.collect_data_from_run(mock_func, mock_task)()

        mock_func.assert_called_once_with()

        expected_result = {
            mock_output.nice_path(): {
                'compile_time': 0,
                'file_size': 1
            }
        }
        self.assertEqual(tool.new_build_statistics, expected_result)

    def test_save_data(self):
        """Test the tool module's save_data function."""
        tool = self.tool

        # setup mocks
        mock_self = mock.Mock()
        mock_self.bldnode.nice_path = lambda: '.'
        mocked_open = mock.mock_open()
        tool.open = mocked_open
        tool.json = mock.Mock()

        tool.old_build_statistics = {
            'something':
            {
                'compile_time': 4,
                'file_size': 900
            },
            'something_else':
            {
                'compile_time': 42,
                'file_size': 50
            },
            'something_old':
            {
                'compile_time': 990,
                'file_size': 777
            }
        }

        tool.new_build_statistics = {
            'something':
            {
                'compile_time': 4,
                'file_size': 900
            },
            'something_else':
            {
                'compile_time': 1337,
                'file_size': 451
            },
            'something_new':
            {
                'compile_time': 1337,
                'file_size': 451
            }
        }

        tool.print_summary = mock.Mock()

        # call function
        tool.save_data(mock_self)

        # check results
        tool.print_summary.assert_called_once_with(
            tool.old_build_statistics,
            tool.new_build_statistics)

        mocked_open.assert_called_once_with(
            os.path.join('.', tool.filename), 'w')

        tool.json.dump.assert_called_once_with(
                {
                    'something':
                    {
                        'compile_time': 4,
                        'file_size': 900
                    },
                    'something_else':
                    {
                        'compile_time': 1337,
                        'file_size': 451
                    },
                    'something_new':
                    {
                        'compile_time': 1337,
                        'file_size': 451
                    },
                    'something_old':
                    {
                        'compile_time': 990,
                        'file_size': 777
                    }
                },
                mocked_open()
            )

    def test_print_summary(self):
        """Test the tool module's print_summary function."""
        tool = self.tool

        empty_new = {}
        empty_old = {}
        tool.compare_build = mock.Mock()
        tool.print_summary(empty_new, empty_old)
        self.assertEqual(0, tool.compare_build.call_count)

        new = {
            'something': {
                'compile_time': 2,
                'file_size': 222,
            },
            'something_else': {
                'compile_time': 2,
                'file_size': 222,
            }
        }

        tool.print_summary(new, empty_old)

        old = {
            'something': {
                'compile_time': 29,
                'file_size': 333,
            },
            'something_else': {
                'compile_time': 29,
                'file_size': 333,
            }
        }

        tool.print_summary(empty_new, old)

        self.assertEqual(0, tool.compare_build.call_count)

        tool.print_summary(new, old)
        tool.compare_build.assert_has_calls(
            [
                mock.call(
                    'something',
                    {'compile_time': 2, 'file_size': 222},
                    {'compile_time': 29, 'file_size': 333},
                    'compile_time'),
                mock.call(
                    'something',
                    {'compile_time': 2, 'file_size': 222},
                    {'compile_time': 29, 'file_size': 333},
                    'file_size'),
                mock.call(
                    'something_else',
                    {'compile_time': 2, 'file_size': 222},
                    {'compile_time': 29, 'file_size': 333},
                    'compile_time'),
                mock.call(
                    'something_else',
                    {'compile_time': 2, 'file_size': 222},
                    {'compile_time': 29, 'file_size': 333},
                    'file_size')
            ], any_order=True)

        tool.compare_build.assert_has_calls(
            [
                mock.call(
                    'total',
                    {'compile_time': 2 * 2, 'file_size': 222 * 2},
                    {'compile_time': 29 * 2, 'file_size': 333 * 2},
                    'compile_time'),
                mock.call(
                    'total',
                    {'compile_time': 2 * 2, 'file_size': 222 * 2},
                    {'compile_time': 29 * 2, 'file_size': 333 * 2},
                    'file_size')
            ], any_order=True)

    def test_compare_build(self):
        """Test the tool module's compare_build function."""
        tool = self.tool

        key = 'key'

        old_stats = {
            key: 4
        }
        new_stats = {
            key: 8
        }

        build = 'test'

        # check that something has been written
        tool.compare_build(build, old_stats, new_stats, key)
        self.assertEqual(1, tool.Logs.pprint.call_count)
        args, _ = tool.Logs.pprint.call_args
        self.assertEqual('PINK', args[0])

        tool.compare_build(build, new_stats, old_stats, key)
        self.assertEqual(2, tool.Logs.pprint.call_count)
        args, _ = tool.Logs.pprint.call_args
        self.assertEqual('CYAN', args[0])

        # check that nothing has been written
        tool.compare_build(build, old_stats, old_stats, key)
        self.assertEqual(2, tool.Logs.pprint.call_count)


def main():
    """Main function."""
    unittest.main()


if __name__ == "__main__":
    main()
