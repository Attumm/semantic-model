import datetime
import json
import re
import uuid

from settipy import settipy

DEBUG_MODE = False


# Per-run data store. ``input`` holds named input payloads passed via the
# ``run_*(..., **input_data)`` kwargs; ``context_data`` is the scratch slot used
# while iterating list items. ``KEY_STORAGE_LIST_ITEM`` holds the merged "common"
# metadata row shared by every list-item view.
STORAGE = {
    "input": {},
    "context_data": {},
}


# Maps a model ``type`` to the Python type used to materialise results.
ITEMS = {
    "dict": dict,
    "list": list,
    "string": str,
    "integer": int,
    "boolean": bool,
}


# Structural types that ``init_item`` knows how to instantiate on demand.
DEFAULT_TYPE = {
    "dict": dict,
    "list": list,
    "list_item": list,
}


class BaseDSMException(Exception):
    """Base class for all semantic-model errors."""


class InvalidModel(BaseDSMException):
    """Raised when a DSM model is malformed or cannot be run.

    Covers missing ``type``, missing/unknown ``source.type``, unknown
    ``postformat.type``, a missing ``dn`` on a source, and a ``json_key_item``
    lookup that has no value and no ``default``.
    """


# defined types
# Reserved key names used throughout a DSM model. Centralising them avoids
# typos and keeps the model schema self-documenting.
KEY_FIELD_TYPE = "field_type"
KEY_TYPE = "type"
KEY_DEFAULT = "default"
KEY_DESCRIPTION = "description"
KEY_EXAMPLE = "example"
KEY_DEPENDS_ON = "depends_on"
KEY_VALIDATOR = "validator"
KEY_LINK = "relation"
KEY_NESTED = "nested"
KEY_RBAC = "rbac"
KEY_GATHER = "source"

KEY_STORAGE_LIST_ITEM = "__global_list_item"
STORAGE[KEY_STORAGE_LIST_ITEM] = {}


def run_with_json(action, model_path, roles=None, **input_path):
    """Load a model + named input JSON files and dispatch to an action.

    ``action`` is one of ``ACTIONS`` (``detail``/``list``/``node``).
    ``input_path`` maps storage names to JSON file paths, e.g.
    ``run_with_json('detail', 'sm.json', input='data.json')``.
    Raises ``ValueError`` for an unknown action.
    """
    dsm_model = json.load(open(model_path))
    input_data = {k: json.load(open(v)) for k, v in input_path.items()}

    try:
        func = ACTIONS[action]
    except KeyError:
        raise ValueError(f"Action not part of {ACTIONS.keys()}")

    return func(dsm_model, roles=roles, **input_data)


def run_detail_json(model_path, roles=None, **input_path):
    """Load model+input files and run the ``detail`` action (nested output)."""
    return run_with_json("detail", model_path, roles=None, **input_path)


def run_list_json(model_path, roles=None, **input_path):
    """Load model+input files and run the ``list`` action (flat rows)."""
    return run_with_json("list", model_path, roles=None, **input_path)


def run_node_json(model_path, roles=None, **input_path):
    """Load model+input files and run the ``node`` action (metadata rows)."""
    return run_with_json("node", model_path, roles=None, **input_path)


def run_detail(model, roles=None, **input_data):
    """Run the ``detail`` action: return the fully nested object for ``model``.

    ``input_data`` is stored in ``STORAGE['input']`` under each kwarg name and
    made available to ``source`` blocks by that name. ``roles`` filters the
    output through RBAC (see :func:`has_read_rights`).
    """
    # setup connection to database
    # setup api credential
    for k, v in input_data.items():
        STORAGE["input"][k] = v

    return full_detail(model, roles=roles, storage=STORAGE)


def get_data(gather_args, model, dn_parent, storage):
    """Resolve which named data store a source reads from.

    Returns ``storage['context_data']`` when the source declares no ``source``
    key (i.e. it reads the current row-in-flight), otherwise
    ``storage['input'][source]``.
    """
    if KEY_GATHER not in gather_args:
        data = storage["context_data"]
    else:
        data = storage["input"][gather_args[KEY_GATHER]]
    return data


