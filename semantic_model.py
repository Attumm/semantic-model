import json
import datetime
import re
DEBUG_MODE = False


STORAGE = {
    "input": {}, "context_data": {},
}

ITEMS = {
    "dict": dict,
    "list": list,
    "string": str,
    "integer": int,
    "boolean": bool,
}

DEFAULT_TYPE = {
    "dict": dict,
    "list": list,
    "list_item": list,
}


class BaseDSMException(Exception):
    pass


class InvalidModel(BaseDSMException):
    pass


# defined types
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


def prepare_model_for_run(model, role=None):
    pass


def run_with_json(action, model_path, role=None, **input_path):
    dsm_model = json.load(open(model_path))
    input_data = {k: json.load(open(v)) for k, v in input_path.items()}

    try:
        func = ACTIONS[action]
    except KeyError:
        raise ValueError(f"Action not part of {ACTIONS.keys()}")

    return func(dsm_model, role=role, **input_data)


def run_detail_json(model_path, role=None, **input_path):
    return run_with_json("detail", model_path, role=None, **input_path)


def run_list_json(model_path, role=None, **input_path):
    return run_with_json("list", model_path, role=None, **input_path)


def run_node_json(model_path, role=None, **input_path):
    return run_with_json("node", model_path, role=None, **input_path)


def run_detail(model, role=None, **input_data):
    ### setup connection to database
    ### setup api credential
    for k, v in input_data.items():
        STORAGE["input"][k] = v

    return full_detail(model, role=role, storage=STORAGE)


def get_data(gather_args, model, dn_parent, storage):
    if KEY_GATHER not in gather_args:
        data = storage["context_data"]
    else:
        data = storage["input"][gather_args[KEY_GATHER]]
    return data


def json_key(gather_args, model, dn_parent, storage):
    data = get_data(gather_args, model, dn_parent, storage)
    if gather_args["dn"] not in data:
        return gather_args.get("default")

    if gather_args.get("multi"):
        yield from data.get(gather_args["dn"])
    else:
        return data.get(gather_args["dn"])


def json_key_item(gather_args, model, dn_parent, storage):
    data = get_data(gather_args, model, dn_parent, storage)
    try:
        return data[gather_args["dn"]]
    except KeyError:
        if "default" in gather_args:
            return gather_args.get("default")
        raise InvalidModel(f"Missing data and default for source {model['source']['type']} with dn {dn_parent}")


def dn_lookup_loop(gather_args, model, dn_parent, storage):
    dn = gather_args["dn"]

    data = get_data(gather_args, model, dn_parent, storage)
    for i in yield_by_dn(data, dn):
        yield i


def dn_lookup(gather_args, model, dn_parent, storage):
    dn = gather_args["dn"]
    data = storage["input"][gather_args[KEY_GATHER]]

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

    dn = gather_args["path_to_target"] or gather_args["dn"]
    found, result = get_by_dn(data, dn)
    if found:
        return result
    return gather_args.get("default")


def key_lookup(gather_args, model, dn_parent, storage):
    if KEY_GATHER not in gather_args:
        return storage["context_data"].get(gather_args["key"])  # TODO set better debugging
    else:
        return storage["input"][gather_args[KEY_GATHER]].get(gather_args["dn"])


def loop_over(gather_args, model, dn_parent, storage):
    data = get_data(gather_args, model, dn_parent, storage)
    yield from data


def index(gather_args, model, dn_parent, storage):
    data = get_data(gather_args, model, dn_parent, storage)
    return data[gather_args["index"]]


def loop_by_dn_key(data_source, dn):
    found, data = get_by_dn(data_source=input_data, dn=dn)
    if found:
        yield from data.keys()
    else:
        yield from []


def is_list_dn(item):
    return item[0] == "[" and item[-1] == "]"


def get_index_num_from_list_dn(item):
    if len(item) == 2:
        return 0
    return int(item[1:item.find("]")])


def get_by_dn(data_source, dn):
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
    found, index = get_by_dn(data_source, dn)
    if found:
        yield from index
    else:
        yield from []


def iter_by_key(gather_args, model, dn_parent, storage):
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
        yield {item: buffer.get(item, {}).get(id_) for item in  items}


