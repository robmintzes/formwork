# Revit 2025 API & Runtime Memory

Guidelines for targeting Autodesk Revit 2025.

---

## Verification metadata

- **Last source review:** 2026-10-01 (runtime section); 2026-08-04 (API section)
- **Primary sources:** Autodesk's [Revit .NET 8 migration guide](https://help.autodesk.com/cloudhelp/2026/ENU/Revit-API/files/Revit_API_Developers_Guide/Introduction/Getting_Started/Using_the_Autodesk_Revit_API/Revit_API_Revit_API_Developers_Guide_Introduction_Getting_Started_Using_the_Autodesk_Revit_API_NET8_Update_html.html), [Revit 2025 API changes](https://help.autodesk.com/view/RVT/2025/ENU/?caas=caas/blog/thebuildingcoder.typepad.com/blog/2024/04/whats-new-in-the-revit-2025-api.html), and [Revit 2024 Toposolid change](https://help.autodesk.com/view/RVT/2024/ENU/?caas=caas/blog/thebuildingcoder.typepad.com/blog/2023/04/whats-new-in-the-revit-2024-api.html)
- **Boundary:** Compile against the exact Revit 2025 assemblies and run in-host tests; source review alone cannot prove dependency or pyRevit-engine compatibility.

---

## 1. Runtime: .NET 8, then .NET 10 from the 2025.5 / 2026.5 updates

> **Updated 2026-10-01.** Autodesk moved Revit 2025 and 2026 from .NET 8 to
> **.NET 10** in the 2025.5 and 2026.5 updates (no API changes), because .NET 8
> support ends in November 2026
> ([Autodesk Developer Blog](https://blog.autodesk.io/autodesk-desktop-products-2025-2026-net-10-updates/),
> [APS preview announcement](https://aps.autodesk.com/blog/call-preview-testing-revit-20262025-migration-net-10)).
> This was verified on the reference workstation: the installed Revit 2025
> (build 20260827) and 2026 (build 20260731) `RevitAPI.dll` files reference
> `System.Runtime 10.0.0.0`.

- **Target runtime:**
  - Revit 2025 before the .5 update: .NET 8.
  - 2025.5 and later: .NET 10.
  - Find which one an install uses from the build or its `RevitAPI.dll` references. Do not assume from the year alone.
- **C# add-ins:**
  - Build for `net10.0-windows` when targeting updated installs; `net8.0-windows` assemblies may still load unless they hit .NET 10 breaking changes or .NET 8-only dependencies.
  - Audit incompatible packages, library references, and obsolete APIs.
  - The generated `revit-addin` starter selects the framework from the installed host.
- **Dependency loading:** .NET 8 assembly probing differs from .NET Framework 4.8. Test every bundled binary dependency instead of assuming a legacy DLL will load.

---

## 2. API changes and cautions

- **Topography and Toposolid:** `Toposolid` superseded `TopographySurface` in Revit 2024. The legacy class remained for backward compatibility, while its creation and point-editing methods were deprecated. Use `Toposolid` for new tools; do not claim that every legacy topography API disappeared in 2025.
- **Units:** Continue to use the `ForgeTypeId`-based unit APIs and the correct identifier kind for each method. Do not treat all legacy unit members as compile errors without checking the exact 2025 API member.
- **Version targeting:** API removals are member-specific. Check Autodesk's 2025 change list before describing an API as removed, moved, or deprecated.