def json_key(gather_args, model, dn_parent, storage):
    """Read a key from a named data store.

    With ``multi: true`` it yields each element at that key (a list source);
    otherwise it returns the value, or ``default`` when the key is absent.
    """
    data = get_data(gather_args, model, dn_parent, storage)
    if gather_args["dn"] not in data:
        return gather_args.get("default")

    if gather_args.get("multi"):
        yield from data.get(gather_args["dn"])
    else:
        return data.get(gather_args["dn"])


def json_key_item(gather_args, model, dn_parent, storage):
    """Read a single required key.

    Raises :class:`InvalidModel` if the key is missing and no ``default`` is
    provided — this is the strict variant of :func:`json_key`.
    """
    data = get_data(gather_args, model, dn_parent, storage)
    try:
        return data[gather_args["dn"]]
    except KeyError:
        if "default" in gather_args:
            return gather_args.get("default")
        raise InvalidModel(
            f"Missing data and default for source {model['source']['type']} with dn {dn_parent}"
        )


def dn_lookup_loop(gather_args, model, dn_parent, storage):
    """Resolve a dot-path ``dn`` and yield each element at that location."""
    dn = gather_args["dn"]

    data = get_data(gather_args, model, dn_parent, storage)
    for i in yield_by_dn(data, dn):
        yield i


def dn_lookup(gather_args, model, dn_parent, storage):
    """Resolve a dot-path ``dn`` (e.g. ``a.b.c``) and return the value.

    Returns ``[]`` if any segment is missing. For list-indexed segments use
    the ``[i]`` syntax handled by :func:`get_by_dn`.
    """
    data = get_data(gather_args, model, dn_parent, storage)
    current_pointer = data
    for item in gather_args["dn"].split("."):
        try:
            current_pointer = current_pointer.get(item)
        except AttributeError:
            # TODO log for debug
            return []
    return current_pointer


def get_from_source(gather_args, model, dn_parent, storage):
    data = get_data(gather_args, model, dn_parent, storage)

    try:
        dn = gather_args.get("path_to_target") or gather_args["dn"]
    except KeyError:
        raise InvalidModel(
            f"Missing 'dn' in source  {model['source']['type']} with dn: {dn_parent}"
        )
    found, result = get_by_dn(data, dn)
    if found:
        return result
    return gather_args.get("default")


def key_lookup(gather_args, model, dn_parent, storage):
    """Look up a ``key``/``dn`` in ``context_data`` or a named input store."""
    key = gather_args.get("key") or gather_args.get("dn")
    if KEY_GATHER not in gather_args:
        return storage["context_data"].get(key)  # TODO set better debugging
    else:
        return storage["input"][gather_args[KEY_GATHER]].get(key)


def loop_over(gather_args, model, dn_parent, storage):
    """Yield every element of the source data."""
    data = get_data(gather_args, model, dn_parent, storage)
    yield from data


def index(gather_args, model, dn_parent, storage):
    """Return the element at ``source[index]`` (positional list pick)."""
    data = get_data(gather_args, model, dn_parent, storage)
    return data[gather_args["index"]]


def is_list_dn(item):
    """True if a DN segment denotes a list index, e.g. ``"[0]"``."""
    return item[0] == "[" and item[-1] == "]"


def get_index_num_from_list_dn(item):
    """Return the integer index encoded in a ``[i]`` DN segment."""
    if len(item) == 2:
        return 0
    return int(item[1 : item.find("]")])


def get_by_dn(data_source, dn):
    """Resolve a dot-separated DN against ``data_source``.

    Supports ``[i]`` list-index segments. Returns ``(found, value)``;
    ``found`` is ``False`` (with an empty value) when any step is missing.
    """
    found = True
    index = data_source
    try:
        for step in dn.split("."):
            if is_list_dn(step):
                index_num = get_index_num_from_list_dn(step)
                index = index[index_num]
            else:
                index = index.get(step, {})
    except (AttributeError, IndexError, KeyError):
        return not found, ""

    return found, index


def yield_by_dn(data_source, dn):
    """Yield each element located at ``dn`` (or nothing if not found)."""
    found, index = get_by_dn(data_source, dn)
    if found:
        yield from index
    else:
        yield from []


