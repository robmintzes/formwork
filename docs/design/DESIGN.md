---
version: "1.0"
name: "Generic Firm Toolbar Design System"
description: "Repository-level UI design standards for WPF/XAML dialogs, pyRevit forms, and HTML outputs."
colors:
  primary: "#1A365D"          # Deep Navy
  primary-light: "#2B6CB0"    # Steel Blue
  secondary: "#4A5568"        # Slate Gray
  background: "#F7FAFC"       # Light Cool Gray
  surface: "#FFFFFF"          # White
  border: "#E2E8F0"           # Subtle Divider Gray
  text-main: "#2D3748"        # Dark Gray Body
  text-muted: "#718096"       # Medium Gray Secondary
  success: "#38A169"          # Forest Green
  warning: "#DD6B20"          # Warm Orange
  danger: "#E53E3E"           # Dark Red
typography:
  family: "Segoe UI, Arial, sans-serif"
  size-title: "16px"
  size-body: "12px"
  size-small: "11px"
---

# UI / UX Design Standards

This document establishes the visual guidelines and design tokens for custom tools in our pyRevit extension. Adherence to these standards ensures a consistent look and feel across both C# WPF dialogs and Python HTML outputs.

---

## 1. Color Palette & Typography

Our design system utilizes clean, professional tokens designed for high readability in high-resolution CAD and BIM monitor setups:
- **Primary Color:** Deep Navy (`#1A365D`) for headers, primary action buttons, and active tabs.
- **Accents:** Steel Blue (`#2B6CB0`) for hover states, focus outlines, and hyperlink text.
- **System States:**
  - **Success:** Forest Green (`#38A169`) for positive progress and completion audits.
  - **Warning:** Orange (`#DD6B20`) for non-blocking notifications or user action requirements.
  - **Danger:** Dark Red (`#E53E3E`) for destructive actions (e.g. element deletions, purging).

---

## 2. WPF / XAML Window Guidelines

When building custom C# or Python WPF forms, ensure windows follow these rules:
- **Margins & Padding:** Maintain a strict `12px` or `16px` outer padding for window boundaries. Inner controls should use standard Spacing (`8px` or `12px`).
- **Control Sizing:**
  - Buttons should have a minimum height of `28px` to ensure they are easy to click.
  - Textboxes and dropdown select menus should share the same height rules as buttons.
- **Window Hierarchy:** Title Bar (Bold Segoe UI, Primary Color) -> Content Workspace -> Footer Action Bar (Right-aligned Primary Action, Left-aligned Cancel/Close).

---

## 3. HTML / CSS Report Guidelines

For scripts that generate rich HTML text summaries or export audit summaries to the pyRevit output window:
- Use a single, clean container wrapping the output.
- Avoid raw browser default colors. Style links, tables, and headers using the colors specified in the tokens frontmatter.
- Apply subtle hover animations to rows inside table audits to improve data scan-ability.
