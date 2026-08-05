"""Tests for engine helpers, postformats, RBAC metadata and the one_to_one
type-detection primitives — plus regression guards for the DN tuple/list
contract.

These cover the "small, pure" building blocks the engine composes, locking
their behavior so refactors stay safe.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from one_to_one import (
    CONFIG,
    create_dn,
    create_dn_list,
    get_all_uniq_keys,
    get_description,
    identify,
    str_type,
)
from semantic_model import (
    create_meta_data_list,
    create_uuid5,
    default_postformat,
    format_dict_to_key_list,
    get_by_dn,
    get_index_num_from_list_dn,
    has_list_item_config,
    has_read_rights,
    int_to_iso_timestamp,
    is_list_dn,
    is_node,
    list_item_config,
    new_dn,
    rbac_views,
    regex_search,
    regex_to_iso_timestamp,
    remove_list_item,
    run_detail,
    run_nodes,
    update_views_to_rbac,
    yield_by_dn,
)


class TestDnHelpers(unittest.TestCase):
    def test_new_dn_appends_key(self):
        self.assertEqual(new_dn(("a",), "b"), ("a", "b"))

    def test_new_dn_empty(self):
        self.assertEqual(new_dn((), "x"), ("x",))

    def test_new_dn_does_not_mutate_input(self):
        original = ("a",)
        new_dn(original, "b")
        self.assertEqual(original, ("a",))

    def test_is_list_dn(self):
        self.assertTrue(is_list_dn("[0]"))
        self.assertTrue(is_list_dn("[]"))
        self.assertFalse(is_list_dn("name"))
        self.assertFalse(is_list_dn("[0"))

    def test_get_index_num_from_list_dn(self):
        self.assertEqual(get_index_num_from_list_dn("[5]"), 5)
        self.assertEqual(get_index_num_from_list_dn("[]"), 0)

    def test_get_by_dn_resolves_dot_path(self):
        data = {"a": {"b": 1}}
        self.assertEqual(get_by_dn(data, "a.b"), (True, 1))

    def test_get_by_dn_list_index(self):
        data = {"a": {"b": [10, 20, 30]}}
        self.assertEqual(get_by_dn(data, "a.b.[0]"), (True, 10))
        self.assertEqual(get_by_dn(data, "a.b.[2]"), (True, 30))

    def test_get_by_dn_missing_returns_empty(self):
        data = {"a": {"b": 1}}
        # missing intermediate returns the default ({}) with found=True
        found, value = get_by_dn(data, "x.y")
        self.assertTrue(found)
        self.assertEqual(value, {})

    def test_get_by_dn_out_of_bound(self):
        data = {"a": {"b": [1]}}
        found, value = get_by_dn(data, "a.b.[9]")
        self.assertFalse(found)

    def test_yield_by_dn_found(self):
        self.assertEqual(list(yield_by_dn({"a": [1, 2, 3]}, "a")), [1, 2, 3])

    def test_yield_by_dn_not_found_empty(self):
        self.assertEqual(list(yield_by_dn({"a": [1]}, "x")), [])


class TestRbac(unittest.TestCase):
    def test_no_roles_is_open(self):
        self.assertTrue(has_read_rights({"rbac": {"a": {"read": True}}}, None))

    def test_matching_role_reads(self):
        self.assertTrue(has_read_rights({"rbac": {"admin": {"read": True}}}, ["admin"]))

    def test_non_matching_role_cannot_read(self):
        self.assertFalse(
            has_read_rights({"rbac": {"admin": {"read": True}}}, ["guest"])
        )

    def test_role_without_read_right_cannot_read(self):
        model = {"rbac": {"admin": {"read": False, "create": True}}}
        self.assertFalse(has_read_rights(model, ["admin"]))

    def test_rbac_views_grants_all_rights(self):
        self.assertEqual(
            rbac_views(["admin", "user"]),
            {
                "admin": {"read": True, "update": True, "create": True, "delete": True},
                "user": {"read": True, "update": True, "create": True, "delete": True},
            },
        )

    def test_update_views_to_rbac_converts_views(self):
        model = {"type": "string", "views": ["admin"]}
        update_views_to_rbac(model, ())
        self.assertNotIn("views", model)
        self.assertEqual(model["rbac"], rbac_views(["admin"]))

    def test_update_views_to_rbac_noop_without_views(self):
        model = {"type": "string"}
        update_views_to_rbac(model, ())
        self.assertNotIn("rbac", model)


class TestNodeMetadata(unittest.TestCase):
    """create_meta_data_list drives the node action's per-column metadata."""

    def test_basic_metadata(self):
        model = {"type": "string"}
        meta = create_meta_data_list(model, ("p", "name"), "name", "Bob")
        self.assertEqual(meta["name"], "Bob")
        self.assertEqual(meta["_name_dn"], ["p", "name"])
        self.assertEqual(meta["_name_type"], "string")

    def test_node_dn_is_list_not_tuple(self):
        # regression guard: node rows must emit list DNs (not tuples)
        meta = create_meta_data_list({"type": "string"}, ("a", "b"), "x", 1)
        self.assertIsInstance(meta["_x_dn"], list)

    def test_field_type_and_description(self):
        model = {"type": "string", "field_type": "text", "description": "a name"}
        meta = create_meta_data_list(model, ("p", "name"), "name", "Bob")
        self.assertEqual(meta["_name_field_type"], "text")
        self.assertEqual(meta["_name_description"], "a name")

    def test_rbac_lists_per_action(self):
        model = {
            "type": "string",
            "rbac": {
                "admin": {
                    "read": True,
                    "create": True,
                    "update": False,
                    "delete": False,
                },
                "user": {"read": True},
            },
        }
        meta = create_meta_data_list(model, ("p", "name"), "name", "Bob")
        self.assertEqual(meta["_name_rbac_read"], ["admin", "user"])
        self.assertEqual(meta["_name_rbac_create"], ["admin"])
        self.assertEqual(meta["_name_rbac_update"], [])
        self.assertEqual(meta["_name_rbac_delete"], [])

    def test_no_rbac_keys_when_absent(self):
        model = {"type": "string"}
        meta = create_meta_data_list(model, ("p", "name"), "name", "Bob")
        self.assertNotIn("_name_rbac_read", meta)