def iter_by_key(gather_args, model, dn_parent, storage):
    """N(1) join across a list of dicts keyed by ``key``.

    Reads ``dn_to_ids`` and ``dn_to_values`` from the source, then for each id
    yields ``{item: value_for_id, ...}`` for every item. Optional
    ``dn_data_source`` narrows the data first.
    """
    # setup args
    dn_data_source = gather_args.get("dn_data_source")
    key = gather_args["key"]
    dn_to_ids = gather_args["dn_to_ids"]
    dn_to_values = gather_args["dn_to_values"]

    # get the initial data_source
    data_source = storage["input"][gather_args[KEY_GATHER]]

    # point the datasource to a subset of data.
    # this will make subsequent dn searches simpler.
    if dn_data_source is not None:
        _, data_source = get_by_dn(data_source=data_source, dn=dn_data_source)

    # get the items that need to be joined
    items = [item[key] for item in data_source]

    # create a buffer to join items with be done N(1) complexity.
    buffer = {}
    for item in data_source:
        found, data = get_by_dn(data_source=item, dn=dn_to_values)
        if found:
            buffer[item[key]] = data
    found, ids = get_by_dn(data_source, dn_to_ids)

    # loop over ids and join the fields
    for index, id_ in enumerate(ids):
        yield {item: buffer.get(item, {}).get(id_) for item in items}


def iter_by_prop(gather_args, model, dn_parent, storage):
    """Join list-of-lists by an id DN, yielding ``{...fields, "id": index}``."""
    # setup args
    dn_data_source = gather_args.get("dn_data_source")
    dn_to_id = gather_args["dn_to_id"]
    dn_to_value = gather_args["dn_to_value"]

    # get the initial data_source
    data_source = storage["input"][gather_args[KEY_GATHER]]

    # point the datasource to a subset of data.
    # this will make subsequent dn searches simpler.
    if dn_data_source is not None:
        _, data_source = get_by_dn(data_source=data_source, dn=dn_data_source)

    buffer = {}
    for key, item in data_source.items():
        for element_in_list in item:
            data_found, data = get_by_dn(data_source=element_in_list, dn=dn_to_value)
            index_found, index = get_by_dn(data_source=element_in_list, dn=dn_to_id)
            if index_found and data_found:
                if index not in buffer:
                    buffer[index] = {}
                buffer[index][key] = data

    for index, item in buffer.items():
        yield {**item, "id": index}


def generate_informations(index):
    """Build a ``(source, group)`` label from a dotted DN for :func:`iter_by_prop2`."""
    all_values = index.split(".")
    group = ".".join(all_values[2:6])
    source = ".".join(all_values[7:11])
    return f"({source if source is not None else '*'},{group})"


def iter_by_prop2(gather_args, model, dn_parent, storage):
    """Like :func:`iter_by_prop` but with a generated ``(source, group)`` id."""
    # setup args
    dn_data_source = gather_args.get("dn_data_source")
    dn_to_id = gather_args["dn_to_id"]
    dn_to_value = gather_args["dn_to_value"]

    # get the initial data_source
    data_source = storage["input"][gather_args[KEY_GATHER]]

    # point the datasource to a subset of data.
    # this will make subsequent dn searches simpler.
    if dn_data_source is not None:
        _, data_source = get_by_dn(data_source=data_source, dn=dn_data_source)

    buffer = {}
    for key, item in data_source.items():
        for element_in_list in item:
            data_found, data = get_by_dn(data_source=element_in_list, dn=dn_to_value)
            index_found, index = get_by_dn(data_source=element_in_list, dn=dn_to_id)
            if index_found and data_found:
                if index not in buffer:
                    buffer[index] = {}
                buffer[index][key] = data

    for index, item in buffer.items():
        yield {**item, "id": generate_informations(index)}


def return_value(gather_args, model, dn_parent, storage):
    """Return a literal ``value`` from the source definition."""
    return gather_args["value"]


def yield_from(gather_args, model, dn_parent, storage):
    """Yield from ``context_data`` (optionally at ``index``)."""
    if "index" in gather_args:
        return storage["context_data"][gather_args["index"]]
    return storage["context_data"]


