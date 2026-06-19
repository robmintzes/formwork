# Revit 2024 API & Runtime Memory

Guidelines for targeting Autodesk Revit 2024.

---

## 1. Runtime Framework
- **Target Runtime:** .NET Framework 4.8.
- **Python Runtime:** IronPython 2.7.x or CPython 3.8.x inside pyRevit.
- **Assembly Loading:** Standard .NET Framework assembly resolution. External libraries must target .NET Framework 4.8 or standard .NET Standard 2.0.

---

## 2. Key API Reference Caveats
- **Structural API:** Use of legacy structural command parameters and properties.
- **Unit Conversions:** Revit 2024 uses the `ForgeTypeId` system (introduced in 2021/2022) for all units. Avoid legacy `DisplayUnitType` or `UnitType` enumerations.
  - Correct unit parsing:
    ```python
    # Convert feet to millimeters
    mm = DB.UnitUtils.ConvertFromInternalUnits(value, DB.SpecTypeId.Length)
    ```
- **Views & Viewports:** Sheet viewports are positioned using sheet-space coordinates in feet.
- **Selection filters:** Standard implementation of `ISelectionFilter` interface.
- **Transactions:** Standard `DB.Transaction(doc, "Name")` constructor.
