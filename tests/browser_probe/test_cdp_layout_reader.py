"""Layout fixtures are not provider, completion, or screenshot evidence."""

import copy
import json
import unittest
from unittest.mock import patch

from consilium.adapters.cdp_layout_reader import (
    SCOPE,
    CdpLayoutObservation,
    CdpLayoutReader,
    decode_layout_output,
    encode_layout_output,
    selected_layout_text,
)
from consilium.adapters.cdp_process_reader import CdpProcessLayoutReader
from consilium.adapters.cdp_read_only import CdpReadOnlySession, _command

URL = "https://example.test/page"


def fixture():
    return {"strings": ["frame-1", URL, "block", "visible", "1", "visible text", "auto", "hidden", "0", "hidden text", ""],
            "documents": [{"frameId": 0, "documentURL": 1,
                           "nodes": {"parentIndex": [-1, 0, 1, 1, 3, 0],
                                     "backendNodeId": [1, 2, 3, 4, 5, 6]},
                           "layout": {"nodeIndex": [1, 2, 3, 4, 5], "text": [10, 5, 10, 9, 9],
                                      "styles": [[2, 3, 4, 6], [2, 3, 4, 6], [2, 3, 8, 6], [2, 3, 4, 6], [2, 3, 4, 6]],
                                      "bounds": [[0, 0, 100, 20]] * 5}}]}


class LayoutTests(unittest.TestCase):
    def text(self, snapshot=None, **changes):
        return selected_layout_text(snapshot or fixture(), **{
            "backend_node_id": 2, "frame_id": "frame-1", "expected_url": URL, **changes})

    def test_only_selected_nontransparent_layout_text_is_returned(self):
        self.assertEqual(self.text(), "visible text")

    def test_hidden_ancestor_and_zero_bounds_are_excluded(self):
        for style in ([2, 7, 4, 6], [2, 3, 8, 6], [2, 3, 4, 7]):
            s = fixture(); s["documents"][0]["layout"]["styles"][0] = style
            self.assertEqual(self.text(s), "")
        s = fixture(); s["documents"][0]["layout"]["bounds"][0][2] = 0
        self.assertEqual(self.text(s), "")

    def test_foreign_frame_url_or_missing_backend_rejected(self):
        for changes in ({"frame_id": "foreign"}, {"expected_url": URL + "/other"}, {"backend_node_id": 99}):
            with self.assertRaises(ValueError):
                self.text(**changes)

    def test_corrupt_graph_and_layout_arrays_rejected(self):
        for field, bad in [("parentIndex", [-1, 0, 3, 1, 3, 0]),
                           ("backendNodeId", [1, 2, 2, 4, 5, 6])]:
            s = fixture(); s["documents"][0]["nodes"][field] = bad
            with self.assertRaises(ValueError):
                self.text(s)
        for field, bad in [("nodeIndex", [1, 1, 3, 4, 5]), ("text", [5]),
                           ("styles", [[2, 3]] * 5), ("bounds", [[0, 0, float("nan"), 1]] * 5)]:
            s = fixture(); s["documents"][0]["layout"][field] = bad
            with self.assertRaises(ValueError):
                self.text(s)

    def test_snapshot_does_not_mutate_input(self):
        s = fixture(); before = copy.deepcopy(s)
        self.text(s)
        self.assertEqual(s, before)

    def test_real_chromium_document_root_and_absent_text_sentinel(self):
        s = fixture(); layout = s["documents"][0]["layout"]
        layout["nodeIndex"].insert(0, 0)
        layout["text"].insert(0, -1)
        layout["styles"].insert(0, [])
        layout["bounds"].insert(0, [0, 0, 100, 100])
        self.assertEqual(self.text(s), "visible text")
        layout["text"][0] = -2
        with self.assertRaises(ValueError):
            self.text(s)

    def test_oversized_text_rejected(self):
        s = fixture(); s["strings"][5] = "x" * 1048577
        with self.assertRaises(ValueError):
            self.text(s)

    def test_command_allowlist_is_exact(self):
        params = {"computedStyles": ["display", "visibility", "opacity", "content-visibility"],
                  "includeDOMRects": True, "includePaintOrder": False}
        self.assertTrue(_command("DOMSnapshot.captureSnapshot", params))
        for changes in ({"computedStyles": ["color"]}, {"includeDOMRects": 1}, {"extra": True}):
            self.assertFalse(_command("DOMSnapshot.captureSnapshot", {**params, **changes}))
        self.assertTrue(_command("DOM.describeNode", {"nodeId": 1, "depth": 0, "pierce": False}))
        self.assertFalse(_command("DOM.describeNode", {"nodeId": True, "depth": 0, "pierce": False}))
        self.assertFalse(_command("Runtime.evaluate", {"expression": "private"}))

    def test_distinct_wire_preserves_scope_and_binds_selector_and_text(self):
        o = CdpLayoutObservation(URL, "tab-1", "frame-1", "doc-1", 2, "visible text")
        raw = encode_layout_output(o, selector="#answer")
        self.assertEqual(decode_layout_output(raw, selector="#answer"), o)
        self.assertEqual(o.scope, SCOPE)
        for key, bad in [("kind", "CDP_RAW_DOM_V1"), ("text_sha256", "0" * 64)]:
            v = json.loads(raw); v[key] = bad
            with self.assertRaisesRegex(ValueError, "CDP_LAYOUT_OUTPUT_INVALID"):
                decode_layout_output(json.dumps(v).encode(), selector="#answer")
        with self.assertRaises(ValueError):
            decode_layout_output(raw, selector="#other")

    def test_wire_private_invalid_input_and_duplicate_keys(self):
        for raw in (b'"private"', b'{"kind":1,"kind":2}', b"x" * (2 * 1048576 + 1)):
            with self.assertRaisesRegex(ValueError, "^CDP_LAYOUT_OUTPUT_INVALID$") as caught:
                decode_layout_output(raw, selector="#answer")
            self.assertIsNone(caught.exception.__context__)

    def test_owned_process_uses_fixed_layout_command_and_cleans_config(self):
        config = {"endpoint": "ws://127.0.0.1:9222/devtools/page/tab-1", "target_id": "tab-1",
                  "expected_url": URL, "selector": "#answer", "timeout_seconds": 10}
        o = CdpLayoutObservation(URL, "tab-1", "frame-1", "doc-1", 2, "visible")
        raw = encode_layout_output(o, selector="#answer")
        def run(process):
            self.assertEqual(process.command[2], "consilium.shell.cdp_layout_read")
            return raw
        with patch("consilium.adapters.cdp_process_reader.BoundedReadProcess.run", run):
            self.assertEqual(CdpProcessLayoutReader(**config)(), o)

    def test_reader_rejects_ambiguous_selection_and_poisoned_surface(self):
        session = CdpReadOnlySession("ws://127.0.0.1:9222/devtools/page/tab-1", lambda *_: None)
        reader = CdpLayoutReader(session, target_id="tab-1", expected_url=URL, selector="#answer")
        answers = [{"targetInfo": {"targetId": "tab-1", "type": "page", "url": URL}},
                   {"frameTree": {"frame": {"id": "frame-1", "loaderId": "doc-1", "url": URL}}},
                   {"root": {"nodeId": 1}}, {"nodeIds": [2, 3]}]
        with patch.object(session, "read", side_effect=answers), self.assertRaisesRegex(ValueError, "CDP_LAYOUT_READ_FAILED"):
            reader()
        self.assertTrue(session.closed)