SOURCE_FUNC = {
    # Registry of every ``source.type`` handler. ``get_func_args_from_source``
    # resolves the gather function through this table; extend it to add custom
    # source types (see README → Extending).
    "json_key": json_key,
    "json_key_item": json_key_item,
    "dn_lookup": dn_lookup,
    "dn_lookup_loop": dn_lookup_loop,
    "key_lookup": key_lookup,
    "iter_by_key": iter_by_key,
    "iter_by_prop": iter_by_prop,
    "iter_by_prop2": iter_by_prop2,
    "loop_over": loop_over,
    "index": index,
    "return_value": return_value,
    "get_from_source": get_from_source,
    "get_from_input_file": get_from_source,
    "yield": yield_from,
}


def always_false(*args, **kwargs):
    """Filter predicate that rejects nothing (the default ``filter_type``)."""
    return False


def dict_key_is_empty(item, key):
    """Filter predicate: True when ``item[key]`` is falsy/missing."""
    return not bool(item.get(key))


def contains(item, arg):
    """Filter predicate: True when ``arg`` is present in ``item``."""
    return arg in item


def not_cotains(item, arg):
    """Filter predicate: True when ``arg`` is absent from ``item``."""
    return arg not in item


FILTERS = {
    # Registry of ``filter_type`` predicates. A gathered value is kept only
    # when its predicate returns False. ``default`` (always_false) keeps all.
    "contains": contains,
    "not_contains": not_cotains,
    "dict_key_is_empty": dict_key_is_empty,
    "default": always_false,
}


def default_postformat(item, **kwargs):
    """Identity postformat: return the value unchanged."""
    return item


def int_to_iso_timestamp(item, **kwargs):
    """Convert a millisecond Unix timestamp to an ISO-8601 string.

    Pass ``fail-silent`` to return the original value on failure instead of
    raising.
    """
    try:
        result = datetime.datetime.fromtimestamp(int(item) / 1e3).isoformat()
    except Exception:
        if kwargs.get("fail-silent"):
            result = item
        else:
            raise
    return result


def regex_to_iso_timestamp(item, **kwargs):
    """Parse ``item`` with ``kwargs['format']`` and return its ISO-8601 form."""
    re_format = kwargs.get("format")
    return datetime.datetime.strptime(item, re_format).isoformat()


def regex_search(item, **kwargs):
    """Return ``re.search(regex, item).group(0)``, or ``default`` if no match.

    The ``default`` fallback makes this a coercive validator: non-matching
    values are replaced rather than dropped.
    """
    regex = kwargs.get("regex")
    result = re.search(regex, item)
    if result is None:
        return kwargs.get("default")
    return result.group(0)


def create_uuid5(domain, id):
    """Deterministic UUID-5 for ``(domain, id)`` (namespace padded to 16 bytes)."""
    namespace = uuid.UUID(bytes=bytes(f"{domain}".ljust(16, "o").encode("ASCII")))
    return str(uuid.uuid5(namespace, id))


def format_dict_to_key_list(item, **kwargs):
    """Postformat: turn a dict into the list of its keys."""
    return [key for key in item.keys()]


POSTFORMAT = {
    # Registry of ``postformat.type`` handlers applied after gathering. Extend
    # it to add custom transforms (see README → Extending).
    "default": default_postformat,
    "int_to_iso_timestamp": int_to_iso_timestamp,
    "regex_to_iso_timestamp": regex_to_iso_timestamp,
    "regex_search": regex_search,
    "hash_uuid": create_uuid5,
    "format_dict_to_key_list": format_dict_to_key_list,
}


def get_func_args_from_source(source, dn):
    """Resolve all dispatch tables for a ``source`` block.

    Returns ``(gather_func, filter_func, gather_args, filter_args,
    postformat_func, postformat_args)``. Raises :class:`InvalidModel` for a
    missing/unknown ``source.type`` or ``postformat.type`` — this is the main
    structural-validation point for source definitions.
    """
    try:
        source_type = source["type"]
    except KeyError:
        raise InvalidModel(f"Missing 'type' on source with dn {dn}")

    try:
        source_func = SOURCE_FUNC[source_type]
    except KeyError:
        raise InvalidModel(
            f"Missing source function on {source_type} on source with dn {dn}"
        )

    try:
        filter_func = FILTERS.get(
            source.get("filter_type", "default")
        )  # TODO fail when filter is not present
    except KeyError:
        raise InvalidModel(f"Missing filter on {source_type} on source with dn {dn}")

    try:
        postformat_options = source.get("postformat", {}).copy()
        postformat_name = postformat_options.pop("type", "default")
        postformat_func = POSTFORMAT[postformat_name]
        postformat_args = postformat_options
    except KeyError:
        # TODO add below message to errors, to make more descriptive
        raise InvalidModel(
            f"Missing post_format on {source_type} on source with dn {dn}, {postformat_name} not in available options {POSTFORMAT.keys()}"
        )

    return (
        source_func,
        filter_func,
        {k: v for k, v in source.items() if k != "type" or k.startswith("filter_")},
        source.get("filter_args", {}),
        postformat_func,
        postformat_args,
    )


