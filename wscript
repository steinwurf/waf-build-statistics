#!/usr/bin/env python
# encoding: utf-8

"""
Waf buildscript which includes the tool.

The actual funcionality of this tool is found in tool.py in this repository.
"""

APPNAME = 'waf-build-statistics'
VERSION = '2.0.0'


def configure(conf):
    """Load the tool."""
    conf.load('tool', conf.path.abspath())
