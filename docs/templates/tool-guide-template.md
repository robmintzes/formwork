# Tool Guide Template — [Tool Name]

> [!NOTE]
> Provide a 1-2 sentence overview of the tool. Who is it for? What is the main problem it solves?

---

## 1. User Workflow & How to Use

Explain step-by-step how a human user interacts with this tool.

1. **Access Point**: Where is the button located on the ribbon? (e.g., *[Extension Name] Tools Tab* -> *[Panel Name] Panel* -> *[Button Name]*).
2. **User Input / Dialog**: 
   - What dialog box or primitive prompt pops up? (Embed a screenshot if applicable).
   - What inputs are required from the user?
3. **Execution**:
   - What happens when the user clicks "OK" or "Run"?
   - What feedback is displayed in the pyRevit output window?

---

## 2. Technical Design & Revit API Context

Detailed technical specification for developers and AI agents.

### API Environment Requirements
* **Min Revit Version**: e.g., 2024
* **Target Document Context**: (Project, Family, or Sheet View)
* **Revit API Selection Type**: (e.g., active selection, user picked element, or filtered element collector)

### Risk & Transaction Profile
* **Risk Classification**: (Low, Medium, High)
* **Modifies Database**: (Yes / No)
* **Transaction Details**: 
  - Transaction Name: `"[Transaction Name]"`
  - Description of database modifications.
  - Exception handling & rollback strategy.

---

## 3. Implementation Details

Provide a brief architectural outline of how the script is structured.

* **Key Classes/Methods used**: (e.g., `Autodesk.Revit.DB.FilteredElementCollector`, etc.)
* **External Dependencies**: (e.g., shared libraries, third-party libraries, etc.)
* **Linked Model Policy**: 
  - (How does the tool handle linked models? Note that linked models are read-only).

---

## 4. Troubleshooting & Common Failures

List potential issues, error codes, and how to resolve them.

* **"No active document" Error**:
  * *Cause*: Running the tool without a project file open.
  * *Fix*: Open a project document and try again.
* **Operation Canceled Exception**:
  * *Cause*: The user pressed `ESC` during element selection.
  * *Fix*: Safe exit; no action required.
* **[Error Message / Bug]**:
  * *Cause*: Describe what triggers this issue.
  * *Fix*: Step-by-step resolution.

---

## 5. Changelog

Record incremental changes and updates to this tool.

* **v1.0.0 (YYYY-MM-DD)**:
  * Initial release.