def gather_items(model, dn, storage):
    """Yield postformatted, filtered values for a multi-value ``source``.

    Each gathered item is dropped when its ``filter_type`` predicate is true,
    then passed through its ``postformat`` transform. Wraps errors as
    :class:`InvalidModel`.
    """
    try:
        source = model[KEY_GATHER]
    except KeyError:
        raise InvalidModel(f"Missing 'source' on dn {dn}")
        return []

    try:
        (
            gather_func,
            filter_func,
            gather_args,
            filter_args,
            postformat_func,
            postformat_args,
        ) = get_func_args_from_source(source, dn)
        for item in gather_func(
            gather_args=gather_args, model=model, dn_parent=dn, storage=storage
        ):
            if not filter_func(item, **filter_args):
                yield postformat_func(item, **postformat_args)

    except Exception as e:
        raise InvalidModel(f"Error while gathering data, on dn {dn}, reason: {e}")


def gather_item(model, dn, storage):
    """Gather and postformat a single value (non-iterable sources).

    Unlike :func:`gather_items` this returns one value rather than yielding.
    """
    try:
        source = model[KEY_GATHER]
    except KeyError:
        raise InvalidModel(f"Missing 'source' on dn {dn}")
    (
        gather_func,
        filter_func,
        gather_args,
        filter_args,
        postformat_func,
        postformat_args,
    ) = get_func_args_from_source(source, dn)
    result = gather_func(
        gather_args=gather_args, model=model, dn_parent=dn, storage=storage
    )
    return postformat_func(result, **postformat_args)


def get_item_type(model, dn):
    """Return ``model['type']`` or raise :class:`InvalidModel` (validation)."""
    try:
        return model["type"]
    except KeyError:
        raise InvalidModel(f"Missing 'type' on dn {dn}")
    except TypeError as e:
        raise InvalidModel(f"Error while getting 'type' on dn {dn}: {e}")


def init_item(model, dn):
    """Instantiate the empty container for ``model['type']`` (dict/list/...)."""
    item_type = get_item_type(model, dn)
    item = DEFAULT_TYPE.get(item_type, lambda: None)()
    return item


def has_read_rights(model, roles):
    """RBAC check: True if any of ``roles`` has ``read`` on ``model``.

    When ``roles`` is ``None`` access control is disabled (everything visible).
    """
    if roles is None:
        return True

    rbac = {k for k, v in model.get("rbac", {}).items() if v.get("read") is True}
    return bool(set(roles) & rbac)


def new_dn(dn, key):
    """Append ``key`` to DN tuple ``dn`` (returns a new tuple)."""
    return dn + (key,)


def full_detail(model, dn=(), context_data=None, roles=None, storage=None):
    """Build the fully nested ``detail`` object for ``model``.

    Recurses through ``dict`` -> ``nested``, and the three ``list`` shapes
    (``item`` / ``items`` / ``nested``). Each visited node is gated by
    :func:`has_read_rights`; ``skip`` nodes are omitted; leaves are gathered via
    :func:`gather_item` / :func:`gather_items`.
    """
    item = init_item(model, dn)

    if model["type"] == "dict":
        for key, sub_model in model["nested"].items():
            if sub_model.get("skip"):
                continue
            if has_read_rights(sub_model, roles):
                item[key] = full_detail(
                    sub_model, new_dn(dn, key), roles=roles, storage=storage
                )

    elif model["type"] == "list":
        if "item" in model:
            sub_model = model["item"]
            for result in gather_items(model, dn, storage=storage):
                if has_read_rights(sub_model, roles):
                    sub_item = init_item(sub_model, dn)
                    # TODO apply "item" logic
                    item.append(result)

        elif "items" in model:
            for result in gather_items(model, dn, storage=storage):
                p = []
                for i, sub_model in enumerate(model["items"]):
                    if has_read_rights(sub_model, roles):
                        sub_item = init_item(sub_model, dn)
                        storage["context_data"] = result

                        result_i = gather_item(sub_model, dn, storage=storage)
                        # TODO apply "item" logic, and tests
                        # result_i = full_detail(sub_model, dn+("[]",), context_data=result, roles=roles, storage=storage)
                        p.append(result_i)

                item.append(p)

        elif "nested" in model:
            for partial_result in gather_items(model, dn, storage=storage):
                sub_item = {}
                for key, sub_model in model["nested"].items():
                    if has_read_rights(sub_model, roles):
                        storage["context_data"] = partial_result
                        sub_item[key] = full_detail(
                            sub_model, new_dn(dn, key), roles=roles, storage=storage
                        )
                item.append(sub_item)
        # item of default
        else:
            return item
    else:
        item = gather_item(model, dn, storage=storage)

    return item


