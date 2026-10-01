# Revit 2027 API & Runtime Memory

Guidelines for targeting Autodesk Revit 2027.

---

## Verification metadata

- **Last source review:** 2026-08-04
- **Primary source:** Autodesk's [Revit 2027 major API changes](https://help.autodesk.com/view/RVT/2027/ENU/?guid=f7165618-24c9-4160-a7a4-09979fe4a981)
- **Boundary:** Compile against the released Revit 2027 assemblies and test add-in discovery and pyRevit behavior in the installed host.

---

## 1. The .NET 10 shift

- **Target runtime:** .NET 10.
- **C# add-ins:** Install the .NET 10 SDK and build Revit 2027 add-ins against .NET 10. Autodesk's migration example identifies SDK `10.0.100`.
- **Dependencies:** Audit breaking changes introduced since .NET 8 and test compiled dependencies in Revit 2027.

---

## 2. Add-in installation folder changes

- **All-users manifests:** Revit's all-users add-in search location moved from `C:\ProgramData\Autodesk\Revit\Addins\20XX` to `C:\Program Files\Autodesk\Revit\Addins\20XX`.
- **Application plugins:** The all-users application-plugin location moved from `C:\ProgramData\Autodesk\ApplicationPlugins` to `C:\Program Files\Autodesk\ApplicationPlugins`.
- **Per-user manifests:** Per-user add-in locations remain supported.
- **Scope:** These are Revit add-in manifest locations, not pyRevit extension search paths. Register pyRevit extension roots through pyRevit's own configuration.

The cited Autodesk API change list documents the location changes and new dependency-isolation options. It does **not** establish a blanket Revit 2027 rule that every unsigned DLL is rejected, so do not encode or repeat such a requirement without a separate authoritative source.
