# Revit 2027 API & Runtime Memory

Guidelines for targeting Autodesk Revit 2027.

---

## 1. The .NET 10 Shift
- **Target Runtime:** **.NET 10**.
- **Impact on Libraries:** Compiled add-ins and custom binary DLLs must target .NET 10. Verify target frameworks inside `.csproj` configurations are updated accordingly.

---

## 2. Strict Signed Add-in Policy
- **Signing Requirement:** Revit 2027 enforces strict security controls for external add-ins. Unsigned DLLs loading into ProgramData folders may be rejected or trigger warning dialogs ("not signed as internal addin").
- **Supply Chain Safety:** Ensure CI/CD pipelines compile and sign output binaries using code-signing certificates before deploying to end-user machines.

---

## 3. Deployment Folder Relocations
- **All-Users Paths:** Avoid deploying raw manifests directly to `%PROGRAMDATA%\Autodesk\Revit\Addins\2027\` without proper admin installer configurations.
- **User-Specific Paths:** Use user-level app data folders (`%APPDATA%\Autodesk\Revit\Addins\2027\`) for rapid development and testing to bypass strict security blocks during development.