def list_item(model, dn, value):
    """Build one ``list``-action row: value + metadata + shared common fields."""
    item = {
        "value": value,
        "dn": dn,
        "title": model.get("title"),
        "description": model.get("description"),
        "type": model["type"],
        "field_type": model.get("field_type"),
        "searchable": model.get("searchable", True),
    }
    item.update(STORAGE[KEY_STORAGE_LIST_ITEM])
    return item


def create_meta_data_list(model, dn, key, value):
    """Build the per-column metadata for a ``node``-action row.

    Emits ``<key>``, ``_<key>_dn``, ``_<key>_type`` (plus ``_<key>_field_type``
    and ``_<key>_description`` when present) and one ``_<key>_rbac_<action>``
    list per RBAC action listing the roles that hold it.
    """
    meta_data = {
        key: value,
        f"_{key}_dn": list(dn),
        # f"_{key}_title": model.get("title"),
        f"_{key}_type": model["type"],
    }
    if model.get("field_type"):
        meta_data[f"_{key}_field_type"] = model.get("field_type")
    if model.get("description"):
        meta_data[f"_{key}_description"] = model.get("description")

    rbac = model.get("rbac")
    if rbac is not None:
        meta_data[f"_{key}_rbac_create"] = [
            group for group, policies in rbac.items() if policies.get("create")
        ]
        meta_data[f"_{key}_rbac_read"] = [
            group for group, policies in rbac.items() if policies.get("read")
        ]
        meta_data[f"_{key}_rbac_update"] = [
            group for group, policies in rbac.items() if policies.get("update")
        ]
        meta_data[f"_{key}_rbac_delete"] = [
            group for group, policies in rbac.items() if policies.get("delete")
        ]

    return meta_data


def list_node(model, dn, value):
    """Build one ``node``-action row: ``_dn`` + ``__columns`` + per-column meta.

    For dict values it expands each key with :func:`create_meta_data_list`;
    for scalar values it emits a single ``"value"`` column.
    """
    item = {"_dn": list(dn), "__columns": []}
    item.update(STORAGE[KEY_STORAGE_LIST_ITEM])
    if isinstance(value, dict):
        for key, loop_value in value.items():
            nested_value = create_meta_data_list(
                model["nested"][key], new_dn(dn, key), key, loop_value
            )
            item.update(nested_value)
            item["__columns"].append(key)
    else:
        meta_item = create_meta_data_list(model, dn, "value", value)
        meta_item["__columns"] = [
            "value",
        ]

        item.update(meta_item)
    return item


