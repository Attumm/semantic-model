import json
import sys

from settipy import settipy

from semantic_model import dsm_looper


DN = []
DN_TO_MODEL = {}
PARENTS = {}


TYPE_TO_DJANGO = {
    "string": "CharField",
    "integer": "IntegerField",
    "int": "IntegerField",
    "float": "FloatField",
    "email": "EmailField",
    "bool": "BooleanField",  # NullBooleanField
    "date": "DateField",
    "datetime": "DateTimeField",
    "text": "TextField",
    "url": "URLField",
    "uuid": "UUIDField",
}


def type_to_django(model):
    type_ = model.get("type_field") or model.get("type")
    return TYPE_TO_DJANGO[type_]


def load_dns(model, dn):
    if len(dn) >= 1:
        DN.append(dn)
        DN_TO_MODEL[dn] = model
        if model["type"] in {"dict", "list"}:
            PARENTS[dn] = model
    return model


def create_parameters(dn):
    if dn[-1] == "id":
        return "primary_key=True"
    return "max_length=256" if DN_TO_MODEL[dn].get("type") == "string" else ""


def create_field(dn):
    return f"    {dn[-1]} = models.{type_to_django(DN_TO_MODEL[dn])}({create_parameters(dn)})  # {DN_TO_MODEL[dn]['type']}"


def create_admin_file(result):
    lines = []
    lines.append("from django.contrib import admin")
    lines.append("")

    for dn in PARENTS:
        lines.append(f"from .models import {dn[-1]}")

    lines.append("")
    for dn in PARENTS:
        lines.append(f"admin.site.register({dn[-1]})")

    return lines


def create_model_file(result):
    lines = []
    lines.append("from django.db import models")

    for dn in DN:
        if dn in PARENTS:
            lines.append("")
            lines.append("")
            lines.append(f"class {dn[-1]}(models.Model):")
        else:
            lines.append(create_field(dn))
    return lines


def create_serializer_file(result):
    lines = []
    lines.append("from .models import *")
    lines.append("from rest_framework import serializers")

    first_round = True
    for dn in DN:
        if dn in PARENTS:
            if not first_round:
                lines.append("         ]")
                lines.append("")
                lines.append("")
            lines.append("")
            lines.append("")
            lines.append(f"class {dn[-1]}Serializer(serializers.HyperlinkedModelSerializer):")
            lines.append("    class Meta:")
            lines.append(f"        model = {dn[-1]}")
            lines.append("        fields = [")
        else:
            lines.append(f"            '{dn[-1]}', ")
        first_round = False

    lines.append("         ]")
    lines.append("")
    lines.append("")

    return lines


def create_views_file(result):
    lines = []
    lines.append("from django.contrib import admin")
    lines.append("from rest_framework import viewsets")
    lines.append("from rest_framework import permissions")
    lines.append("from .serializers import *")
    lines.append("")

    lines.append("from .models import *")
    lines.append("")
    lines.append("")

    for dn in PARENTS:
        lines.append(f"class {dn[-1]}ViewSet(viewsets.ModelViewSet):")
        lines.append(f"     queryset = {dn[-1]}.objects.all()")
        lines.append(f"     serializer_class = {dn[-1]}Serializer")
        lines.append("")
        lines.append("")

    return lines


def create_urls_file(results):
    lines = []
    lines.append("from django.urls import include, path")
    lines.append("from rest_framework import routers")
    lines.append("from .views import *")
    lines.append("")
    lines.append("")

    lines.append("router = routers.DefaultRouter()")

    for dn in PARENTS:
        lines.append(f"router.register(r'{dn[-1]}', {dn[-1]}ViewSet)")

    lines.append("")
    lines.append("urlpatterns = [")
    lines.append("    path('', include(router.urls)),")
    lines.append("    path('api-auth/', include('rest_framework.urls', namespace='rest_framework'))")
    lines.append("]")

    return lines


if __name__ == "__main__":
    MODE = {
        "admin": create_admin_file,
        "model": create_model_file,

        "urls": create_urls_file,
        "serializer": create_serializer_file,
        "views": create_views_file,
    }
    settipy.set("mode", "model", f"set the mode options: {list(MODE.keys())}", options=list(MODE.keys()))
    settipy.set("input", "", "path to input json file. example: ./example.json")
    settipy.parse()

    if settipy.get("input"):
        dsm_model = json.load(open(settipy.get("input")))
    else:
        data = sys.stdin.read()
        dsm_model = json.loads(data)

    result = dsm_looper(load_dns, dsm_model)

    lines = MODE[settipy.get("mode")](result)
    for i in lines:
        print(i)
