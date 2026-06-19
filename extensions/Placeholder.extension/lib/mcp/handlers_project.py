# -*- coding: utf-8 -*-
"""pyRevit Routes - Project details endpoint handlers for MCP."""

from pyrevit import script
import clr
clr.AddReference("RevitAPI")
from Autodesk.Revit.DB import (
    AttachmentType,
    FilteredElementCollector,
    FilteredWorksetCollector,
    Level,
    WorksetKind,
    RevitLinkInstance,
    CADLinkType,
    ModelPathUtils,
)

from mcp.response import make_ok, make_error

logger = script.get_logger()


def _require_doc(tool, doc):
    if doc is None:
        return make_error(
            tool,
            "no_document",
            "No project document is open in the active Revit session.",
            checks=[
                "Open a Revit project (.rvt) before calling this tool.",
                "Call revit_health_ping to check document state.",
            ],
        )
    return None


def get_project_info(doc, request):
    """Get metadata about the currently open Revit project."""
    tool = "revit_project_info"
    err = _require_doc(tool, doc)
    if err:
        return err
    try:
        info = doc.ProjectInformation
        path = _safe_doc_path(doc)
        is_workshared = _safe_is_workshared(doc)

        return make_ok(
            tool,
            {
                "title": _safe_doc_title(doc),
                "path": path,
                "is_workshared": is_workshared,
                "project_number": _safe_str(info.Number),
                "project_name": _safe_str(info.Name),
                "client_name": _safe_str(info.ClientName),
                "project_address": _safe_str(info.Address),
                "project_status": _safe_str(info.Status),
                "issue_date": _safe_str(info.IssueDate),
            },
            doc=doc,
            next_actions=[
                "Call revit_project_levels for level data.",
                "Call revit_project_worksets for workset state.",
                "Call revit_project_links for linked model state.",
            ],
        )
    except Exception as exc:
        logger.error("pyRevit MCP routes_project/info error: {}".format(exc))
        return make_error(
            tool, "revit_error",
            "Unexpected error reading project info: " + str(exc),
            doc=doc,
        )


def get_project_levels(doc, request):
    """Get all levels defined in the project, sorted by elevation."""
    tool = "revit_project_levels"
    err = _require_doc(tool, doc)
    if err:
        return err
    try:
        collector = FilteredElementCollector(doc).OfClass(Level)
        levels = []
        for lvl in collector:
            levels.append({
                "name": lvl.Name,
                "elevation_feet": lvl.Elevation,
                "id": lvl.Id.IntegerValue,
            })
        levels.sort(key=lambda x: x["elevation_feet"])

        return make_ok(
            tool,
            {
                "count": len(levels),
                "levels": levels,
            },
            doc=doc,
        )
    except Exception as exc:
        logger.error("pyRevit MCP routes_project/levels error: {}".format(exc))
        return make_error(
            tool, "revit_error",
            "Unexpected error reading levels: " + str(exc),
            doc=doc,
        )


def get_project_worksets(doc, request):
    """Get all user worksets in the currently open workshared Revit project."""
    tool = "revit_project_worksets"
    err = _require_doc(tool, doc)
    if err:
        return err

    if not _safe_is_workshared(doc):
        return make_ok(
            tool,
            {"workshared": False, "worksets": []},
            doc=doc,
            messages=["This project is not workshared. No user worksets exist."],
        )

    try:
        collector = FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset)
        worksets = []
        for ws in collector:
            worksets.append({
                "name": ws.Name,
                "id": ws.Id.IntegerValue,
                "is_open": bool(ws.IsOpen),
                "owner": _safe_str(ws.Owner) if ws.Owner else None,
            })
        worksets.sort(key=lambda x: x["name"])

        return make_ok(
            tool,
            {
                "workshared": True,
                "count": len(worksets),
                "worksets": worksets,
            },
            doc=doc,
        )
    except Exception as exc:
        logger.error("pyRevit MCP routes_project/worksets error: {}".format(exc))
        return make_error(
            tool, "revit_error",
            "Unexpected error reading worksets: " + str(exc),
            doc=doc,
        )