def list_items(model, dn=(), context_data=None, roles=None, storage=None):
    """Yield ``list``-action rows by walking ``model`` (one row per leaf)."""
    item = init_item(model, dn)
    if model["type"] == "dict":
        for key, sub_model in model["nested"].items():
            if sub_model.get("skip"):
                continue
            if has_read_rights(sub_model, roles):
                yield from list_items(
                    sub_model, new_dn(dn, key), roles=roles, storage=storage
                )

    elif model["type"] == "list":
        # list item contains single item
        if "item" in model:
            sub_model = model["item"]
            for result in gather_items(model, dn, storage=storage):
                if has_read_rights(sub_model, roles):
                    sub_item = init_item(sub_model, dn)
                    # TODO apply "item" logic
                    yield list_item(sub_model, dn + ("item",), result)

        # list contains multiple single items
        elif "items" in model:
            for result in gather_items(model, dn, storage=storage):
                for i, sub_model in enumerate(model["items"]):
                    if has_read_rights(sub_model, roles):
                        # TODO apply "sub_item" logic
                        sub_item = init_item(sub_model, dn)
                        storage["context_data"] = result
                        result_i = gather_item(sub_model, dn, storage=storage)
                        yield list_item(sub_model, dn + ("item",), result_i)

        # list contains dict
        elif "nested" in model:
            for partial_result in gather_items(model, dn, storage=storage):
                for key, sub_model in model["nested"].items():
                    if has_read_rights(sub_model, roles):
                        storage["context_data"] = partial_result
                        yield from list_items(
                            sub_model, new_dn(dn, key), roles=roles, storage=storage
                        )
        # return default or initil item
        else:
            yield item

    else:
        result = gather_item(model, dn, storage=storage)
        yield list_item(model=model, dn=dn, value=result)


def is_node(model):
    """True when a dict/list node has only leaf children (a renderable node row)."""
    return model["type"] in ["dict", "list"] and all(
        "nested" not in sub_model for sub_model in model["nested"].values()
    )


def list_nodes(model, dn=(), context_data=None, roles=None, storage=None):
    """Yield ``node``-action rows (one per node, with column metadata)."""
    item = init_item(model, dn)
    if model["type"] == "dict":
        if is_node(model):
            result = full_detail(model, dn, roles=roles, storage=storage)
            yield list_node(model=model, dn=dn, value=result)
        else:
            for key, sub_model in model["nested"].items():
                if sub_model.get("skip"):
                    continue

                if has_read_rights(sub_model, roles):
                    yield from list_nodes(
                        sub_model, new_dn(dn, key), roles=roles, storage=storage
                    )

    elif model["type"] == "list":
        if is_node(model):
            result = full_detail(model, dn, roles=roles, storage=storage)
            for item in result:
                yield list_node(model=model, dn=dn, value=item)
        else:
            # list item contains single item
            if "item" in model:
                sub_model = model["item"]
                for result in gather_items(model, dn, storage=storage):
                    if has_read_rights(sub_model, roles):
                        # TODO apply "item" logic, and tests
                        sub_item = init_item(sub_model, dn)
                        yield list_nodes(sub_model, new_dn(dn, "item"), result)

            # list contains multiple single items
            elif "items" in model:
                for result in gather_items(model, dn, storage=storage):
                    for i, sub_model in enumerate(model["items"]):
                        if has_read_rights(sub_model, roles):
                            # TODO apply "item" logic, and tests
                            sub_item = init_item(sub_model, dn)
                            storage["context_data"] = result
                            result_i = gather_item(sub_model, dn, storage=storage)
                            yield list_nodes(
                                sub_model,
                                new_dn(
                                    dn,
                                    "item",
                                ),
                                result_i,
                            )

            # list contains dict
            elif "nested" in model:
                for partial_result in gather_items(model, dn, storage=storage):
                    for key, sub_model in model["nested"].items():
                        if has_read_rights(sub_model, roles):
                            storage["context_data"] = partial_result
                            yield from list_nodes(
                                sub_model, new_dn(dn, key), roles=roles, storage=storage
                            )
            # return default or initil item
            else:
                print("should not happen")

    else:
        result = gather_item(model, dn, storage=storage)
        yield list_node(model=model, dn=dn, value=result)


def list_item_config(model, dn):
    if "list_item" in model:
        return model["list_item"]
    return model


def has_list_item_config(model):
    return "standard" in model.get("nested", {}) or "common" in model.get("nested", {})


def run_list(model, roles=None, **input_data):
    for k, v in input_data.items():
        STORAGE["input"][k] = v

    if has_list_item_config(model):
        common_key = "common" if "common" in model.get("nested", {}) else "standard"
        common_fields = full_detail(
            model["nested"][common_key], dn=(common_key,), roles=roles, storage=STORAGE
        )
        STORAGE[KEY_STORAGE_LIST_ITEM] = {
            f"common_{key}": val for key, val in common_fields.items()
        }

    return list_items(model, roles=roles, storage=STORAGE)