class TestIsNodeAndListItemConfig(unittest.TestCase):
    def test_is_node_dict_with_only_leaves(self):
        model = {
            "type": "dict",
            "nested": {"a": {"type": "string"}, "b": {"type": "integer"}},
        }
        self.assertTrue(is_node(model))

    def test_is_node_false_when_nested_child(self):
        model = {
            "type": "dict",
            "nested": {"a": {"type": "dict", "nested": {"x": {"type": "string"}}}},
        }
        self.assertFalse(is_node(model))

    def test_list_item_config_returns_list_item_when_present(self):
        model = {"type": "string", "list_item": {"x": 1}}
        self.assertEqual(list_item_config(model, ()), {"x": 1})

    def test_list_item_config_falls_back_to_model(self):
        model = {"type": "string"}
        self.assertIs(list_item_config(model, ()), model)

    def test_has_list_item_config_standard(self):
        self.assertTrue(
            has_list_item_config({"nested": {"standard": {"type": "string"}}})
        )

    def test_has_list_item_config_common(self):
        self.assertTrue(
            has_list_item_config({"nested": {"common": {"type": "string"}}})
        )

    def test_has_list_item_config_absent(self):
        self.assertFalse(has_list_item_config({"nested": {"x": {"type": "string"}}}))
        self.assertFalse(has_list_item_config({}))


class TestRemoveListItem(unittest.TestCase):
    def test_removes_list_item(self):
        model = {"type": "string", "list_item": {"x": 1}}
        remove_list_item(model, ())
        self.assertNotIn("list_item", model)

    def test_promotes_validators_to_field_type(self):
        model = {"type": "string", "validators": "text"}
        remove_list_item(model, ())
        self.assertNotIn("validators", model)
        self.assertEqual(model["field_type"], "text")

    def test_noop_when_neither_present(self):
        model = {"type": "string"}
        remove_list_item(model, ())
        self.assertEqual(model, {"type": "string"})


class TestPostformats(unittest.TestCase):
    def test_default_postformat_is_identity(self):
        self.assertEqual(default_postformat("anything"), "anything")

    def test_int_to_iso_timestamp(self):
        # 2023-11-14T22:13:20Z
        result = int_to_iso_timestamp("1700000000000")
        self.assertTrue(result.startswith("2023-11-14T22:13:20"))

    def test_int_to_iso_timestamp_accepts_int(self):
        result = int_to_iso_timestamp(1700000000000)
        self.assertTrue(str(result).startswith("2023"))

    def test_int_to_iso_timestamp_raises_on_garbage(self):
        with self.assertRaises((ValueError, TypeError)):
            int_to_iso_timestamp("notanumber")

    def test_int_to_iso_timestamp_fail_silent(self):
        self.assertEqual(
            int_to_iso_timestamp("notanumber", **{"fail-silent": True}), "notanumber"
        )

    def test_regex_to_iso_timestamp(self):
        result = regex_to_iso_timestamp("20200629_105645", format="%Y%m%d_%H%M%S")
        self.assertEqual(result, "2020-06-29T10:56:45")

    def test_regex_search_match(self):
        self.assertEqual(regex_search("apple_21", regex=r"(\d+)"), "21")

    def test_regex_search_no_match_returns_default(self):
        self.assertEqual(regex_search("apple", regex=r"(\d+)", default="NaN"), "NaN")

    def test_regex_search_no_match_no_default(self):
        self.assertIsNone(regex_search("apple", regex=r"(\d+)"))

    def test_create_uuid5_is_deterministic(self):
        self.assertEqual(create_uuid5("domain", "id1"), create_uuid5("domain", "id1"))

    def test_create_uuid5_differs_for_different_inputs(self):
        self.assertNotEqual(
            create_uuid5("domain", "id1"), create_uuid5("domain", "id2")
        )

    def test_format_dict_to_key_list(self):
        self.assertEqual(format_dict_to_key_list({"a": 1, "b": 2}), ["a", "b"])


