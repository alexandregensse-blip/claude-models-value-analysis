"""Reads the catalogue of data/catalog/ (JSON): what the data file needs to be read correctly. Pure standard library;
used by the model (model/lqm.py) and by the site (site/build.py). Each file is described in data/README.md.

MODELS         {model: {label, colour, flag_task_size?}}; MODEL_ORDER (fit and grids), DISPLAY_ORDER (legend)
FAMILIES       {family: [groups]} — groups that run the same benchmark (same task set, version, grading); FAMILY_OF
PUBLISHER_OF   {source: publisher} — outlets of one organisation publishing its own measurements
COMPOSITES     {group: [component groups]} — an index and what it aggregates, as its publisher documents it
UNIT_ALIASES   {source: {label: unit}} — two labels a publisher uses for one cost unit
GROUP_DISPLAY  {group: (label, type, verified configuration)} and GROUP_MERGE {group: group} — sources table
"""
import json, os

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog")


def _load(name):
    with open(os.path.join(HERE, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


_m = _load("models")
MODELS, MODEL_ORDER, DISPLAY_ORDER = _m["models"], _m["order"], _m["display_order"]
FAMILIES = _load("families")
FAMILY_OF = {g: f for f, gs in FAMILIES.items() for g in gs}
PUBLISHER_OF = _load("publishers")
COMPOSITES = {g: v["components"] for g, v in _load("composites").items()}
UNIT_ALIASES = _load("unit_aliases")
_g = _load("groups")
GROUP_DISPLAY = {g: (v["label"], v["type"], v["config"]) for g, v in _g["display"].items()}
GROUP_MERGE = _g["merge"]
FILES = [os.path.join("data", "catalog", n) for n in sorted(os.listdir(HERE)) if n.endswith(".json")]