def run_nodes(model, roles=None, **input_data):
    for k, v in input_data.items():
        STORAGE["input"][k] = v

    if has_list_item_config(model):
        common_key = "common" if "common" in model.get("nested", {}) else "standard"
        common_fields = full_detail(
            model["nested"][common_key], dn=(common_key,), roles=roles, storage=STORAGE
        )
        STORAGE[KEY_STORAGE_LIST_ITEM] = {
            f"common_{key}": val for key, val in common_fields.items()
        }

    return list_nodes(model, roles=roles, storage=STORAGE)


def rbac_views(items):
    return {
        i: {"read": True, "update": True, "create": True, "delete": True} for i in items
    }


def update_views_to_rbac(model, dn):
    if "views" in model:
        views = model.pop("views")
        model["rbac"] = rbac_views(views)
    return model


def remove_list_item(model, dn):
    if "list_item" in model:
        model.pop("list_item")

    if "validators" in model:
        model["field_type"] = model.pop("validators")
    return model


def dsm_looper(run_func, dsm_model):
    def loop_over(model, dn=()):
        model = run_func(model, dn)
        if model["type"] == "dict":
            for key, sub_model in model["nested"].items():
                loop_over(sub_model, new_dn(dn, key))
        elif model["type"] == "list":
            if "items" in model:
                for sub_model in model["items"]:
                    loop_over(sub_model, new_dn(dn, "items"))
            elif "item" in model:
                loop_over(model["item"], new_dn(dn, "item"))
            elif "nested" in model:
                for key, sub_model in model["nested"].items():
                    loop_over(sub_model, new_dn(dn, key))
        return model

    return loop_over(dsm_model.copy())


ACTIONS = {
    "detail": run_detail,
    "list": run_list,
    "node": run_nodes,
}


def run_semantic_model(sm_model_path, input_file):
    return run_detail_json(sm_model_path, input=input_file)


def run_semantic_list_model(sm_model_path, input_file):
    return run_list_json(sm_model_path, input=input_file)


def run_semantic_nodes_model(sm_model_path, input_file):
    return run_node_json(sm_model_path, input=input_file)


def explain(*args, **kwargs):
    """Print the CLI usage cheat-sheet (``-mode help``)."""
    print("*** Explain ***\n")
    print("Create for initial model:")
    print(
        "python3 -m semantic_model -mode one_to_one -input example.json > sm_model.json"
    )
    print()
    print("Run model with just created model and example_data")
    print("python3 -m semantic_model -input example.json -sm sm_model.json")
    print()
    print("Graph created model and create a png image")
    print("sudo docker run -i attumm/dsm_png:lastest < sm_model.json > output.png")
    print()


def pjson(result):
    """Pretty-print ``result`` as indented JSON to stdout."""
    if result is None:
        return
    print(json.dumps(result, indent=4))


def json_(result):
    """Print ``result`` as compact JSON to stdout."""
    if result is None:
        return
    print(json.dumps(result))


def tofile(result):
    """Write ``result`` to ``output.json``."""
    if result is None:
        return
    with open("output.json", "w") as f:
        json.dump(result, f)


OUTPUT = {
    "pjson": pjson,
    "json": json_,
    "tofile": tofile,
}

if __name__ == "__main__":
    from one_to_one import run_one_to_one

    CLI = {
        "default": run_semantic_model,
        "detail": run_semantic_model,
        "list": run_semantic_list_model,
        "nodes": run_semantic_nodes_model,
        "greg": run_one_to_one,
        "one_to_one": run_one_to_one,
        "help": explain,
    }

    settipy.set("mode", "default", f"set the mode options: {CLI.keys()}")
    settipy.set("sm", "", "path to sm model. example: ./sm.json")
    settipy.set("input", "", "path to input json file. example: ./example.json")
    settipy.set("output", "pjson", "path to input json file. options: {OUTPUT.keys()}")
    settipy.parse()

    mode = settipy.get("mode")
    sm_model_path = settipy.get("sm")
    input_path = settipy.get("input")
    output = settipy.get("output")

    try:
        run_mode = CLI[mode]
    except KeyError:
        print(f"{mode} not in valid mode options: {list(CLI.keys())}")
        raise SystemExit(1) from None

    result = run_mode(sm_model_path, input_path)

    try:
        OUTPUT[output](result)
    except KeyError:
        print(f"{output} not in valid output options: {list(OUTPUT.keys())}")
