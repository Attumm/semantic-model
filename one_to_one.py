import re
import sys
import json

from data import regexes, descriptions

# I like vanilla python, for some reason parser like the request liberary could be installed already.
# If it's not installed we will just skip it.
try:
    from dateutil import parser
except Exception:
    class A():
        pass
    parser = A()
    parser.parse = lambda x: False


class Skip(Exception):
    pass


NESTED = "nested"
ITERABLES = ["list", "dict"]

TYPE_TRANSLATE = {
        "str": "string"
}

TYPE_FIELD = {
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
    if item is None:
        return "str"
    return str(type(item).__name__)


def get_description(identified):
    if CONFIG.get("skip_description"):
        return ""
    return DATA["description"].get(identified, "")


def create_source(data, result, dn, has_context_data):
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
    if dn == "":
        return title

    if index is not None:
        return f"{dn}.[{index}]"

    return f"{dn}.{title}"


def create_dn_list(title, dn, index=None):
    result = "[]" if index is None else f"[{index}]"

    if title is not None:
        result = f"{title}.{result}"
    if dn:
        result = f"{dn}.{result}"
    return result


def get_all_uniq_keys(data):
    keys = {}
    for item in data:
        for k, v in item.items():
            keys[k] = v
    return keys
            

def one_to_one_looper(data, title=None, dn="", has_context_data=False):
    type_ = str_type(data)
    type_ = TYPE_TRANSLATE.get(type_, type_)
    result = {}
    if title is not None:
        result["title"] = " ".join(i.capitalize() for i in title.replace("_", " ").split(" "))

    result["type"] = type_
    if not CONFIG.get("skip_source") and dn:
        try:
            result["source"] = create_source(data, result, dn, has_context_data)
        except Skip:
            print("skipped", dn)
            pass

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
                    nested_result[k] = one_to_one_looper(v, title=k, dn=create_dn(dn, k), has_context_data=True)
            else:
                type_found = list(types_found.keys())[0]
                result["item"] = one_to_one_looper(data[0], dn=create_dn_list(result.get("title"), dn))

        elif len(types_found) == 0:
            result["item"] = one_to_one_looper("", dn=create_dn_list(result.get("title"), dn))

        else:
            result["items"] = []
            for type_found, index in types_found.items():
                if type_found not in ITERABLES:
                    r = one_to_one_looper(data[index], dn=create_dn_list(result.get("title"), dn, index))
                    result["items"].append(r)
                else:
                    raise Exception
    else:
        pass

    return result


def run_one_to_one(sm_model_path, input_file):
    return one_to_one_looper(json.load(open(input_file)))


if __name__ == "__main__":
    result = one_to_one_looper(json.load(sys.stdin))

    print(json.dumps(result, indent=2))
