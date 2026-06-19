# -*- coding: utf-8 -*-
"""Startup script for Placeholder extension."""
import sys
import os

from pyrevit import logger

log = logger.get_logger("Placeholder Extension Startup")


def __init__(sender, args):
    log.info("Placeholder pyRevit Toolbar loaded successfully.")
    try:
        ext_dir = os.path.dirname(__file__)
        lib_dir = os.path.join(ext_dir, "lib")
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        from mcp import startup as mcp_startup
        mcp_startup.init()
    except Exception as e:
        log.warning("Could not initialize MCP routes bridge: {}".format(e))
