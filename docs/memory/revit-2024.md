# Revit 2024 API & Runtime Memory

Guidelines for targeting Autodesk Revit 2024.

---

## Verification metadata

- **Last source review:** 2026-08-04
- **Primary sources:** Autodesk's [Revit 2024 Units developer guide](https://help.autodesk.com/cloudhelp/2024/ENU/Revit-API/files/Revit_API_Developers_Guide/Introduction/Application_and_Document/Revit_API_Revit_API_Developers_Guide_Introduction_Application_and_Document_Units_html.html) and [.NET migration guide](https://help.autodesk.com/cloudhelp/2026/ENU/Revit-API/files/Revit_API_Developers_Guide/Introduction/Getting_Started/Using_the_Autodesk_Revit_API/Revit_API_Revit_API_Developers_Guide_Introduction_Getting_Started_Using_the_Autodesk_Revit_API_NET8_Update_html.html)
- **Boundary:** Source review does not replace compiling against the Revit 2024 assemblies or testing inside the selected pyRevit build.

---

## 1. Runtime framework

- **Target runtime:** .NET Framework 4.8.
- **pyRevit Python engine:** Engine availability and version come from the installed pyRevit build and configuration, not from Revit itself. Verify the configured engine in the live Revit/pyRevit combination.
- **Binary dependencies:** Build and test compiled dependencies against the Revit 2024 .NET Framework host. Do not infer runtime compatibility from a library's target label alone.

---

## 2. Key API reference caveats

- **Unit conversions:** Revit 2024 uses `ForgeTypeId` identifiers for the current unit APIs. `UnitUtils.ConvertFromInternalUnits` requires a unit identifier such as `UnitTypeId.Millimeters`, not a measurable-spec identifier such as `SpecTypeId.Length`.
  ```python
  # Convert Revit's internal length unit (feet) to millimeters.
  mm = DB.UnitUtils.ConvertFromInternalUnits(value, DB.UnitTypeId.Millimeters)
  ```
- **Unit parsing:** APIs such as `UnitFormatUtils.TryParse` accept a measurable spec such as `SpecTypeId.Length`; that does not make the spec valid for `ConvertFromInternalUnits`.
- **Views and viewports:** Sheet viewport positions use Revit's internal length unit (feet).
- **Selection filters:** Implement the standard `ISelectionFilter` interface and handle user cancellation explicitly.
- **Transactions:** Use `DB.Transaction(doc, "Name")`, keep transaction scopes narrow, and never prompt while a transaction is open.
