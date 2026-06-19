# -*- coding: utf-8 -*-
"""Startup script for Placeholder extension."""
from pyrevit import logger

log = logger.get_logger("Placeholder Extension Startup")


def __init__(sender, args):
    log.info("Placeholder pyRevit Toolbar loaded successfully.")
