#!/usr/bin/env python
# encoding: utf-8

"""
Waf buildscript which includes the tool.

The actual funcionality of this tool is found in tool.py in this repository.
"""


def configure(conf):
    """Load the tool."""
    conf.load('tool', conf.path.abspath())
