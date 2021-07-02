import sys
import json

NESTED = "nested"
ITERABLES = ["list", "dict"]

TYPE_TRANSLATE = {
        "str": "string"
}


def str_type(item):
    return str(type(item).__name__)


def looper(data, title=None, toplevel=True):
    type_ = str_type(data)
    type_ = TYPE_TRANSLATE.get(type_, type_)
    result = {
        "type": type_
    }
    if title is not None:
        result["title"] = " ".join(i.capitalize() for i in title.replace("_", " ").split(" "))

    if type_ not in ITERABLES:
        result["example"] = str(data)[:40]

    if type_ == "dict":
        nested_result = {}
        result["nested"] = nested_result
        for k, v in data.items():
            nested_result[k] = looper(v, title=k, toplevel=False)

    elif type_ == "list":
        types_found = {str_type(v): i for i, v in enumerate(data)}
        if len(types_found) == 1:
            type_found = list(types_found.keys())[0]
            result["item"] = looper(data[0], toplevel=False)
        else:
            result["items"] = []
            for type_found, index in types_found.items():
                if type_found not in ITERABLES:
                    r = looper(data[index], toplevel=False)
                    result["items"].append(r)

    else:
        pass

    return result


if __name__ == "__main__":
    result = looper(json.load(sys.stdin))
    print(json.dumps(result, indent=2))
