# Revit 2025 API & Runtime Memory

Guidelines for targeting Autodesk Revit 2025.

---

## 1. The .NET 8 Shift
- **Target Runtime:** **.NET 8** (no longer .NET Framework).
- **Impact on Libraries:** C# add-ins and custom assembly dependencies (`bin/` dlls) must target .NET 8. Legacy .NET Framework dlls will fail to load or cause unpredictable runtime crashes.
- **Dependency Loading:** Assembly resolution uses .NET Core's loading context mechanism.

---

## 2. API Deprecations & Changes
- **Deprecated Structural Properties:** Several properties on structural elements like `FamilyInstance.StructuralUsage` or structural analytical models have been deprecated or moved to new interfaces.
- **Topography & Toposolid:** Revit 2025 relies fully on the `Toposolid` class. The legacy `TopographySurface` API is deprecated. Ensure creation tools target `Toposolid.Create()` and related methods.
- **Unit API:** Strict enforcement of `ForgeTypeId` for parameter definitions. Legacy unit conversions will throw compilation errors.
- **Addin Folder Paths:** Because Revit 2025 runs on .NET 8, the default user-addins paths remain standard, but the add-in loading order has been modified.
