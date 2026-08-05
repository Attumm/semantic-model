"""Tests for the model-validation error paths and the JSON/CLI entry points.

These harden the "validate the model" feature: the engine raises
:class:`semantic_model.InvalidModel` for the various ways a DSM model can be
malformed, and the JSON-file helpers (the path real users take) must behave the
same as their in-memory counterparts.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from semantic_model import (
    BaseDSMException,
    InvalidModel,
    json_,
    pjson,
    run_detail,
    run_detail_json,
    run_list_json,
    run_node_json,
    run_semantic_list_model,
    run_semantic_model,
    run_semantic_nodes_model,
    run_with_json,
    tofile,
)

SIMPLE_MODEL = {
    "type": "dict",
    "nested": {
        "name": {
            "type": "string",
            "source": {"type": "json_key_item", "source": "input", "dn": "NAME"},
        },
    },
}
SIMPLE_INPUT = {"NAME": "Bob"}


def _write(tmpdir, name, obj):
    path = os.path.join(tmpdir, name)
    with open(path, "w") as f:
        json.dump(obj, f)
    return path


class TestExceptionContract(unittest.TestCase):
    def test_base_dsm_exception_is_exception(self):
        self.assertTrue(issubclass(BaseDSMException, Exception))

    def test_invalid_model_is_base_dsm_exception(self):
        self.assertTrue(issubclass(InvalidModel, BaseDSMException))

    def test_invalid_model_is_exception(self):
        self.assertTrue(issubclass(InvalidModel, Exception))


class TestValidationErrors(unittest.TestCase):
    """Every malformed-model case the engine must reject with InvalidModel."""

    def test_missing_type(self):
        with self.assertRaises(InvalidModel):
            run_detail({"source": {"type": "json_key"}}, input={})

    def test_missing_source_on_leaf(self):
        with self.assertRaises(InvalidModel):
            run_detail({"type": "string"}, input={})

    def test_missing_source_type(self):
        with self.assertRaises(InvalidModel):
            run_detail({"type": "string", "source": {}}, input={})

    def test_unknown_source_type(self):
        with self.assertRaises(InvalidModel):
            run_detail(
                {
                    "type": "string",
                    "source": {"type": "bogus", "source": "input", "dn": "x"},
                },
                input={},
            )

    def test_unknown_postformat(self):
        with self.assertRaises(InvalidModel):
            run_detail(
                {
                    "type": "string",
                    "source": {
                        "type": "json_key_item",
                        "source": "input",
                        "dn": "x",
                        "postformat": {"type": "bogus"},
                    },
                },
                input={"x": "v"},
            )

    def test_json_key_item_missing_key_without_default_raises(self):
        # the strict variant of json_key: no value and no default -> InvalidModel
        with self.assertRaises(InvalidModel):
            run_detail(
                {
                    "type": "string",
                    "source": {
                        "type": "json_key_item",
                        "source": "input",
                        "dn": "missing",
                    },
                },
                input={},
            )

    def test_json_key_item_missing_key_with_default_returns_default(self):
        result = run_detail(
            {
                "type": "string",
                "source": {
                    "type": "json_key_item",
                    "source": "input",
                    "dn": "missing",
                    "default": "D",
                },
            },
            input={},
        )
        self.assertEqual(result, "D")

    def test_get_from_source_missing_dn_raises(self):
        with self.assertRaises(InvalidModel):
            run_detail(
                {
                    "type": "string",
                    "source": {"type": "get_from_source", "source": "input"},
                },
                input={},
            )

    def test_error_message_mentions_dn(self):
        try:
            run_detail({"type": "string"}, input={})
        except InvalidModel as e:
            self.assertIn("dn", str(e).lower())
        else:
            self.fail("expected InvalidModel")


class TestJsonEntryPoints(unittest.TestCase):
    """The file-loading entry points must match the in-memory run_* calls."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.model_path = _write(self.tmp, "m.json", SIMPLE_MODEL)
        self.input_path = _write(self.tmp, "i.json", SIMPLE_INPUT)

    def test_run_with_json_detail(self):
        self.assertEqual(
            run_with_json("detail", self.model_path, input=self.input_path),
            {"name": "Bob"},
        )

    def test_run_with_json_unknown_action_raises(self):
        with self.assertRaises(ValueError):
            run_with_json("bogus", self.model_path, input=self.input_path)

    def test_run_detail_json_matches_run_detail(self):
        self.assertEqual(
            run_detail_json(self.model_path, input=self.input_path),
            run_detail(SIMPLE_MODEL, input=SIMPLE_INPUT),
        )

    def test_run_list_json_returns_rows(self):
        rows = list(run_list_json(self.model_path, input=self.input_path))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"], "Bob")

    def test_run_node_json_returns_rows(self):
        rows = list(run_node_json(self.model_path, input=self.input_path))
        self.assertEqual(len(rows), 1)

    def test_run_semantic_model_alias(self):
        self.assertEqual(
            run_semantic_model(self.model_path, self.input_path), {"name": "Bob"}
        )

    def test_run_semantic_list_model_alias(self):
        self.assertEqual(
            len(list(run_semantic_list_model(self.model_path, self.input_path))), 1
        )

    def test_run_semantic_nodes_model_alias(self):
        self.assertEqual(
            len(list(run_semantic_nodes_model(self.model_path, self.input_path))), 1
        )


class TestOutputHelpers(unittest.TestCase):
    def test_pjson_prints_indented_json(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pjson({"a": 1})
        self.assertIn('"a": 1', buf.getvalue())
        self.assertIn("\n", buf.getvalue())  # indented -> multi-line

    def test_json_prints_compact_json(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            json_({"a": 1})
        self.assertEqual(buf.getvalue().strip(), '{"a": 1}')

    def test_pjson_none_is_noop(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pjson(None)
        self.assertEqual(buf.getvalue(), "")

    def test_tofile_writes_output_json(self):
        cwd = os.getcwd()
        out = os.path.join(cwd, "output.json")
        try:
            if os.path.exists(out):
                os.remove(out)
            tofile({"a": 1})
            self.assertTrue(os.path.exists(out))
            with open(out) as f:
                self.assertEqual(json.load(f), {"a": 1})
        finally:
            if os.path.exists(out):
                os.remove(out)

    def test_tofile_none_is_noop(self):
        cwd = os.getcwd()
        out = os.path.join(cwd, "output.json")
        existed = os.path.exists(out)
        try:
            tofile(None)
            if not existed:
                self.assertFalse(os.path.exists(out))
        finally:
            pass


if __name__ == "__main__":
    unittest.main()
