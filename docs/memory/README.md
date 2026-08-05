# Revit Version Memory Overlays

This folder contains version-specific reference files that outline API shifts, runtime deprecations, and target .NET environments for different Revit releases.

---

## Why Version Overlays Matter

Revit API interfaces change rapidly between releases. In addition, Autodesk changed the underlying framework runtime across recent versions:
- **Revit 2024 and older:** Uses legacy .NET Framework 4.8.
- **Revit 2025 and 2026:** Uses modern .NET 8.
- **Revit 2027:** Uses modern .NET 10.

AI coding assistants often confuse these details, leading to scripts that use deprecated methods or compile assemblies targeting the wrong .NET version.

---

## Structure of this Directory

- `revit-2024.md`: Specific considerations for Revit 2024 and .NET Framework 4.8 compatibility.
- `revit-2025.md`: .NET 8 targeting, dependency-loading cautions, current unit
  APIs, and the Revit 2024 transition from legacy topography to Toposolid.
- `revit-2027.md`: .NET 10 targeting and Autodesk's documented all-users add-in
  and application-plugin folder relocations.

---

## How Agents Use This

AI coding agents are instructed to read the specific markdown file matching the user's targeted Revit environment before drafting any script or library.
