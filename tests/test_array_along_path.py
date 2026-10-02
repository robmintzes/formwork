"""Generator, preview math and transaction regression checks without a Revit host."""
from __future__ import annotations

import ast
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

from formwork_engine.adapters import array_along_path
from formwork_engine.checks import check_outputs
from formwork_engine.diagnostics import Diagnostics
from formwork_engine.profile import load_profile
from formwork_engine.workspace import init_workspace, render_workspace
from validators.check_bundle_structure import validate_bundle_structure
from validators.validate_toolbar_spec import validate_toolbar_spec

ROOT = Path(__file__).resolve().parents[1]


def profile(name):
    diags = Diagnostics()
    loaded = load_profile(ROOT / "profiles" / name, diags)
    assert loaded is not None and not diags.has_errors
    return loaded


def source(name):
    return (ROOT / "formwork_engine/templates/array_along_path" / (name + ".tmpl")).read_text(encoding="utf-8")


def plan_module():
    module = types.ModuleType("array_plan")
    exec(source("plan.py").replace("{{ author_literal }}", '"Test Firm"'), module.__dict__)
    return module


class PlanTests(unittest.TestCase):
    def test_success_description_is_user_readable_and_keeps_run_evidence(self):
        settings = {"mode":"count", "value":19, "offset":2.5, "align":True,
                    "preserve":True, "rot_jit":91, "pos_jit":2, "seed":59071}
        summary, lines = plan_module().result_description("Furniture - Standard",19,1,settings,112.53)
        self.assertEqual(summary,"19 copies placed along 112.53 ft")
        for expected in ("Path length: 112.53 ft", "Distribution: 19 copies, evenly spaced",
                         "Side offset: 2.50 ft", "Follow path tangent: On", "Keep source offset: On",
                         "Copies placed: 19", "Skipped on top of the source: 1"):
            self.assertIn(expected,lines)
        self.assertNotIn("rot_jit", "\n".join(lines))
        self.assertNotIn("Settings:", "\n".join(lines))
        settings.update(mode="distance", value=5)
        self.assertIn("Distribution: 5.00 ft spacing",plan_module().result_description("Chair",22,0,settings,112.53)[1])
    def test_rejects_bad_payloads_and_accepts_boundary(self):
        validate = plan_module().validate_plan
        row = {"x": 0, "y": 2, "z": 0, "rot_delta": 0, "station": 1}
        self.assertEqual(len(validate([row] * 2000)), 2000)
        for payload in (None, [], [row] * 2001, [None], [dict(row, x=float("nan"))],
                        [dict(row, z=float("inf"))], [dict(row, x=True)],
                        [dict(row, x="1")], [dict(row, station=-1)], [dict(row, rot_delta=361)]):
            with self.subTest(payload=str(payload)[:60]), self.assertRaises(ValueError):
                validate(payload)
        cleaned = validate([row])
        row["x"] = 10
        self.assertEqual(cleaned[0]["x"], 0)  # Snapshot, not a mutable client reference.


