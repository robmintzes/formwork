from __future__ import annotations

import ast
import importlib
import importlib.util
import io
import json
import runpy
import sys
import tempfile
import tokenize
import types
import unittest
from pathlib import Path


EXTENSION_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PACKAGE = "revit_mcp_bridge"
MCP_ROOT = EXTENSION_ROOT / "lib" / BRIDGE_PACKAGE
HELLO_SCRIPT = (
    EXTENSION_ROOT
    / "PlaceholderTab.tab"
    / "PlaceholderPanel.panel"
    / "HelloButton.pushbutton"
    / "script.py"
)


def _load_file(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _static_python2_issues(source, label):
    """Flag common Python 3 syntax that the IronPython 2 parser rejects.

    This is deliberately a conservative static guard, not a replacement for a
    live IronPython compile and Revit test.
    """
    forbidden_node_names = {
        "AnnAssign",
        "AsyncFor",
        "AsyncFunctionDef",
        "AsyncWith",
        "Await",
        "JoinedStr",
        "Match",
        "MatMult",
        "NamedExpr",
        "Nonlocal",
        "TryStar",
        "TypeAlias",
        "YieldFrom",
    }
    issues = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        node_name = type(node).__name__
        if node_name in forbidden_node_names:
            issues.append("{} uses {}".format(label, node_name))

        if isinstance(node, (ast.FunctionDef, ast.Lambda)):
            arguments = node.args
            all_arguments = (
                list(getattr(arguments, "posonlyargs", []))
                + list(arguments.args)
                + list(arguments.kwonlyargs)
            )
            annotated = [
                argument for argument in all_arguments if argument.annotation is not None
            ]
            if (
                annotated
                or getattr(arguments, "posonlyargs", [])
                or arguments.kwonlyargs
            ):
                issues.append(
                    "{} uses annotations, positional-only, or keyword-only arguments".format(
                        label
                    )
                )
            if isinstance(node, ast.FunctionDef) and node.returns is not None:
                issues.append("{} uses a return annotation".format(label))

        if isinstance(node, ast.ClassDef) and node.keywords:
            issues.append("{} uses Python 3 class keywords".format(label))
        if isinstance(node, ast.Dict) and any(key is None for key in node.keys):
            issues.append("{} uses dictionary unpacking".format(label))
        if isinstance(node, (ast.List, ast.Set, ast.Tuple)) and any(
            isinstance(element, ast.Starred) for element in node.elts
        ):
            issues.append("{} uses iterable unpacking in a literal".format(label))
        if isinstance(node, ast.Raise) and node.cause is not None:
            issues.append("{} uses exception chaining".format(label))
        if isinstance(node, ast.comprehension) and node.is_async:
            issues.append("{} uses an async comprehension".format(label))

    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    for token in tokens:
        if token.type == tokenize.NUMBER and "_" in token.string:
            issues.append("{} uses numeric separators".format(label))

    return issues


class ElementIdSerializationTests(unittest.TestCase):
    def setUp(self):
        self.compat = _load_file("template_mcp_compat", MCP_ROOT / "compat.py")

    def test_prefers_current_value_and_returns_builtin_int(self):
        class CurrentElementId(object):
            Value = 4294967297
            IntegerValue = 7

        value = self.compat.element_id_value(CurrentElementId())
        self.assertEqual(4294967297, value)
        self.assertIs(type(value), int)
        self.assertEqual("4294967297", json.dumps(value))

    def test_falls_back_to_legacy_integer_value(self):
        class LegacyElementId(object):
            IntegerValue = 42

        self.assertEqual(42, self.compat.element_id_value(LegacyElementId()))

    def test_none_remains_none(self):
        self.assertIsNone(self.compat.element_id_value(None))


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.saved_mcp_modules = {
            name: module
            for name, module in sys.modules.items()
            if name == BRIDGE_PACKAGE or name.startswith(BRIDGE_PACKAGE + ".")
        }
        for name in list(self.saved_mcp_modules):
            sys.modules.pop(name, None)

        package = types.ModuleType(BRIDGE_PACKAGE)
        package.__path__ = [str(MCP_ROOT)]
        sys.modules[BRIDGE_PACKAGE] = package
        self.dispatch = importlib.import_module(BRIDGE_PACKAGE + ".dispatch")

    def tearDown(self):
        for name in list(sys.modules):
            if name == BRIDGE_PACKAGE or name.startswith(BRIDGE_PACKAGE + "."):
                sys.modules.pop(name, None)
        sys.modules.update(self.saved_mcp_modules)

    def test_registered_operation_calls_literal_handler(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            handler_name = "template_test_handler"
            registry_name = "template_test_registry"
            (temp_path / (handler_name + ".py")).write_text(
                "def run(doc, request):\n    return {'status': 'ok', 'value': 7}\n",
                encoding="utf-8",
            )
            (temp_path / (registry_name + ".py")).write_text(
                "def resolve(op):\n"
                "    if op == 'project/example':\n"
                "        return ('example', 'template_test_handler', 'run', [])\n"
                "    return None\n",
                encoding="utf-8",
            )
            sys.path.insert(0, temp_dir)
            try:
                result = self.dispatch.call_registered(
                    "project/example", None, None, registry_name
                )
            finally:
                sys.path.remove(temp_dir)
                sys.modules.pop(handler_name, None)
                sys.modules.pop(registry_name, None)

        self.assertEqual("ok", result["status"])
        self.assertEqual(7, result["value"])

    def test_unregistered_operation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            registry_name = "template_test_rejecting_registry"
            (temp_path / (registry_name + ".py")).write_text(
                "def resolve(op):\n    return None\n",
                encoding="utf-8",
            )
            sys.path.insert(0, temp_dir)
            try:
                result = self.dispatch.call_registered(
                    "delete/everything", None, None, registry_name
                )
            finally:
                sys.path.remove(temp_dir)
                sys.modules.pop(registry_name, None)

        self.assertEqual("error", result["status"])
        self.assertEqual("operation_not_allowed", result["error"]["code"])


class StaticRuntimeTests(unittest.TestCase):
    def test_hello_button_is_python3_parseable_and_read_only(self):
        source = HELLO_SCRIPT.read_text(encoding="utf-8")
        ast.parse(source)
        transaction_token = "Trans" + "action("
        self.assertNotIn(transaction_token, source)
        self.assertNotIn("from __future__ import annotations", source)
        self.assertIn('__author__ = "Template Author"', source)
        self.assertLess(source.index("if doc is None:"), source.index("forms.alert("))

    def test_extension_runtime_flags_no_common_python3_only_syntax(self):
        issues = []
        for path in sorted(EXTENSION_ROOT.rglob("*.py")):
            if "tests" in path.parts:
                continue
            relative_path = path.relative_to(EXTENSION_ROOT)
            issues.extend(
                _static_python2_issues(
                    path.read_text(encoding="utf-8"), str(relative_path)
                )
            )

        self.assertEqual([], issues)

    def test_static_python2_guard_rejects_representative_python3_syntax(self):
        samples = {
            "dict-unpacking": "value = {**mapping}\n",
            "numeric-separator": "value = 1_000\n",
            "positional-only": "def sample(value, /):\n    return value\n",
        }
        for label, source in samples.items():
            with self.subTest(label=label):
                self.assertTrue(_static_python2_issues(source, label))

    def test_authored_runtime_files_have_rebrandable_metadata(self):
        runtime_files = [EXTENSION_ROOT / "startup.py", HELLO_SCRIPT]
        runtime_files.extend(sorted(MCP_ROOT.glob("*.py")))
        missing = []
        for path in runtime_files:
            source = path.read_text(encoding="utf-8")
            if '__author__ = "Template Author"' not in source:
                missing.append(path.relative_to(EXTENSION_ROOT).as_posix())

        self.assertEqual([], missing)

    def test_project_handlers_reject_family_documents_before_queries(self):
        source = (MCP_ROOT / "handlers_project.py").read_text(encoding="utf-8")
        guard_start = source.index("def _require_doc")
        first_handler = source.index("def get_project_info")
        guard_source = source[guard_start:first_handler]
        self.assertIn("IsFamilyDocument", guard_source)
        self.assertIn("family_document_not_supported", guard_source)

    def test_extension_startup_calls_initializer_without_server_activation(self):
        startup_path = EXTENSION_ROOT / "startup.py"
        source = startup_path.read_text(encoding="utf-8")
        self.assertNotIn("activate_server", source)

        calls = []

        class Logger(object):
            def info(self, message):
                pass

            def warning(self, message):
                pass

        pyrevit = types.ModuleType("pyrevit")
        pyrevit.script = types.SimpleNamespace(get_logger=lambda: Logger())
        package = types.ModuleType(BRIDGE_PACKAGE)
        package.startup = types.SimpleNamespace(init=lambda: calls.append("init"))

        saved = {
            name: sys.modules.get(name) for name in ("pyrevit", BRIDGE_PACKAGE)
        }
        sys.modules["pyrevit"] = pyrevit
        sys.modules[BRIDGE_PACKAGE] = package
        try:
            runpy.run_path(str(startup_path), run_name="template_startup_test")
        finally:
            for name, module in saved.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        self.assertEqual(["init"], calls)


if __name__ == "__main__":
    unittest.main()