class TestNodeDnContract(unittest.TestCase):
    """End-to-end regression guard: run_nodes emits list DNs (not tuples)."""

    def test_run_nodes_dn_is_list(self):
        model = {
            "type": "dict",
            "nested": {
                "person": {
                    "type": "dict",
                    "nested": {
                        "name": {
                            "type": "string",
                            "source": {
                                "type": "json_key_item",
                                "source": "input",
                                "dn": "NAME",
                            },
                        },
                    },
                },
            },
        }
        rows = list(run_nodes(model, input={"NAME": "Bob"}))
        self.assertEqual(len(rows), 1)
        row = rows[0]  # type: ignore[assignment]
        self.assertEqual(row["_dn"], ["person"])  # type: ignore[index]
        self.assertEqual(row["_name_dn"], ["person", "name"])  # type: ignore[index]


class TestOneToOnePrimitives(unittest.TestCase):
    def setUp(self):
        CONFIG.clear()

    def tearDown(self):
        CONFIG.clear()

    def test_identify_email(self):
        self.assertEqual(identify("bob@example.com"), "Email Address")

    def test_identify_ipv4(self):
        self.assertEqual(
            identify("172.0.0.1"), "Internet Protocol (IP) Address Version 4"
        )

    def test_identify_url(self):
        self.assertEqual(
            identify("https://example.com"), "Uniform Resource Locator (URL)"
        )

    def test_identify_phone(self):
        self.assertEqual(identify("+1 555 123 4567"), "Phone Number")

    def test_identify_no_match_returns_empty(self):
        self.assertEqual(identify("definitely_not_a_known_type_xyz"), "")

    def test_str_type_none(self):
        self.assertEqual(str_type(None), "str")

    def test_str_type_str(self):
        self.assertEqual(str_type("hi"), "str")

    def test_str_type_int(self):
        self.assertEqual(str_type(5), "int")

    def test_str_type_list(self):
        self.assertEqual(str_type([1, 2]), "list")

    def test_str_type_dict(self):
        self.assertEqual(str_type({}), "dict")

    def test_get_description_returns_text(self):
        desc = get_description("Email Address")
        self.assertIsInstance(desc, str)
        self.assertTrue(len(desc) > 10)

    def test_get_description_unknown_returns_empty(self):
        self.assertEqual(get_description("not a real type name"), "")

    def test_get_description_skip_flag(self):
        CONFIG["skip_description"] = True
        self.assertEqual(get_description("Email Address"), "")

    def test_create_dn_root(self):
        self.assertEqual(create_dn("", "name"), "name")

    def test_create_dn_nested(self):
        self.assertEqual(create_dn("a", "name"), "a.name")

    def test_create_dn_with_index(self):
        self.assertEqual(create_dn("a", None, 0), "a.[0]")

    def test_create_dn_list_no_index(self):
        self.assertEqual(create_dn_list("arp", "", None), "arp.[]")

    def test_create_dn_list_with_index(self):
        self.assertEqual(create_dn_list("arp", "", 1), "arp.[1]")

    def test_create_dn_list_with_parent_dn(self):
        self.assertEqual(create_dn_list("arp", "domain", None), "domain.arp.[]")

    def test_get_all_uniq_keys_merges(self):
        result = get_all_uniq_keys([{"a": 1, "b": 2}, {"a": 1, "c": 3}])
        self.assertEqual(result, {"a": 1, "b": 2, "c": 3})


class TestEndToEndBootstrapAndRun(unittest.TestCase):
    """A one_to_one-generated model should run through the engine round-trip."""

    def test_bootstrap_model_runs_detail(self):
        from one_to_one import one_to_one_looper

        CONFIG.clear()
        CONFIG["skip_description"] = True
        try:
            sample = {"name": "Bob", "email": "bob@example.com"}
            model = one_to_one_looper(sample)
            result = run_detail(model, input=sample)
            self.assertEqual(result, sample)
        finally:
            CONFIG.clear()


if __name__ == "__main__":
    unittest.main()
