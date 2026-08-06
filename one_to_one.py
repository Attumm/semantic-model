import json
import re
import sys

from data import descriptions, regexes

# I like vanilla python, for some reason parser like the request liberary could be installed already.
# If it's not installed we will just skip it.
try:
    from dateutil import parser
except Exception:

    class A:
        pass

    parser = A()
    parser.parse = lambda x: False


class Skip(Exception):
    """Raised to skip generating ``source`` for a node (caught in the looper)."""


NESTED = "nested"
ITERABLES = ["list", "dict"]

TYPE_TRANSLATE = {"str": "string"}

TYPE_FIELD = {
    # Promotes a recognised value to a semantic ``field_type`` rather than a
    # bare ``string`` (keys come from data.regexes).
    "Uniform Resource Locator (URL)": "URL",
    "Internet Protocol (IP) Address Version 6": "ipv6",
    "Email Address": "email",
    "Internet Protocol (IP) Address Version 4": "ipv4",
    "Latitude & Longitude Coordinates": "geopoint",
}

data_dir = "data"
DATA = {
    "regex": regexes,
    "description": descriptions,
}

CONFIG = {}


def identify(item):
    """Match ``item`` against the built-in regex catalogue; return its name.

    Falls back to detecting a parseable timestamp (via ``dateutil`` when
    installed). Returns ``""`` if nothing matches.
    """
    for name, regex in DATA["regex"].items():
        if re.match(regex, item):
            return name
        try:
            if type(item) == str and not item.isdigit() and parser.parse(item):
                return "timestamp"
        except Exception:
            pass
    return ""


def str_type(item):
    """Return the DSM type name for ``item``'s Python type (``str`` -> ``"str"``)."""
    if item is None:
        return "str"
    return str(type(item).__name__)


def get_description(identified):
    """Return the human description for an identified type (``""`` if skipped)."""
    if CONFIG.get("skip_description"):
        return ""
    return DATA["description"].get(identified, "")


def create_source(data, result, dn, has_context_data):
    """Infer a ``source`` block for the current node from the sample data.

    Picks ``dn_lookup_loop`` for list/iterable sources, ``yield`` inside a list
    row, or ``json_key_item`` for scalar leaves (reading ``context_data`` when
    inside a list-of-dicts, otherwise the named input).
    """
    if result["type"] == "list":
        types_found = {str_type(v): i for i, v in enumerate(data)}
        if len(types_found) == 1:
            if "dict" in types_found:
                return {"type": "dn_lookup_loop", "source": "input", "dn": dn}
            else:
                return {"type": "dn_lookup_loop", "source": "input", "dn": dn}
        else:
            return {"type": "dn_lookup_loop", "source": "input", "dn": dn}

    elif dn[-1] == "]":
        if dn[-2].isdigit():
            return {"type": "yield", "index": dn.split(".")[-1][1:-1]}
        else:
            return {"type": "yield"}

    elif result["type"] in ["string", "int", "bool", "float"]:
        if has_context_data:
            return {"type": "json_key_item", "dn": dn.split(".")[-1]}
        else:
            return {"type": "json_key_item", "source": "input", "dn": dn}
    else:
        return {}


def create_dn(dn, title, index=None):
    """Build a dotted DN string: ``dn.title`` or ``dn.[index]``."""
    if dn == "":
        return title

    if index is not None:
        return f"{dn}.[{index}]"

    return f"{dn}.{title}"


def create_dn_list(title, dn, index=None):
    """Build a list-position DN: ``title.dn.[]`` or ``title.dn.[index]``."""
    result = "[]" if index is None else f"[{index}]"

    if title is not None:
        result = f"{title}.{result}"
    if dn:
        result = f"{dn}.{result}"
    return result


def get_all_uniq_keys(data):
    """Merge all keys across a list of dicts into one ``{key: sample_value}``."""
    keys = {}
    for item in data:
        for k, v in item.items():
            keys[k] = v
    return keys


def one_to_one_looper(data, title=None, dn="", has_context_data=False):
    """Recursively build a starter DSM model from sample ``data``.

    Infers each node's ``type``, ``source`` (unless ``skip_source`` is set), and
    for leaves an auto-detected ``field_type``/``description``/``example``.
    Dicts recurse into ``nested``; lists pick ``item`` (one shape), ``items``
    (mixed shapes), or ``nested`` (list of dicts).
    """
    type_ = str_type(data)
    type_ = TYPE_TRANSLATE.get(type_, type_)
    result = {}
    if title is not None:
        result["title"] = " ".join(
            i.capitalize() for i in title.replace("_", " ").split(" ")
        )

    result["type"] = type_
    if not CONFIG.get("skip_source") and dn:
        try:
            result["source"] = create_source(data, result, dn, has_context_data)
        except Skip:
            print("skipped", dn)

    if type_ not in ITERABLES:
        identified = identify(str(data))
        if identified in TYPE_FIELD:
            result["field_type"] = TYPE_FIELD[identified]

        result["example"] = str(data)[:50]
        result["description"] = get_description(identified)

    elif type_ == "dict":
        nested_result = {}
        result["nested"] = nested_result
        for k, v in data.items():
            nested_result[k] = one_to_one_looper(v, title=k, dn=create_dn(dn, k))

    elif type_ == "list":
        types_found = {str_type(v): i for i, v in enumerate(data)}
        if len(types_found) == 1:
            if "dict" in types_found:
                nested_result = {}
                result["nested"] = nested_result

                for k, v in get_all_uniq_keys(data).items():
                    nested_result[k] = one_to_one_looper(
                        v, title=k, dn=create_dn(dn, k), has_context_data=True
                    )
            else:
                type_found = list(types_found.keys())[0]
                result["item"] = one_to_one_looper(
                    data[0], dn=create_dn_list(result.get("title"), dn)
                )

        elif len(types_found) == 0:
            result["item"] = one_to_one_looper(
                "", dn=create_dn_list(result.get("title"), dn)
            )

        else:
            result["items"] = []
            for type_found, index in types_found.items():
                if type_found not in ITERABLES:
                    r = one_to_one_looper(
                        data[index], dn=create_dn_list(result.get("title"), dn, index)
                    )
                    result["items"].append(r)
                else:
                    raise Exception
    else:
        pass

    return result


def run_one_to_one(sm_model_path, input_file):
    """Build a starter model from a sample JSON file (``-mode one_to_one``)."""
    return one_to_one_looper(json.load(open(input_file)))


if __name__ == "__main__":
    result = one_to_one_looper(json.load(sys.stdin))

    print(json.dumps(result, indent=2))