def get_project_links(doc, request):
    """Get all linked Revit models and CAD files in the project."""
    tool = "revit_project_links"
    err = _require_doc(tool, doc)
    if err:
        return err
    try:
        collector = FilteredElementCollector(doc).OfClass(RevitLinkInstance)
        links = []
        for inst in collector:
            link_doc = inst.GetLinkDocument()
            ltype = doc.GetElement(inst.GetTypeId())
            loaded_path = None
            load_state = "unknown"

            try:
                ext_file_ref = ltype.GetExternalFileReference()
                loaded_path = _safe_model_path_to_string(
                    ext_file_ref.GetAbsolutePath() if ext_file_ref else None
                )
                load_state = _get_load_state(ltype)
            except Exception:
                pass

            links.append({
                "name": inst.Name,
                "id": inst.Id.IntegerValue,
                "type": "revit",
                "loaded": link_doc is not None or load_state == "loaded",
                "load_state": load_state,
                "path": loaded_path,
                "is_overlay": _safe_is_overlay(inst),
            })

        cad_collector = FilteredElementCollector(doc).OfClass(CADLinkType)
        for cad in cad_collector:
            try:
                ext_file_ref = cad.GetExternalFileReference()
                cad_path = _safe_model_path_to_string(
                    ext_file_ref.GetAbsolutePath() if ext_file_ref else None
                )
                cad_load_state = _get_load_state(cad)
            except Exception:
                cad_path = None
                cad_load_state = "unknown"
            links.append({
                "name": cad.Name,
                "id": cad.Id.IntegerValue,
                "type": "cad",
                "loaded": cad_load_state == "loaded",
                "load_state": cad_load_state,
                "path": cad_path,
                "is_overlay": None,
            })

        links.sort(key=lambda x: x["name"])
        return make_ok(
            tool,
            {
                "count": len(links),
                "links": links,
            },
            doc=doc,
            next_actions=[
                "Check 'loaded: false' entries for unloaded links before issuing."
            ],
        )
    except Exception as exc:
        logger.error("pyRevit MCP routes_project/links error: {}".format(exc))
        return make_error(
            tool, "revit_error",
            "Unexpected error reading links: " + str(exc),
            doc=doc,
        )


def _safe_str(value):
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _safe_doc_path(doc):
    try:
        return doc.PathName if doc.PathName else None
    except Exception:
        return None


def _safe_doc_title(doc):
    try:
        return doc.Title
    except Exception:
        return None


def _safe_is_workshared(doc):
    for attr_name in ("IsWorkshared", "IsWorkShared"):
        try:
            return bool(getattr(doc, attr_name))
        except Exception:
            pass
    return False


def _get_load_state(link_type):
    try:
        if hasattr(link_type, "GetLinkedFileStatus"):
            return _enum_to_snake(link_type.GetLinkedFileStatus())
    except Exception:
        pass

    try:
        ref = link_type.GetExternalFileReference()
        if ref is None:
            return "not_found"
        return _enum_to_snake(ref.GetLinkedFileStatus())
    except Exception:
        return "unknown"


def _safe_is_overlay(inst):
    try:
        ltype_elem = inst.Document.GetElement(inst.GetTypeId())
        if hasattr(ltype_elem, "AttachmentType"):
            return ltype_elem.AttachmentType == AttachmentType.Overlay
    except Exception:
        pass
    return None


def _safe_model_path_to_string(model_path):
    if model_path is None:
        return None
    try:
        visible_path = ModelPathUtils.ConvertModelPathToUserVisiblePath(model_path)
        return _safe_str(visible_path)
    except Exception:
        return _safe_str(model_path)


def _enum_to_snake(value):
    raw = str(value)
    if "." in raw:
        raw = raw.split(".")[-1]

    chars = []
    index = 0
    for ch in raw:
        if ch.isupper() and index > 0:
            chars.append("_")
        chars.append(ch.lower())
        index += 1
    return "".join(chars)
