# semantic-model

> **All data about data in one model.** A DSM (Data Semantic Model) is a single
> JSON document that describes the structure, types, validators, relations,
> access rights and data sources of your data. From that one definition you can
> **validate** input, **generate** several runtime views (detail / list / node),
> and **scaffold** code for different target systems (Django + DRF, Graphviz
> diagrams) — without repeating yourself.

The model is the single source of truth. The same definition that validates a
payload is the one that produces a Django `models.py`, a DRF `serializers.py`,
and a visual graph of the data.

---

## Table of contents

- [Why](#why)
- [Install](#install)
- [Quick start](#quick-start)
- [The model — a single source of truth](#the-model--a-single-source-of-truth)
- [Validation](#validation)
- [Generating output for different systems](#generating-output-for-different-systems)
  - [Runtime views: detail / list / node](#runtime-views-detail--list--node)
  - [Code generation: Django / DRF](#code-generation-django--drf)
  - [Code generation: Graphviz diagrams](#code-generation-graphviz-diagrams)
  - [Bootstrapping a model from sample data](#bootstrapping-a-model-from-sample-data)
- [Model reference](#model-reference)
- [Extending](#extending)
- [Project layout](#project-layout)
- [Testing](#testing)
- [License](#license)

---

## Why

Most data plumbing is written three or more times: once to validate, once to
serialise for an API, once to map onto a database schema, again for docs, etc.
Every copy drifts. `semantic-model` replaces those copies with **one model**:

```
                      ┌─────────────┐
   sample data  ──▶   │  one_to_one  │──┐
                      └─────────────┘  │
                                       ▼
                              ┌────────────────┐
                              │  the DSM model  │  (one JSON file)
                              └────────────────┘
                  validate │  │  │  │  │  generate
            ───────────────┘  │  │  │  └──────────────
              ▼               ▼  ▼  ▼                 ▼
          detail           list  node            Django/DRF   Graphviz
        (nested JSON)   (flat rows) (meta rows)   (code files)   (DOT)
```

- Define the shape **once**.
- The engine **validates** structure, types, semantic field types, filters and
  access rights as it runs.
- The same model is walked to **emit** views or **generate** code for whichever
  target system you need.

## Install

```sh
pip install semantic-model
```

> The package depends on [`settipy`](https://pypi.org/project/settipy/) for CLI
> argument parsing. `one_to_one` additionally uses `python-dateutil` when
> available (it degrades gracefully if not installed).

## Quick start

```sh
# 1. Bootstrap an initial model from a sample JSON payload
python3 -m semantic_model -mode one_to_one -input example.json > sm_model.json

# 2. Run the model against data (default action = "detail")
python3 -m semantic_model -input example.json -sm sm_model.json

# 3. Render the model itself as a PNG (uses the bundled Docker image)
sudo docker run -i attumm/dsm_png:latest < sm_model.json > output.png
```

Other modes: `-mode list`, `-mode nodes`, `-mode detail` (default), `-mode help`.

---

## The model — a single source of truth

A DSM model is plain JSON. A small example:

```json
{
  "title": "Person View",
  "type": "dict",
  "description": "A single person record.",
  "rbac": { "admin": {"read": true, "create": true}, "user": {"read": true} },
  "nested": {
    "name": {
      "title": "Name",
      "type": "string",
      "source": { "type": "json_key_item", "source": "input", "dn": "NAME" },
      "example": "Bob"
    },
    "age": {
      "title": "Age",
      "type": "integer",
      "field_type": "integer",
      "skip": true,
      "source": { "type": "json_key_item", "source": "input", "dn": "_AGE" }
    }
  }
}
```

Every node carries:

| key          | meaning                                                                 |
|--------------|-------------------------------------------------------------------------|
| `type`       | `dict`, `list`, `string`, `integer`, `boolean` (structural type)       |
| `field_type` | semantic type: `URL`, `email`, `ipv4`, `ipv6`, `geopoint`, `float`, …   |
| `title`      | human-readable label                                                    |
| `description`| free-text explanation                                                   |
| `example`    | sample value                                                            |
| `default`    | value used when the source has none                                     |
| `source`     | how/where to gather the value (see [Model reference](#model-reference)) |
| `postformat` | a transform applied after gathering (regex, timestamp, …)              |
| `filter_type`| a predicate that drops gathered values (`contains`, `not_contains`, …) |
| `rbac`       | per-role read/create/update/delete rights                              |
| `nested`     | children for `dict` (and list-of-dict) nodes                            |
| `item`/`items` | child(ren) for `list` nodes                                           |
| `skip`       | omit this node from output                                              |
| `relation`   | link to another node                                                    |

`dict` nodes recurse into `nested`. `list` nodes come in three flavours:

- `item`   → a list of one repeated scalar/object shape
- `items`  → a list of several different shapes (positional)
- `nested` → a list of dicts (each key is a sub-model)

---

## Validation

Validation is built into the engine rather than a separate step — every run is
a validation pass. It happens at several layers:

### 1. Model structure validation

The model itself is checked while it runs. The engine raises
`InvalidModel` (`semantic_model.InvalidModel`) for:

- a node with no `type` (`get_item_type`)
- a node with a `source` but no `type` on that source (`get_func_args_from_source`)
- an unknown `source.type` (not in `SOURCE_FUNC`)
- an unknown `postformat.type` (not in `POSTFORMAT`)
- a missing `dn`/`path_to_target` on a source that needs it
- a `json_key_item` source whose key is absent **and** has no `default`

```python
from semantic_model import run_detail, InvalidModel

try:
    run_detail(broken_model, input=data)
except InvalidModel as e:
    print("model is invalid:", e)
```

### 2. Type validation

Every leaf declares a `type` (`string`/`integer`/`boolean`/`dict`/`list`).
`get_item_type` / `init_item` use it to build the correctly-typed result, and
reject nodes whose `type` is missing or wrong.

### 3. Semantic field-type validation

`field_type` declares the *shape* of a value, not just its Python type:
`URL`, `email`, `ipv4`, `ipv6`, `geopoint`, `float`, `text`, `iso_timestamp`,
etc. `one_to_one` auto-detects these from sample data using a built-in regex
catalogue (`data.regexes`), so a field holding an email is recognised as
`email` rather than a bare `string`.

### 4. Postformat transform & validate

A `source.postformat` block transforms a gathered value and can supply a
fallback. `regex_search` returns `default` when the pattern does not match,
which is a coercive form of validation:

```json
"source": {
  "type": "index", "index": 0,
  "postformat": { "type": "regex_search", "regex": "(\\d+)", "default": "NaN" }
}
```

Built-in postformats: `default`, `int_to_iso_timestamp`,
`regex_to_iso_timestamp`, `regex_search`, `hash_uuid`,
`format_dict_to_key_list`.

### 5. Filter predicates

`filter_type` drops values that fail a predicate during gathering:
`contains`, `not_contains`, `dict_key_is_empty` (default = accept all).

### 6. Access validation (RBAC)

Each node may carry an `rbac` map of role → rights
(`read`/`create`/`update`/`delete`). Pass `roles=[...]` to any `run_*`
function and nodes without the `read` right for any supplied role are omitted.
`has_read_rights` is the per-node check; `update_views_to_rbac` converts a
legacy `views` list into an `rbac` map.

---

## Generating output for different systems

This is the core idea: **one model → many outputs**. The outputs split into two
families — runtime *views* produced by the engine, and *generated code/diagrams*
produced by walking the model with `dsm_looper`.

### Runtime views: detail / list / node

All three take the same model and the same input, returning different shapes:

| action   | entry point / CLI `-mode` | shape of each item                                            |
|----------|---------------------------|---------------------------------------------------------------|
| `detail` | `run_detail` / `detail`    | fully nested object mirroring the model                       |
| `list`   | `run_list`   / `list`     | one flat row per leaf: `value, dn, title, description, type, field_type, searchable` |
| `node`   | `run_nodes`  / `nodes`    | one row per node with `_dn`, `__columns`, and per-column metadata (`_<key>_dn`, `_<key>_type`, `_<key>_rbac_*`) |

```python
from semantic_model import run_detail, run_list, run_nodes

run_detail(model, input=data)            # nested dict/list
list(run_list(model, input=data))        # flat rows
list(run_nodes(model, input=data))       # node rows with metadata
```

There are also JSON-file helpers that load the model and input from paths:
`run_detail_json`, `run_list_json`, `run_node_json`, and the dispatcher
`run_with_json(action, model_path, roles=..., input=...)`.

### Code generation: Django / DRF

`extras/sm_to_django.py` walks the model with `dsm_looper` and emits a full
Django REST Framework scaffold from the **same** definition:

```sh
python3 extras/sm_to_django.py -mode model      < sm_model.json   # models.py
python3 extras/sm_to_django.py -mode serializer < sm_model.json   # serializers.py
python3 extras/sm_to_django.py -mode views      < sm_model.json   # views.py
python3 extras/sm_to_django.py -mode urls       < sm_model.json   # urls.py
python3 extras/sm_to_django.py -mode admin      < sm_model.json   # admin.py
```

`TYPE_TO_DJANGO` maps each DSM `type`/`field_type` to a Django field
(`string→CharField`, `email→EmailField`, `url→URLField`, `integer→IntegerField`,
…). Each `dict`/`list` node becomes a `models.Model` class; leaves become
fields. `-mode` selects which file to emit (read the model from a file with
`-input path.json` or from stdin).

### Code generation: Graphviz diagrams

`extras/sm_to_graph.py` walks the model and emits a Graphviz `digraph` of the
Distinguished Names (DNs), colouring by depth:

```sh
python3 extras/sm_to_graph.py < sm_model.json > model.dot
dot -Tpng model.dot > model.png
```

### Bootstrapping a model from sample data

`one_to_one.py` goes the other direction: give it a sample payload and it
produces a starter DSM model, inferring types and semantic field types:

```sh
python3 -m semantic_model -mode one_to_one -input example.json > sm_model.json
# or pipe directly:
cat example.json | python3 one_to_one.py > sm_model.json
```

`identify()` matches each value against the regex catalogue; `str_type()`
maps Python types to DSM types; `TYPE_FIELD` promotes recognised values to
semantic field types (`URL`, `ipv6`, `email`, `ipv4`, `geopoint`). `CONFIG`
flags (`skip_description`, `skip_source`) tune the output. The produced model
is then refined by hand and reused for every other output.

---

## Model reference

### `source` types (how a value is gathered)

| `source.type`     | behaviour                                                        |
|-------------------|------------------------------------------------------------------|
| `json_key`        | read a key from a named storage; `multi: true` yields all items |
| `json_key_item`   | read a single key (raises `InvalidModel` if missing & no default) |
| `dn_lookup`       | dot-path lookup `a.b.c` (supports `[i]` list indices)           |
| `dn_lookup_loop`  | like `dn_lookup` but yields each element                        |
| `key_lookup`      | look up a `key`/`dn` in input or context_data                   |
| `iter_by_key`     | N(1) join across a list of dicts by key                          |
| `iter_by_prop`    | join list-of-lists by an id, emitting `{...fields, "id": ...}`  |
| `iter_by_prop2`   | like `iter_by_prop` with a generated information id              |
| `loop_over`       | yield every element of the source                                |
| `index`           | pick `source[index]`                                             |
| `return_value`    | return a literal `value`                                         |
| `get_from_source` / `get_from_input_file` | resolve a `dn`/`path_to_target` or return `default` |
| `yield`           | yield from `context_data` (optionally by `index`)               |

### Distinguished Names (DN)

DNs are dot-paths that locate a value inside a data source, e.g.
`input_data.foo.bar.apple` or `items.[0].values`. `get_by_dn` resolves them
(supporting `[i]` list indexing); `yield_by_dn` yields each element at a DN.
`new_dn(dn, key)` appends a segment as a tuple.

### `postformat` types

`default`, `int_to_iso_timestamp`, `regex_to_iso_timestamp`, `regex_search`,
`hash_uuid` (deterministic UUID5), `format_dict_to_key_list`.

### `filter_type` predicates

`contains`, `not_contains`, `dict_key_is_empty`, `default` (accept all).

---

## Extending

Add custom postformats by registering into the dispatch tables before running:

```python
from semantic_model import POSTFORMAT, SOURCE_FUNC, FILTERS

def strip(item, **kwargs):
    return item.strip()

POSTFORMAT["strip"] = strip
```

The same pattern works for `SOURCE_FUNC` (custom `source.type` handlers) and
`FILTERS` (custom `filter_type` predicates). Every handler has the signature
`(item, **kwargs)` for postformats/filters, or
`(gather_args, model, dn_parent, storage)` for source functions.

---

## Project layout

```
semantic_model.py     Core engine: model walker, sources, postformats,
                       filters, RBAC, and the detail/list/node actions.
one_to_one.py         Bootstrap a starter model from sample data.
data.py               Built-in regex catalogue + descriptions used by
                       one_to_one for semantic type detection.
extras/
  sm_to_django.py      Generate Django + DRF files from a model.
  sm_to_graph.py       Generate a Graphviz digraph from a model.
tests/
  tests.py             Engine tests (detail/list/nodes, sources, RBAC, …).
  one_to_one_tests.py  Model-bootstrapping tests.
setup.py               Packaging (semantic-model, MIT).
```

## Testing

```sh
python3 -m unittest discover tests/
```

`automatic_tests.sh` re-runs the suite on every file change (requires `entr`).

## License

MIT — see `LICENSE`.
