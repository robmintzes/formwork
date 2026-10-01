"""Governance surface: agent instructions, branch policy, hooks, CI, ruleset.

Canonical rules live in one generated AGENTS.md; vendor-specific files are thin
pointers to it. Foundation validators and hooks are vendored so the workspace
validates itself; the few foundation-specific values in them are replaced by
asserted, exact substitutions (generation fails if a source file drifts).
Reads foundation resources only, never the workspace.
"""

from __future__ import annotations

import json
from pathlib import Path

from formwork_engine.adapters import RenderResult
from formwork_engine.diagnostics import Diagnostic
from formwork_engine.outputs import OWNERSHIP_SEED, text_file
from formwork_engine.profile import Profile
from formwork_engine.textutil import md, pascal, py_string, render_file
from formwork_engine.vendoring import VendoringError, substitute as _substitute

ADAPTER_ID = "governance"
FOUNDATION = Path(__file__).resolve().parents[2]
VENDORED = (
    "validators/__init__.py",
    "validators/check_branch_policy.py",
    "validators/check_bundle_structure.py",
    "validators/check_safety_rules.py",
    "validators/validate_toolbar_spec.py",
    ".githooks/check-branch",
    ".githooks/pre-commit",
    ".githooks/pre-push",
    "scripts/install-git-hooks.ps1",
)
POINTERS = {
    "CLAUDE.md": "Claude Code",
    "GEMINI.md": "Gemini CLI",
    ".github/copilot-instructions.md": "GitHub Copilot",
}
RULESET = ".github/rulesets/main-branch-ruleset.json"


def _vendored(profile: Profile) -> list:
    config = profile.config
    owner_example = config.maintainers[0].branch_prefix
    files = []
    for rel in VENDORED:
        text = (FOUNDATION / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
        if rel.endswith(".py"):
            text = _substitute(rel, text, '__author__ = "Template Author"', "__author__ = " + py_string(config.identity.author), required=False)
        if rel == "validators/check_branch_policy.py":
            text = _substitute(rel, text, "(e.g. robmintzes/fix-selection)", "(e.g. {}/fix-selection)".format(owner_example))
        if rel == "scripts/install-git-hooks.ps1":
            text = _substitute(rel, text, 'param([string]$Owner = "robmintzes")', "param([Parameter(Mandatory = $true)][string]$Owner)")
        files.append(text_file(rel, text, ADAPTER_ID))
    return files


def _ruleset(profile: Profile) -> str:
    data = json.loads((FOUNDATION / ".github" / "main-branch-ruleset.json").read_text(encoding="utf-8"))
    rules = {rule["type"]: rule for rule in data["rules"]}
    rules["pull_request"]["parameters"]["required_approving_review_count"] = profile.config.governance.required_approvals
    contexts = [check["context"] for check in rules["required_status_checks"]["parameters"]["required_status_checks"]]
    if contexts != ["branch-policy", "repository-validation"]:
        raise VendoringError("ruleset required checks changed; keep them aligned with the generated workflow job names")
    return json.dumps(data, indent=2, ensure_ascii=False)


def render(profile: Profile) -> RenderResult:
    config = profile.config
    identity = config.identity
    technical = config.technical
    governance = config.governance
    maintainers = "\n".join(
        "| {} | `{}` |".format(md(m.name), m.branch_prefix) for m in config.maintainers
    )
    first_prefix = config.maintainers[0].branch_prefix
    approvals = governance.required_approvals
    approval_text = (
        "No independent approval is required (single-maintainer default); pull requests and CI still are."
        if approvals == 0
        else "{} independent approval(s) are required before merging.".format(approvals)
    )
    common = {
        "display_name": md(identity.display_name),
        "first_prefix": first_prefix,
    }

    result = RenderResult()
    result.files.append(
        text_file(
            "AGENTS.md",
            render_file(
                "governance/AGENTS.md.tmpl",
                dict(
                    common,
                    maintainers=maintainers,
                    extension=technical.extension,
                    tab=technical.tab,
                    ns=pascal(technical.namespace),
                    author=md(identity.author),
                    support_url=identity.support_url,
                ),
            ),
            ADAPTER_ID,
        )
    )
    for path, client in sorted(POINTERS.items()):
        depth = path.count("/")
        target = "../" * depth + "AGENTS.md"
        result.files.append(
            text_file(path, render_file("governance/agent-pointer.md.tmpl", {"client": client, "agents_path": target}), ADAPTER_ID)
        )
    result.files.append(
        text_file(
            ".agents/skills/pyrevit-tool/SKILL.md",
            render_file(
                "governance/pyrevit-tool-SKILL.md.tmpl",
                {
                    "extension": technical.extension,
                    "tab": technical.tab,
                    "ns": pascal(technical.namespace),
                    "author": md(identity.author),
                },
            ),
            ADAPTER_ID,
        )
    )
    result.files.append(
        text_file(
            "docs/onboarding/BRANCH_POLICY.md",
            render_file(
                "governance/BRANCH_POLICY.md.tmpl",
                dict(common, maintainers=maintainers, approval_text=approval_text, ruleset_path=RULESET),
            ),
            ADAPTER_ID,
        )
    )
    result.files.append(
        text_file(".github/workflows/development-policy.yml", render_file("governance/development-policy.yml.tmpl", {}), ADAPTER_ID)
    )
    result.files.append(text_file(RULESET, _ruleset(profile), ADAPTER_ID))
    result.files.extend(_vendored(profile))
    result.files.append(
        text_file("docs/agents/FIRM_RULES.md", render_file("governance/FIRM_RULES.md.tmpl", {}), ADAPTER_ID, OWNERSHIP_SEED)
    )
    result.files.append(
        text_file("docs/handoffs/INDEX.md", render_file("governance/handoffs-INDEX.md.tmpl", {}), ADAPTER_ID, OWNERSHIP_SEED)
    )

    result.diagnostics.append(
        Diagnostic(
            "governance.ruleset-not-applied",
            "info",
            "governance: " + RULESET,
            "The generated GitHub ruleset is configuration only; it protects nothing until a maintainer applies it to the hosted repository.",
            "See docs/onboarding/BRANCH_POLICY.md, 'Activate server rules'.",
        )
    )
    if governance.approvals_defaulted:
        result.diagnostics.append(
            Diagnostic(
                "governance.approvals-default",
                "info",
                "firm.json#/governance/required_approvals",
                "Using the default of {} required approval(s) for {} maintainer(s).".format(approvals, len(config.maintainers)),
                "Set governance.required_approvals to choose explicitly.",
            )
        )
    return result
