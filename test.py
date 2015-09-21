#!/usr/bin/env python
# encoding: utf-8

"""Unit test for tool.py"""

import sys
import imp
import unittest


waflib = imp.new_module('waflib')
MockTaskGen = imp.new_module('TaskGen')


class mock_feature(object):
    def __init__(self, wild_card):
        pass
    def __call__(self, func):
        return func


class mock_before_method(object):
    def __init__(self, wild_card):
        pass
    def __call__(self, func):
        return func


class mock_after_method(object):
    def __init__(self, wild_card):
        pass
    def __call__(self, func):
        return func


setattr(MockTaskGen, 'feature', mock_feature)
setattr(MockTaskGen, 'before_method', mock_before_method)
setattr(MockTaskGen, 'after_method', mock_after_method)
setattr(waflib, 'TaskGen', MockTaskGen)


class MockLogs(object):
    def __init__(self):
        super(MockLogs, self).__init__()
setattr(waflib, 'Logs', MockLogs)

sys.modules['waflib'] = waflib

import tool

class MockTask(object):
    """docstring for Task"""
    def __init__(self):
        super(Task, self).__init__()
        self.output_tasks = []


class TestTool(unittest.TestCase):
    def test_tool(self):
        def func():
            pass
        mock_task = MockTask()
        tool.collect_data_from_run(f, mock_task)