"""Golden/shape tests for the code generators in ``extras/``.

The whole point of semantic-model is that *one* model definition yields output
for *different systems*. These tests pin the shape of the Django/DRF scaffold
and the Graphviz digraph so the generators don't silently drift.
"""
import importlib.util
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None  # type guard for type-checkers
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DJANGO_PATH = os.path.join(os.path.dirname(__file__), "..", "extras", "sm_to_django.py")
GRAPH_PATH = os.path.join(os.path.dirname(__file__), "..", "extras", "sm_to_graph.py")


def _person_model():
    """A small model with one dict parent (becomes a Django model) and leaves."""
    return {
        "type": "dict",
        "nested": {
            "person": {
                "type": "dict",
                "nested": {
                    "name": {"type": "string", "field_type": "text"},
                    "age": {"type": "integer"},
                    "id": {"type": "integer"},
                },
            },
        },
    }


class DjangoGenTestBase(unittest.TestCase):
    def setUp(self):
        self.dj = load_module("sm_to_django_under_test", os.path.abspath(DJANGO_PATH))
        # each generator run mutates module-level state; reset it each time
        self.dj.DN = []  # type: ignore[attr-defined]
        self.dj.DN_TO_MODEL = {}  # type: ignore[attr-defined]
        self.dj.PARENTS = {}  # type: ignore[attr-defined]
        self.dj.dsm_looper(self.dj.load_dns, json.loads(json.dumps(_person_model())))


class TestTypeToDjango(unittest.TestCase):
    def setUp(self):
        self.dj = load_module("sm_to_django_types", os.path.abspath(DJANGO_PATH))

    def test_known_mappings(self):
        expected = {
            "string": "CharField",
            "integer": "IntegerField",
            "int": "IntegerField",
            "float": "FloatField",
            "email": "EmailField",
            "bool": "BooleanField",
            "date": "DateField",
            "datetime": "DateTimeField",
            "text": "TextField",
            "url": "URLField",
            "uuid": "UUIDField",
        }
        for dsm_type, django_field in expected.items():
            self.assertEqual(self.dj.TYPE_TO_DJANGO[dsm_type], django_field)

    def test_type_to_django_prefers_type_field(self):
        self.assertEqual(
            self.dj.type_to_django({"type_field": "email", "type": "string"}),
            "EmailField",
        )

    def test_type_to_django_falls_back_to_type(self):
        self.assertEqual(self.dj.type_to_django({"type": "integer"}), "IntegerField")


class TestDjangoModelFile(DjangoGenTestBase):
    def test_emits_model_class_with_fields(self):
        lines = self.dj.create_model_file(None)
        text = "\n".join(lines)
        self.assertIn("from django.db import models", text)
        self.assertIn("class person(models.Model):", text)
        # leaves become fields with the right Django type and trailing dsm-type comment
        self.assertIn("name = models.CharField(max_length=256)  # string", text)
        self.assertIn("age = models.IntegerField()  # integer", text)
        # id is a primary key
        self.assertIn("id = models.IntegerField(primary_key=True)  # integer", text)

    def test_field_lines_are_indented_members(self):
        lines = self.dj.create_model_file(None)
        field_lines = [line for line in lines if "=" in line and "models." in line]
        for line in field_lines:
            self.assertTrue(line.startswith("    "), f"field not indented: {line!r}")


class TestDjangoParameters(unittest.TestCase):
    def setUp(self):
        self.dj = load_module("sm_to_django_params", os.path.abspath(DJANGO_PATH))
        self.dj.DN = []  # type: ignore[attr-defined]
        self.dj.DN_TO_MODEL = {}  # type: ignore[attr-defined]
        self.dj.PARENTS = {}  # type: ignore[attr-defined]
        self.dj.dsm_looper(self.dj.load_dns, json.loads(json.dumps(_person_model())))

    def test_id_is_primary_key(self):
        self.assertEqual(self.dj.create_parameters(("person", "id")), "primary_key=True")

    def test_string_gets_max_length(self):
        self.assertEqual(self.dj.create_parameters(("person", "name")), "max_length=256")


class TestDjangoAdminFile(DjangoGenTestBase):
    def test_admin_imports_and_registers(self):
        lines = self.dj.create_admin_file(None)
        text = "\n".join(lines)
        self.assertIn("from django.contrib import admin", text)
        self.assertIn("from .models import person", text)
        self.assertIn("admin.site.register(person)", text)


class TestDjangoSerializerFile(DjangoGenTestBase):
    def test_serializer_shape(self):
        lines = self.dj.create_serializer_file(None)
        text = "\n".join(lines)
        self.assertIn("from rest_framework import serializers", text)
        self.assertIn("class personSerializer(serializers.HyperlinkedModelSerializer):", text)
        self.assertIn("model = person", text)
        # leaves are listed in the fields array
        self.assertIn("'name'", text)
        self.assertIn("'age'", text)
        self.assertIn("'id'", text)


class TestDjangoViewsFile(DjangoGenTestBase):
    def test_views_shape(self):
        lines = self.dj.create_views_file(None)
        text = "\n".join(lines)
        self.assertIn("from rest_framework import viewsets", text)
        self.assertIn("class personViewSet(viewsets.ModelViewSet):", text)
        self.assertIn("queryset = person.objects.all()", text)
        self.assertIn("serializer_class = personSerializer", text)


class TestDjangoUrlsFile(DjangoGenTestBase):
    def test_urls_shape(self):
        lines = self.dj.create_urls_file(None)
        text = "\n".join(lines)
        self.assertIn("from rest_framework import routers", text)
        self.assertIn("router = routers.DefaultRouter()", text)
        self.assertIn("router.register(r'person', personViewSet)", text)
        self.assertIn("path('', include(router.urls))", text)


class TestSmToGraph(unittest.TestCase):
    def setUp(self):
        self.g = load_module("sm_to_graph_under_test", os.path.abspath(GRAPH_PATH))
        self.model = {
            "type": "dict",
            "nested": {
                "person": {
                    "type": "dict",
                    "nested": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                    },
                },
            },
        }

    def _run(self, model):
        # the generator reads the model from stdin in __main__
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
        import subprocess
        proc = subprocess.run(
            [sys.executable, os.path.abspath(GRAPH_PATH)],
            input=json.dumps(model), capture_output=True, text=True, env=env,
        )
        return proc

    def test_emits_digraph(self):
        proc = self._run(self.model)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        out = proc.stdout
        self.assertTrue(out.startswith("digraph G {"), out)
        self.assertTrue(out.rstrip().endswith("}"), out)

    def test_has_one_node_per_dn(self):
        proc = self._run(self.model)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        # DN line lists every visited dn; person + 2 leaves = 3 entries
        dn_line = [line for line in proc.stdout.splitlines() if line.startswith("DN:")][0]
        self.assertIn("('person',)", dn_line)
        self.assertIn("('person', 'name')", dn_line)
        self.assertIn("('person', 'age')", dn_line)
        # each non-root DN gets a labelled node declaration
        label_lines = [line for line in proc.stdout.splitlines() if 'label="' in line]
        self.assertEqual(len(label_lines), 3)

    def test_get_color_is_cyclic(self):
        colors = self.g.COLORS
        for i in range(len(colors) * 2):
            depth = i + 1
            self.assertEqual(self.g.get_color([0] * depth), colors[depth % len(colors)])


if __name__ == "__main__":
    unittest.main()
