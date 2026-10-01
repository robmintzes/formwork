# -*- coding: utf-8 -*-
"""Small, Revit-version-neutral serialization helpers.

This module deliberately imports no Revit assemblies so it can be tested under
ordinary Python as well as loaded by IronPython inside pyRevit.
"""

__author__ = "Template Author"


def element_id_value(element_id):
    """Return a JSON-safe integer for an ElementId across Revit versions.

    Revit 2024 and newer expose the 64-bit ``Value`` property. Older releases
    expose ``IntegerValue``. Converting either result through Python's ``int``
    prevents a raw ``System.Int64`` object from leaking into JSON responses.
    """
    if element_id is None:
        return None

    try:
        value = element_id.Value
    except AttributeError:
        value = element_id.IntegerValue
    return int(value)