def iter_by_prop(gather_args, model, dn_parent, storage):
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
                if not index in buffer:
                    buffer[index] = {}
                buffer[index][key] = data

    for index, item in buffer.items():
        yield {**item, "id": index}


def generate_informations(index):
    all_values = index.split(".")
    group = ".".join(all_values[2:6])
    source = ".".join(all_values[7:11])
    return f"({source if source is not None else '*'},{group})"


def iter_by_prop2(gather_args, model, dn_parent, storage):
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
                if not index in buffer:
                    buffer[index] = {}
                buffer[index][key] = data

    for index, item in buffer.items():
        yield {**item, "id": generate_informations(index)}


def return_value(gather_args, model, dn_parent, storage):
    return gather_args["value"]

def yield_from(gather_args, model, dn_parent, storage):
    if "index" in gather_args:
        return storage["context_data"][gather_args["index"]]
    return storage["context_data"]



SOURCE_FUNC = {
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
    return False


def dict_key_is_empty(item, key):
    return not bool(item.get(key))


def not_cotains(item, arg):
    return arg not in item


FILTERS = {
    "dict_key_is_empty": dict_key_is_empty,
    "not_contains": not_cotains,
    "default": always_false,
}


def default_postformat(item, **kwargs):
    return item


def int_to_iso_timestamp(item, **kwargs):
    try:
        result = datetime.datetime.fromtimestamp(int(item) / 1e3).isoformat()
    except Exception:
        if kwargs.get("fail-silent"):
            result = item
        else:
            raise
    return result


def regex_to_iso_timestamp(item, **kwargs):
    re_format = kwargs.get("format")
    return datetime.datetime.strptime(item, re_format).isoformat()


def regex_search(item, **kwargs):
    regex = kwargs.get("regex")
    result = re.search(regex, item)
    if result is None:
        return kwargs.get("default")
    return result.group(0)


POSTFORMAT = {
    "default": default_postformat,
    "int_to_iso_timestamp": int_to_iso_timestamp,
    "regex_to_iso_timestamp": regex_to_iso_timestamp,
    "regex_search": regex_search,
}


def get_func_args_from_source(source, dn):
    try:
        source_type = source["type"]
    except KeyError:
        raise InvalidModel(f"Missing 'type' on source with dn {dn}")

    try:
        source_func = SOURCE_FUNC[source_type]
    except KeyError:
        raise InvalidModel(f"Missing source function on {source_type} on source with dn {dn}")

    try:
        filter_func = FILTERS.get(source.get("filter_type", "default"))  # TODO fail when filter is not present
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
            f"Missing post_format on {source_type} on source with dn {dn}, {postformat_name} not in available options {POST_FORMAT.keys()}"
        )

    return source_func, filter_func, {k: v for k, v in source.items() if k != "type" or k.startswith("filter_")}, source.get("filter_args", {}), postformat_func, postformat_args 


def gather_items(model, dn, storage):
    try:
        source = model[KEY_GATHER]
    except KeyError:
        raise InvalidModel(f"Missing 'source' on dn {dn}")
        return []

    gather_func, filter_func, gather_args, filter_args, postformat_func, postformat_args = get_func_args_from_source(source, dn)
    for item in gather_func(gather_args=gather_args, model=model, dn_parent=dn, storage=storage):
        if not filter_func(item, **filter_args):
            yield postformat_func(item, **postformat_args)


def gather_item(model, dn, storage):
    try:
        source = model[KEY_GATHER]
    except KeyError:
        raise InvalidModel(f"Missing 'source' on dn {dn}")
    gather_func, filter_func, gather_args, filter_args, postformat_func, postformat_args = get_func_args_from_source(source, dn)
    result = gather_func(gather_args=gather_args, model=model, dn_parent=dn, storage=storage)
    return postformat_func(result, **postformat_args)


def get_item_type(model, dn):
    try:
        return model["type"]
    except KeyError:
        raise InvalidModel(f"Missing 'type' on dn {dn}")


def init_item(model, dn):
    item_type = get_item_type(model, dn)
    item = DEFAULT_TYPE.get(item_type, lambda: None)()
    return item


def has_read_rights(model, role):
    if role is None:
        return True

    roles = model.get("rbac", {})
    return roles.get(role, {}).get("read") is True


