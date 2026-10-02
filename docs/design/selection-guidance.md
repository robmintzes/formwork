# Canvas selection guidance

Every tool that uses native Revit canvas picks uses the generated UI kit's
`selection_guide.SelectionGuide`. Array Along Path is the first consumer; it is
currently the only generated tool with native picks. List/chooser dialogs have
their own instructions and need no canvas banner.

The strip sits at the top of the active drawing view, below the ribbon/view
tabs. It displays the tool and step, a direct instruction, Finish/Esc guidance,
step indicators and the firm's wordmark. Packaged fonts and brushes come from
the UI kit theme. A dark canvas receives a light strip; a light canvas receives
an inverse strip, so guidance contrasts with the drawing surface.

Validate context before entering the guide. Consume valid preselection without
flashing an empty banner. Show each step immediately before its native pick.
Use a context manager so cancellation/errors close the guide before preview,
result dialogs or transactions. No transaction spans a pick.

The component adapts active-UIView rectangle and DPI docking from the source
banner, recorded in R08. It uses pyRevit's [prompt-bar foundation](https://docs.pyrevitlabs.io/reference/pyrevit/forms/#pyrevit.forms.TemplatePromptBar)
with firm-local XAML. Branded-load failure falls back to the stock WarningBar;
if both are unavailable, native status prompts remain and diagnostics record it.

Static tests cover lifecycle cleanup, active-view selection, negative monitor
coordinates, DPI conversion, fallback and resource contracts. The native WPF
screenshot harness was blocked by the workstation's Cylance script policy;
no native screenshot is claimed for this component. Live docking, contrast,
preselection and Escape require checks in Revit at the target DPI/version.