class GenerationTests(unittest.TestCase):
    def test_both_profiles_generate_valid_neutral_outputs(self):
        for name in ("bimxbert", "quillmoor"):
            with self.subTest(profile=name):
                loaded = profile(name)
                files = array_along_path.render(loaded).files
                diags = Diagnostics()
                check_outputs(files, diags)
                self.assertFalse(diags.has_errors, diags.items)
                content = "\n".join(f.content.decode("utf-8") for f in files if f.text)
                for forbidden in ("rgdt", "Rockwell", "D:\\design-technology", "IvyPresto", "Proxima Nova"):
                    self.assertNotIn(forbidden, content)
                page = next(f.content.decode() for f in files if f.path.endswith("/tool.html"))
                self.assertNotIn("onerror=", page)
                self.assertNotIn("<style>", page)
                self.assertNotIn("<script>", page)
                self.assertIn("connect-src 'none'", page)

    def test_workspace_spec_and_repeat_render(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "Workspace"
            self.assertEqual(init_workspace(ROOT / "profiles/bimxbert", workspace)["summary"]["outcome"], "pass")
            report = render_workspace(workspace)
            self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
            self.assertFalse(validate_bundle_structure(workspace)[0])
            self.assertFalse(validate_toolbar_spec(workspace)[1])
            rerun = render_workspace(workspace)
            self.assertEqual(rerun["summary"]["changes"], 0)
            manifest = json.loads((workspace / ".formwork/manifest.json").read_text())
            folder = array_along_path.button_dir(profile("bimxbert"))
            self.assertEqual(manifest["files"][folder + "/script.py"]["adapter"], "array-along-path")
            # A write-capable ribbon tool must coexist with the read-only MCP bridge.
            tests = workspace / "extensions/BIMxBert.extension/tests"
            command = [sys.executable, "-m", "unittest", "discover", "-s", str(tests), "-q"]
            run = subprocess.run(command, cwd=workspace, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            bridge = workspace / "extensions/BIMxBert.extension/lib/revit_mcp_bridge/response.py"
            bridge.write_text(bridge.read_text(encoding="utf-8") + '\ndef forbidden_write(doc):\n    return DB.Transaction(doc, "Write")\n', encoding="utf-8")
            rejected = subprocess.run(command + ["-k", "test_bridge_never_opens_a_revit_transaction"],
                                      cwd=workspace, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("response.py", rejected.stderr)

    def test_missing_web_host_dependency_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            firm = Path(directory) / "firm"
            shutil.copytree(ROOT / "profiles/bimxbert", firm)
            data = json.loads((firm / "firm.json").read_text())
            data["surfaces"].remove("web-host")
            (firm / "firm.json").write_text(json.dumps(data))
            diags = Diagnostics()
            self.assertIsNone(load_profile(firm, diags))
            self.assertTrue(diags.has_errors)

    @unittest.skipUnless(shutil.which("node"), "Node required for preview math")
    def test_preview_seed_spacing_count_cap_and_anchor_exclusion(self):
        script = source("tool.js")
        # Execute the exact production math without DOM/rendering or the boot.
        begin = script.index("var S =")
        end = script.index("/* ================================================================\n   Rendering")
        math_code = script[begin:end]
        harness = r'''
const assert = require('node:assert/strict');
const fields = {
  'mode-count': {checked: false}, 'in-spacing': {value: '5'}, 'in-offset': {value:'0'},
  'chk-align': {checked:true}, 'chk-preserve': {checked:false},
  'in-rotjit': {value:'0'}, 'in-posjit': {value:'0'}
};
const document = {getElementById: id => fields[id]};
'''+math_code+r'''
S.path = [[0,0,0],[20,0,0]]; S.source={anchor:[0,0,0],offset_vector:[0,2,0]}; buildCumdist();
computePlacements(); assert.deepEqual(S.placements.map(p=>p.x),[5,10,15,20]);
fields['mode-count'].checked=true; fields['in-spacing'].value='3'; computePlacements();
assert.equal(S.placements.length,3);
S.placements.forEach((p,i)=>assert.ok(Math.abs(p.x-(i+1)*20/3)<1e-9));
fields['in-spacing'].value='1'; computePlacements();
assert.deepEqual(S.placements.map(p=>p.x),[20]);
fields['in-spacing'].value='2000'; computePlacements();
assert.equal(S.placements.length,2000);
fields['in-spacing'].value='3';
fields['in-offset'].value='4.5'; computePlacements();
assert.equal(S.placements.length,3);
assert.deepEqual(S.placements.map(p=>p.x),[0,10,20]);
assert.ok(S.placements.every(p=>p.y===4.5));
assert.equal(S.skippedAtSource,0);
fields['mode-count'].checked=false; fields['in-spacing'].value='10'; computePlacements();
const spacedOffset=JSON.stringify(S.placements);
fields['mode-count'].checked=true; fields['in-spacing'].value='3'; computePlacements();
assert.equal(JSON.stringify(S.placements),spacedOffset);
fields['in-offset'].value='0';
fields['chk-preserve'].checked=true; fields['in-rotjit'].value='30'; fields['in-posjit'].value='2';
S.seed=42; computePlacements(); const first=JSON.stringify(S.placements); computePlacements();
assert.equal(JSON.stringify(S.placements),first); S.seed=43; computePlacements();
assert.notEqual(JSON.stringify(S.placements),first);
S.path=[[0,0,0],[5000,0,0]]; buildCumdist(); fields['mode-count'].checked=false;
fields['in-spacing'].value='0.5'; assert.equal(computePlacements().capped,true);
assert.ok(S.placements.length<=2000);
console.log('Preview math passed');
'''
        result = subprocess.run(["node", "-e", harness], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TransactionTests(unittest.TestCase):
    def execute(self, commit="Committed", fail_at=None):
        tree = ast.parse(source("script.py").replace("{{ author_literal }}", '"Test Firm"')
                         .replace("{{ package }}", "test_web").replace("{{ ui_package }}", "test_ui")
                         .replace("{{ ns }}", "test"))
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "place_copies")
        events = []
        class Vector:
            def __init__(self, x, y, z): self.x, self.y, self.z = x,y,z
            def __sub__(self, other): return Vector(self.x-other.x,self.y-other.y,self.z-other.z)
            def GetLength(self): return math.sqrt(self.x**2+self.y**2+self.z**2)
        class Options:
            def SetFailuresPreprocessor(self, x): pass
            def SetClearAfterRollback(self, x): pass
            def SetForcedModalHandling(self, x): pass
        class Tx:
            def __init__(self, *args): self.started=False; self.ended=False
            def Start(self): self.started=True; events.append("start"); return "Started"
            def Commit(self): self.ended=commit=="Committed"; events.append("commit"); return commit
            def RollBack(self): self.ended=True; events.append("rollback")
            def HasStarted(self): return self.started
            def HasEnded(self): return self.ended
            def GetFailureHandlingOptions(self): return Options()
            def SetFailureHandlingOptions(self, options): pass
        category = types.SimpleNamespace(Id=1)
        element = types.SimpleNamespace(Id=1, GetType=lambda:"Family", GetTypeId=lambda:42, Category=category)
        def copy(doc, eid, movement):
            events.append("copy")
            if fail_at and events.count("copy")==fail_at: raise RuntimeError("Copy rejected")
            return [2]
        env = {"validate_plan": plan_module().validate_plan, "Transaction":Tx,
               "TransactionStatus":types.SimpleNamespace(Started="Started",Committed="Committed"),
               "XYZ":Vector,"ANCHOR_SKIP_TOL":0.01,"math":math,"RollbackOnError":lambda:None,
               "ElementTransformUtils":types.SimpleNamespace(CopyElement=copy),
               "eid_int":lambda x:x,"element_label":lambda x:"Source",
               "result_description":plan_module().result_description}
        exec(compile(ast.Module(body=[fn], type_ignores=[]),"transaction","exec"),env)
        rows = [{"x":x,"y":0,"z":0,"station":x,"rot_delta":0} for x in (0,5,10)]
        result = env["place_copies"](types.SimpleNamespace(GetElement=lambda eid:element),element,
                                    Vector(0,0,0),Vector(0,0,1),{"placements":rows,"settings":{}})
        return result, events

    def test_commits_once_and_excludes_anchor(self):
        result, events = self.execute()
        self.assertEqual(result["counts"], {"ok":2,"warn":1,"fail":0})
        self.assertEqual(events,["start","copy","copy","commit"])

    def test_copy_failure_rolls_back_all_and_reports_zero_success(self):
        result, events = self.execute(fail_at=2)
        self.assertEqual(events[-1],"rollback")
        self.assertEqual(result["status"],"failed")
        self.assertEqual(result["counts"]["ok"],0)
        self.assertEqual(result["items"],[])

    def test_non_committed_status_is_never_success(self):
        result, events = self.execute(commit="RolledBack")
        self.assertEqual(result["status"],"failed")
        self.assertEqual(result["counts"]["ok"],0)

    def test_browser_callback_submits_only_and_main_writes_after_show(self):
        text = source("script.py")
        callback = text[text.index("    def execute("):text.index("def place_copies")]
        self.assertNotIn("Transaction(",callback)
        self.assertNotIn("CopyElement",callback)
        self.assertLess(text.index("win.show()"),text.index("show_result(place_copies("))


if __name__ == "__main__":
    unittest.main()