def new_dn(dn, key):
    return dn + (key,)


def full_detail(model, dn=(), context_data=None, role=None, storage=None):
    item = init_item(model, dn)

    if model["type"] == "dict":
        for key, sub_model in model["nested"].items():
            if sub_model.get("skip"):
                continue
            if has_read_rights(sub_model, role):
                item[key] = full_detail(sub_model, new_dn(dn, key), role=role, storage=storage)

    elif model["type"] == "list":
        if "item" in model:
            sub_model = model["item"]
            for result in gather_items(model, dn, storage=storage):
                if has_read_rights(sub_model, role):
                    sub_item = init_item(sub_model, dn)
                    # TODO apply "item" logic
                    item.append(result)

        elif "items" in model:
            for result in gather_items(model, dn, storage=storage):
                p = []
                for i, sub_model in enumerate(model["items"]):
                    if has_read_rights(sub_model, role):
                        sub_item = init_item(sub_model, dn)
                        storage["context_data"] = result

                        result_i = gather_item(sub_model, dn, storage=storage)
                        # TODO apply "item" logic, and tests
                        #result_i = full_detail(sub_model, dn+("[]",), context_data=result, role=role, storage=storage)
                        p.append(result_i)

                item.append(p)

        elif "nested" in model:
            for partial_result in gather_items(model, dn, storage=storage):
                sub_item = {}
                for key, sub_model in model["nested"].items():
                    if has_read_rights(sub_model, role):
                        storage["context_data"] = partial_result
                        sub_item[key] = full_detail(sub_model,  new_dn(dn, key), role=role, storage=storage)
                item.append(sub_item)
        # item of default
        else:
            return item
    else:
        item = gather_item(model, dn, storage=storage)

    return item



def list_item(model, dn, value):
    item =  {
        "value": value,
        "dn": dn,
        "title": model.get("title"),
        "description": model.get("description"),
        "type": model["type"],
        "field_type": model.get("field_type"),
    }
    item.update(STORAGE[KEY_STORAGE_LIST_ITEM])
    return item

def list_node(model, dn, value):
    item =  {
        "_dn": dn,
        "_title": model.get("title"),
        "_description": model.get("description"),
        "_type": model["type"],
        "_field_type": model.get("field_type"),
    }
    item.update(STORAGE[KEY_STORAGE_LIST_ITEM])
    if type(value) == dict:
        item.update(value)
    else:
        item["value"] = value
    return item


def list_items(model, dn=(), context_data=None, role=None, storage=None):
    item = init_item(model, dn)
    if model["type"] == "dict":
        for key, sub_model in model["nested"].items():
            if sub_model.get("skip"):
                continue
            if has_read_rights(sub_model, role):
                yield from list_items(sub_model, new_dn(dn, key), role=role, storage=storage)

    elif model["type"] == "list":

        # list item contains single item
        if "item" in model:
            sub_model = model["item"]
            for result in gather_items(model, dn, storage=storage):
                if has_read_rights(sub_model, role):
                    sub_item = init_item(sub_model, dn)
                    # TODO apply "item" logic
                    yield list_item(sub_model, dn+("item",), result)

        # list contains multiple single items
        elif "items" in model:
            for result in gather_items(model, dn, storage=storage):
                for i, sub_model in enumerate(model["items"]):
                    if has_read_rights(sub_model, role):
                        sub_item = init_item(sub_model, dn)
                        # TODO apply "item" logic
                        storage["context_data"] = result
                        result_i = gather_item(sub_model, dn, storage=storage)
                        yield list_item(sub_model, dn+("item",), result_i)

        # list contains dict
        elif "nested" in model:
            for partial_result in gather_items(model, dn, storage=storage):
                for key, sub_model in model["nested"].items():
                    if has_read_rights(sub_model, role):
                        storage["context_data"] = partial_result
                        yield from list_items(sub_model,  new_dn(dn, key), role=role, storage=storage)
        # return default or initil item
        else:
            pass

    else:
        result = gather_item(model, dn, storage=storage)
        yield list_item(model=model, dn=dn, value=result)


def is_node(model):
    return model["type"] in ["dict", "list"] and all("nested" not in sub_model for sub_model in  model["nested"].values())


