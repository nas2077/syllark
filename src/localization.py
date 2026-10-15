"""Shared local catalogs for human-readable exports and native error dialogs."""
import json
import os
import re
import sys
from functools import lru_cache

HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))


@lru_cache(maxsize=1)
def catalogs():
    base = os.path.join(HERE, "locales")
    with open(os.path.join(base, "languages.json"), encoding="utf-8") as f:
        languages = json.load(f)
    result = {}
    for language in languages:
        with open(os.path.join(base, language["code"] + ".json"), encoding="utf-8") as f:
            result[language["code"]] = json.load(f)
    return result


def normalize(code):
    available = catalogs()
    if code in available:
        return code
    base = str(code or "").replace("_", "-").split("-")[0].lower()
    return next((c for c in available if c.lower().split("-")[0] == base), "en")


def translate(key, locale="en", **params):
    text = catalogs()[normalize(locale)].get(key, key)
    return re.sub(r"\{(\w+)\}", lambda m: str(params.get(m[1], m[0])), text)


@lru_cache(maxsize=1)
def metadata_labels():
    labels = {}
    for catalog in catalogs().values():
        for key in ("date", "duration", "language", "link"):
            labels[catalog[key]] = key
            labels[key] = key
    return labels


@lru_cache(maxsize=1)
def silence_labels():
    return {c["(no speech)"] for c in catalogs().values()} | {"(no speech)"}
