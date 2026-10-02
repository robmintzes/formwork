"""Lifecycle and viewport docking checks without showing a Revit window."""
import ast
from pathlib import Path
import types
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "formwork_engine/templates/ui_kit/selection_guide.py.tmpl"


def definitions(names, env):
    text = SOURCE.read_text(encoding="utf-8").replace("{{ ns }}", "Test")
    text = text.replace("{{ package }}", "test_ui").replace("{{ author_literal }}", '"Test Firm"')
    tree = ast.parse(text)
    nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "guide", "exec"), env)
    return env


class GuideLifetime(unittest.TestCase):
    def environment(self):
        events = []
        class Banner:
            def set_step(self, *args): events.append(("step",args))
            def Show(self): events.append(("show",))
            def Close(self): events.append(("close",))
        def factory(uidoc): events.append(("create",)); return Banner()
        env = definitions(["SelectionGuide"], {"create_banner":factory,
            "bootstrap":types.SimpleNamespace(badge_text=lambda x:x),
            "revit":types.SimpleNamespace(uidoc="active"),
            "LOGGER":types.SimpleNamespace(warning=lambda message:None)})
        return env["SelectionGuide"], events

    def test_steps_show_once_close_and_preserve_finish_cancel_guidance(self):
        Guide, events = self.environment()
        with Guide("Array Along Path",2) as guide:
            guide.step(1,"Select the path curves",multi=True)
            guide.step(2,"Select the source")
        self.assertEqual([e[0] for e in events],["create","step","show","step","close"])
        self.assertIn("Click Finish",events[1][1][2])
        self.assertIn("Esc to cancel",events[3][1][2])
        self.assertIn("Step 2 of 2",events[3][1][0])

    def test_escape_or_tool_error_closes_banner_without_swallowing_exception(self):
        Guide, events = self.environment()
        with self.assertRaisesRegex(RuntimeError,"canceled"):
            with Guide("Tool") as guide:
                guide.step(1,"Pick")
                raise RuntimeError("canceled")
        self.assertEqual(events[-1],("close",))

    def test_preselection_without_pick_does_not_flash_an_empty_banner(self):
        Guide, events = self.environment()
        with Guide("Tool"):
            pass
        self.assertEqual(events,[])

    def test_brand_failure_uses_stock_guidance_and_total_failure_keeps_native_prompt(self):
        def broken(*args): raise RuntimeError("unavailable")
        fallback = object()
        env = definitions(["create_banner"], {"SelectionBanner":broken,
            "WarningGuide":lambda:fallback, "LOGGER":types.SimpleNamespace(warning=lambda x:None)})
        self.assertIs(env["create_banner"]("doc"),fallback)
        env["WarningGuide"] = broken
        self.assertIsNone(env["create_banner"]("doc"))


class GuideDocking(unittest.TestCase):
    def test_uses_active_view_rect_including_negative_monitor_coordinates_and_dpi(self):
        class Prompt:
            def update_window(self): self.stock=True
        rect = types.SimpleNamespace(Top=-200,Left=-2400,Right=0)
        views = [types.SimpleNamespace(ViewId=n,GetWindowRectangle=lambda:rect) for n in (1,2)]
        env = definitions(["SelectionBanner"], {"_PromptBar":Prompt,
            "forms":types.SimpleNamespace(TemplatePromptBar=Prompt),
            "HOST_APP":types.SimpleNamespace(proc_screen_scalefactor=1.5)})
        banner = env["SelectionBanner"].__new__(env["SelectionBanner"])
        banner.user_height = 56
        banner._uidoc = types.SimpleNamespace(ActiveView=types.SimpleNamespace(Id=2),GetOpenUIViews=lambda:views)
        banner.update_window()
        self.assertAlmostEqual(banner.Top,-200/1.5)
        self.assertEqual(banner.Left,-1600)
        self.assertEqual(banner.Width,1600)
        self.assertEqual(banner.Height,56)
        banner._uidoc.ActiveView.Id = 3
        banner.update_window()
        self.assertTrue(banner.stock)


if __name__ == "__main__":
    unittest.main()