def list_nodes(model, dn=(), context_data=None, role=None, storage=None):
    item = init_item(model, dn)
    if model["type"] == "dict":
        if is_node(model):
            result = full_detail(model, dn, role=role, storage=storage)
            yield list_node(model=model, dn=dn, value=result)
        else:
            for key, sub_model in model["nested"].items():
                if sub_model.get("skip"):
                    continue

                if has_read_rights(sub_model, role):

                    yield from list_nodes(sub_model, new_dn(dn, key), role=role, storage=storage)

    elif model["type"] == "list":
        if is_node(model):
            result = full_detail(model, dn, role=role, storage=storage)
            for item in result:
                yield list_node(model=model, dn=dn, value=item)
        else:

            # list item contains single item
            if "item" in model:
                sub_model = model["item"]
                for result in gather_items(model, dn, storage=storage):
                    if has_read_rights(sub_model, role):
                        sub_item = init_item(sub_model, dn)
                        # TODO apply "item" logic
                        yield list_nodes(sub_model, dn+("item",), result)

            # list contains multiple single items
            elif "items" in model:
                for result in gather_items(model, dn, storage=storage):
                    for i, sub_model in enumerate(model["items"]):
                        if has_read_rights(sub_model, role):
                            sub_item = init_item(sub_model, dn)
                            # TODO apply "item" logic
                            storage["context_data"] = result
                            result_i = gather_item(sub_model, dn, storage=storage)
                            yield list_nodes(sub_model, dn+("item",), result_i)

            # list contains dict
            elif "nested" in model:
                for partial_result in gather_items(model, dn, storage=storage):
                    for key, sub_model in model["nested"].items():
                        if has_read_rights(sub_model, role):
                            storage["context_data"] = partial_result
                            yield from list_nodes(sub_model,  new_dn(dn, key), role=role, storage=storage)
            # return default or initil item
            else:
                pass

    else:
        result = gather_item(model, dn, storage=storage)
        yield list_node(model=model, dn=dn, value=result)


def list_item_config(model, dn):
    if "list_item" in model:
        return model["list_item"]
    return model


def has_list_item_config(model):
    return "standard" in model.get("nested", {}) or "common" in model.get("nested", {})


def run_list(model, role=None, **input_data):
    for k, v in input_data.items():
        STORAGE["input"][k] = v

    if has_list_item_config(model):
        common_key = "common" if "common" in model.get("nested", {}) else "standard"
        common_fields = full_detail(model["nested"][common_key], dn=(common_key, ), role=role, storage=STORAGE)
        STORAGE[KEY_STORAGE_LIST_ITEM] = {f"common_{key}": val for key, val in common_fields.items()}

    return list_items(model, role=role, storage=STORAGE)


def run_nodes(model, role=None, **input_data):
    for k, v in input_data.items():
        STORAGE["input"][k] = v

    if has_list_item_config(model):
        common_key = "common" if "common" in model.get("nested", {}) else "standard"
        common_fields = full_detail(model["nested"][common_key], dn=(common_key, ), role=role, storage=STORAGE)
        STORAGE[KEY_STORAGE_LIST_ITEM] = {f"common_{key}": val for key, val in common_fields.items()}

    return list_nodes(model, role=role, storage=STORAGE)


def rbac_views(l):
    return {i: {"read": True, "update": True, "create": True, "delete": True} for i in l}


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


if __name__ == "__main__":
    #input_model = json.load(open("inputs/dds/lb/example_input_LB_F5_2.json"))
    #dsm_model = json.load(open("dds/models/dds/lb/dsm_LB_F5_2_rbac1.json"))

    #result = dsm_looper(update_views_to_rbac, dsm_model)
    #esult = dsm_looper(remove_list_item, dsm_model)
    input_path = "inputs/dds/lb/example_input_LB_F5_2.json"
    dsm_path = "dds/models/dds/lb/dsm_LB_F5_2_rbac1.json"
    #result = run_detail_json(dsm_model, input=input_model)
    result = run_detail_json(dsm_path, input=input_path)
    #rint(json.dumps(result, indent=2))
    print(result)
    #list_item_data(dsm_model)
    #print(list_item_config)
