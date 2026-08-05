# Revit 2025 API & Runtime Memory

Guidelines for targeting Autodesk Revit 2025.

---

## Verification metadata

- **Last source review:** 2026-08-04
- **Primary sources:** Autodesk's [Revit .NET 8 migration guide](https://help.autodesk.com/cloudhelp/2026/ENU/Revit-API/files/Revit_API_Developers_Guide/Introduction/Getting_Started/Using_the_Autodesk_Revit_API/Revit_API_Revit_API_Developers_Guide_Introduction_Getting_Started_Using_the_Autodesk_Revit_API_NET8_Update_html.html), [Revit 2025 API changes](https://help.autodesk.com/view/RVT/2025/ENU/?caas=caas/blog/thebuildingcoder.typepad.com/blog/2024/04/whats-new-in-the-revit-2025-api.html), and [Revit 2024 Toposolid change](https://help.autodesk.com/view/RVT/2024/ENU/?caas=caas/blog/thebuildingcoder.typepad.com/blog/2023/04/whats-new-in-the-revit-2024-api.html)
- **Boundary:** Compile against the exact Revit 2025 assemblies and run in-host tests; source review alone cannot prove dependency or pyRevit-engine compatibility.

---

## 1. The .NET 8 shift

- **Target runtime:** .NET 8 (no longer .NET Framework 4.8).
- **C# add-ins:** Rebuild Revit 2025 add-ins for `net8.0-windows` and audit incompatible packages, library references, and obsolete APIs.
- **Dependency loading:** .NET 8 assembly probing differs from .NET Framework 4.8. Test every bundled binary dependency instead of assuming a legacy DLL will load.

---

## 2. API changes and cautions

- **Topography and Toposolid:** `Toposolid` superseded `TopographySurface` in Revit 2024. The legacy class remained for backward compatibility, while its creation and point-editing methods were deprecated. Use `Toposolid` for new tools; do not claim that every legacy topography API disappeared in 2025.
- **Units:** Continue to use the `ForgeTypeId`-based unit APIs and the correct identifier kind for each method. Do not treat all legacy unit members as compile errors without checking the exact 2025 API member.
- **Version targeting:** API removals are member-specific. Check Autodesk's 2025 change list before describing an API as removed, moved, or deprecated.
