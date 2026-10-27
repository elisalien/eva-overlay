#!/usr/bin/env python3
"""Build the EVA-Responsive Wire source (portrait-ready fork of EVA Overlay).

Six text fields typed in Arena (String In, " / " = line break) go through Replace and
Text Render into EVA_Responsive.isf, which measures the rendered lines and lays them out
in nine Evangelion style interface presets. The label atlas (eva_atlas.png, made by
build_atlas.py) feeds the "atlas" image input. The clock is accumulated in the patch
(seconds and beats since the last "Recommencer"), so a preset always starts from its intro.

The .wire is derived from template/base.wire, a patch made by hand in Wire: the ISF node,
the image, the output, the clock nodes (Transport Time, System Time, Derivative, Clamp,
Accumulate) and one slider and one dropdown used as templates for the dashboard. The
String In, Replace, Length, Text Render and Trigger In nodes are written from scratch below.
Run build_atlas.py first when the atlas words change, then this script after any change
to the shader inputs. Never save the patch from Wire: Arena finds it by its identifier,
which this script always writes (uuid5 of "vj/wire/EVA-Responsive").

  python build_wire.py                  -> ~/Documents/Resolume Wire/Patches/EVA-Responsive
  python build_wire.py --patches DIR    -> DIR/EVA-Responsive (Documents moved, OneDrive...)
"""
import argparse
import copy
import json
import shutil
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template" / "base.wire"
PATCHES = Path.home() / "Documents" / "Resolume Wire" / "Patches"

NAME = "EVA-Responsive"
PATCH_DIR = PATCHES / NAME
SHADER = "EVA_Responsive.isf"
ATLAS = "eva_atlas.png"
# Node ids in template/base.wire.
ISF_NODE, IMAGE_NODE = "0", "1"
FLOAT_TEMPLATE, CHOICE_TEMPLATE = "5", "3"

# Text Render settings per field. The shader re-lays out every line, so the render only
# has to be big and sharp: titles render in 4K. EXTRA line spacing keeps the lines apart
# so the shader can find them (banc.html uses the same values).
EXTRA = 40
FIELDS = [
    # label, default text, font, style, scale, 4K, line width
    ("Titre", "ANGEL / ATTACK", "Noto Serif CJK JP", "Black", 2.0, True, 3600),
    ("Sous-titre", "NEON GENESIS", "Shippori Mincho B1", "ExtraBold", 0.9, False, 1800),
    ("Kanji", "獏 / 宇宙人", "Noto Serif CJK JP", "Black", 2.0, True, 3600),
    ("Label", "EPISODE:1", "Yu Gothic", "Bold", 0.9, False, 1800),
    ("Infos", "CODE 601 / BLOOD TYPE : BLUE / TARGET 3RD ANGEL", "Yu Gothic", "Bold", 0.6, False, 1700),
    ("Bandeau", "EMERGENCY", "Bahnschrift", "Bold Condensed", 0.9, False, 1800),
]

GROUPS = [
    ("Presets", ["preset", "cycle", "clockMode", "duree", "transition", "transDur", "replay", "@Recommencer"]),
    ("Mise en page", ["margin", "fill", "stretch", "justify", "leading", "orient"]),
    ("Animation", ["speed", "entree", "sortie", "stagger", "blink", "glitch", "timerMin", "seed"]),
    ("Rendu", ["palette", "bgMode", "uiAmt", "opacity", "glowAmt", "scan", "grain", "chroma"]),
    ("Audio", ["pulse", "level"]),
]
LABELS = {
    "preset": "Preset", "cycle": "Défilement", "clockMode": "Horloge", "duree": "Durée (s / temps)",
    "transition": "Transition", "transDur": "Durée transition", "replay": "Rejouer si texte change",
    "margin": "Marge", "fill": "Taille texte", "stretch": "Étirement", "justify": "Alignement",
    "leading": "Interligne", "orient": "Orientation",
    "speed": "Vitesse", "entree": "Entrée", "sortie": "Sortie", "stagger": "Décalage lignes",
    "blink": "Clignotement", "glitch": "Glitch", "timerMin": "Compte à rebours (min)", "seed": "Graine",
    "palette": "Palette", "bgMode": "Fond", "uiAmt": "Interface", "opacity": "Opacité", "glowAmt": "Lueur",
    "scan": "Scanlines", "grain": "Grain", "chroma": "Aberration",
    "pulse": "Pulse", "level": "Niveau",
}
OPTION_LABELS = {
    "preset": ["Carte titre", "Alerte", "MAGI", "Sound Only", "Synchro", "Activité", "Pattern Blue", "Bandeau", "Terminal"],
    "cycle": ["Fixe", "Auto", "Aléatoire"],
    "entree": ["Auto", "Coupe", "Frappe", "Décodage", "Balayage", "Clignotement"],
    "palette": ["Auto", "NERV Orange", "Alerte Rouge", "MAGI Vert", "Pattern Bleu", "Unité-01", "Unité-02", "Unité-00", "Blanc Titre"],
    "replay": ["Non", "Oui"],
}
HIDDEN_SHADER = {f"len{k}" for k in range(6)} | {"tBeat", "tSec"}

STRING_IN = "77697265-F29F-45E9-A833-21E09C750BA7"
REPLACE = "77697265-5852-44AB-89e5-F52a24ca2d50"
LENGTH = "77697265-5f58-4439-9a96-809989a9e66e"
TEXT_RENDER = "77697265-E2EC-4F1B-901A-CEFC474D3C07"
TRIGGER_IN = "77697265-e61f-42c0-862a-0dca04e14569"


def attr(t, v):
    return {"type": t, "value": v}


def node(cls, version, name, x, y, attributes, constants, hidden, h=58, w=195):
    return {"attributes": attributes, "bounds": {"height": h, "width": w, "x": x, "y": y},
            "class": {"id": cls, "version": version}, "clock": "video", "color": "ffff6a00",
            "constants": constants, "hidden": hidden, "name": name, "thumbnail_visible": True}


def string_in(name, text, x, y):
    return node(STRING_IN, 3, name, x, y,
                {"flow": attr("flow", "signal"), "instances": attr("integer", 1),
                 "options-count": attr("integer", 0), "widget": attr("integer", 0)},
                {"input": attr("string", text)},
                ["flow", "input", "instances", "options-count", "widget"], h=82, w=130)


def replace_node(x, y):
    return node(REPLACE, 2, "Retour à la ligne", x, y,
                {"flow": attr("flow", "signal"), "input-dimensions": attr("integer", 1),
                 "match-dimensions": attr("integer", 1), "mode": attr("integer", 0),
                 "replace-dimensions": attr("integer", 1)},
                {"input": attr("string", ""), "match": attr("string", " / "), "replace": attr("string", "\n")},
                ["flow", "input-dimensions", "match-dimensions", "mode", "replace-dimensions"], h=82)


def length_node(x, y):
    return node(LENGTH, 2, "Length", x, y,
                {"flow": attr("flow", "signal"), "instances": attr("integer", 1)},
                {"input0": attr("string", "")}, ["flow", "instances"], h=30)


def text_render(name, font, style, scale, uhd, linewidth, x, y):
    dims = ["alignment", "alignmentvert", "bypass", "glowin", "glowout", "input", "linewidth",
            "material", "outlinecolor", "outlinewidth", "position", "rotation", "scale", "spacing"]
    attributes = {f"{d}-dimensions": attr("integer", 1) for d in dims}
    attributes.update({
        "bitdepth": attr("integer", 0), "font": attr("string", font), "reduce": attr("bool", False),
        "resolution-absolute": attr("float2", [3840, 2160] if uhd else [1920, 1080]),
        "resolution-mode": attr("integer", 1),
        "resolution-relative": attr("float2", [1, 1]), "style": attr("string", style),
    })
    constants = {
        "alignment": attr("integer", 1), "alignmentvert": attr("integer", 1), "bypass": attr("bool", False),
        "glowin": attr("float", 0), "glowout": attr("float", 0), "input": attr("string", ""),
        "linewidth": attr("float", linewidth), "material": attr("color", [1, 1, 1, 1]),
        "outlinecolor": attr("color", [1, 0, 0, 1]), "outlinewidth": attr("float", 0),
        "position": attr("float2", [0, 0]), "rotation": attr("float", 0), "scale": attr("float", scale),
        "spacing": attr("float2", [0, EXTRA]),
    }
    hidden = sorted([f"{d}-dimensions" for d in dims] + [
        "bitdepth", "bypass", "glowin", "glowout", "outlinecolor", "outlinewidth",
        "reduce", "resolution-relative", "rotation"])
    return node(TEXT_RENDER, 5, name, x, y, attributes, constants, hidden, h=226)


def trigger_in(name, x, y):
    return node(TRIGGER_IN, 1, name, x, y,
                {"flow": attr("flow", "event"), "instances": attr("integer", 1)},
                {"input": attr("trigger", None)}, ["flow", "input", "instances"], h=82, w=130)


def float_in(tpl, name, lo, hi, value, x, y):
    n = copy.deepcopy(tpl)
    n["attributes"]["min"]["value"], n["attributes"]["max"]["value"] = lo, hi
    n["constants"]["input"]["value"] = value
    n["name"] = name
    n["bounds"].update(x=x, y=y)
    return n


def choice_in(tpl, name, labels, values, default, x, y):
    n = copy.deepcopy(tpl)
    attrs = {k: v for k, v in n["attributes"].items() if not k.startswith("option")}
    for k, (label, value) in enumerate(zip(labels, values)):
        attrs[f"option{k}-label"] = attr("string", label)
        attrs[f"option{k}-value"] = attr("integer", value)
    attrs["options-count"] = attr("integer", len(labels))
    attrs["min"]["value"], attrs["max"]["value"] = min(values), max(values)
    n["attributes"] = attrs
    n["hidden"] = sorted(attrs) + ["input"]
    n["constants"]["input"]["value"] = default
    n["name"] = name
    n["bounds"].update(x=x, y=y)
    return n


def cached_input(i):
    """The ISF node keeps a parsed copy of the header next to the path."""
    out = {"name": i["NAME"], "type": i["TYPE"]}
    if i["TYPE"] == "image":
        return out
    out["label"] = i["LABEL"]
    out["defaultValue"] = i["DEFAULT"]
    if i["TYPE"] == "long":
        out["options"] = [{"label": l, "value": v} for l, v in zip(i["LABELS"], i["VALUES"])]
    else:
        out["min"], out["max"] = i["MIN"], i["MAX"]
    return out


def build_wire():
    src = (HERE / SHADER).read_text(encoding="utf-8")
    inputs = json.loads(src[src.index("/*") + 2: src.index("}*/") + 1])["INPUTS"]
    by_name = {i["NAME"]: i for i in inputs}

    wire = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    patch = wire["patch"]
    nodes = patch["nodes"]
    float_tpl, choice_tpl = nodes[FLOAT_TEMPLATE], nodes[CHOICE_TEMPLATE]
    deriv_tpl, clamp_tpl, accu_tpl, float_conv_tpl = nodes["20"], nodes["21"], nodes["18"], nodes["24"]
    # Keep: ISF 0, Image 1 (now the label atlas), Texture Out 2, Transport Time 19, the
    # system clock 23-29 and Derivative 20 -> Clamp 21 -> Accumulate 18.
    for k in (FLOAT_TEMPLATE, CHOICE_TEMPLATE):
        del nodes[k]
    conns = patch["connections"] = [c for c in patch["connections"]
                                    if c["from"][0] in range(23, 30) and c["to"][0] in range(23, 30)]

    def link(a, out, b, inp):
        conns.append({"from": [a, out], "to": [b, inp]})

    isf = nodes[ISF_NODE]
    isf["attributes"]["fragment-shader"]["value"]["path"]["main"] = (PATCH_DIR / SHADER).as_posix()
    isf["attributes"]["fragment-shader"]["value"]["value"]["inputs"] = [cached_input(i) for i in inputs]
    keep = {k: v for k, v in isf["constants"].items() if k in ("bypass", "time")}
    for i in inputs:
        if i["TYPE"] == "long":
            keep[i["NAME"]] = attr("integer", i["DEFAULT"])
        elif i["TYPE"] == "float":
            keep[i["NAME"]] = attr("float", i["DEFAULT"])
    isf["constants"] = keep
    isf["bounds"]["height"] = 58 + 24 * len(inputs)
    isf["name"] = "EVA-Responsive"
    link(0, "output", 2, "input")

    img = nodes[IMAGE_NODE]
    img["attributes"]["image"]["value"]["path"]["main"] = (PATCH_DIR / ATLAS).as_posix()
    img["attributes"]["image"]["value"]["value"].update(
        {"codec": "PNG", "channelCount": 3, "bitDepth": 24, "resolution": {"width": 2048, "height": 2048}})
    img["name"] = "Atlas labels"
    link(1, "output", 0, "atlas")

    next_id = patch["nextNodeId"]

    def add(n):
        nonlocal next_id
        nodes[str(next_id)] = n
        next_id += 1
        return next_id - 1

    # Clocks since the last "Recommencer": seconds (existing chain) and beats (new chain).
    link(29, "output0", 20, "input0")
    link(20, "output0", 21, "value")
    link(21, "output0", 18, "input0")
    link(18, "output0", 0, "tSec")
    d2 = copy.deepcopy(deriv_tpl); d2["bounds"].update(x=396, y=1700)
    c2 = copy.deepcopy(clamp_tpl); c2["bounds"].update(x=651, y=1700); c2["constants"]["max"]["value"] = 0.5
    a2 = copy.deepcopy(accu_tpl); a2["bounds"].update(x=1161, y=1700)
    d2, c2, a2 = add(d2), add(c2), add(a2)
    link(19, "beats", d2, "input0")
    link(d2, "output0", c2, "value")
    link(c2, "output0", a2, "input0")
    link(a2, "output0", 0, "tBeat")
    wire_inputs = {}
    restart = add(trigger_in("Recommencer", -200, 1500))
    for acc in (18, a2):
        link(restart, "output", acc, "reset")
        nodes[str(acc)]["hidden"] = [h for h in nodes[str(acc)]["hidden"] if h != "reset"]
    wire_inputs["@Recommencer"] = restart

    texts = []
    for k, (label, text, font, style, scale, uhd, lw) in enumerate(FIELDS):
        y = -1400 + k * 300
        s = add(string_in(label, text, -760, y))
        r = add(replace_node(-560, y))
        t = add(text_render(f"Texte {label}", font, style, scale, uhd, lw, -300, y))
        ln = add(length_node(-560, y + 120))
        fc = copy.deepcopy(float_conv_tpl); fc["bounds"].update(x=-300, y=y + 240)
        fc = add(fc)
        link(s, "output", r, "input")
        link(r, "output0", t, "input")
        link(s, "output", ln, "input0")
        link(ln, "output0", fc, "input0")
        link(fc, "output0", 0, f"len{k}")
        link(t, "output", 0, f"txt{k}")
        texts.append(s)

    # Dashboard.
    groups, roots, y = {}, [], -60
    gid = 1790000000600
    groups[str(gid)] = {"children": texts, "collapsed": False, "name": "Textes"}
    roots.append({"group": gid})
    for g, (group_name, names) in enumerate(GROUPS):
        children = []
        for name in names:
            if name.startswith("@"):
                children.append(wire_inputs[name])
                continue
            i = by_name[name]
            if i["TYPE"] == "long":
                n = choice_in(choice_tpl, LABELS[name], OPTION_LABELS.get(name, i["LABELS"]),
                              i["VALUES"], i["DEFAULT"], 560, y)
            else:
                n = float_in(float_tpl, LABELS[name], i["MIN"], i["MAX"], i["DEFAULT"], 560, y)
            y += 112
            nid = add(n)
            link(nid, "output", 0, name)
            children.append(nid)
        gid = 1790000000602 + g * 2
        groups[str(gid)] = {"children": children, "collapsed": g > 1, "name": group_name}
        roots.append({"group": gid})
    patch["nextNodeId"] = next_id
    patch["inputOrder"] = {"groups": groups, "roots": roots}

    wired = {c["to"][1] for c in conns if c["to"][0] == 0}
    missing = [i["NAME"] for i in inputs if i["NAME"] not in wired]
    if missing:
        raise SystemExit(f"shader inputs left unconnected: {missing}")
    shown = {n for _, names in GROUPS for n in names if not n.startswith("@")}
    extra = [i["NAME"] for i in inputs if i["TYPE"] != "image"
             and i["NAME"] not in shown and i["NAME"] not in HIDDEN_SHADER]
    if extra:
        raise SystemExit(f"shader inputs missing from the dashboard: {extra}")

    meta = patch["meta"]
    meta.update({"displayName": NAME, "author": "VJ", "vendor": "VJ", "url": "", "mail": "",
                 "identifier": str(uuid.uuid5(uuid.NAMESPACE_URL, f"vj/wire/{NAME}"))})
    meta["resolution"] = {"width": 1080, "height": 1920}   # opens in portrait; Arena uses its comp size
    meta["description"] = ("Version responsive (16:9, 9:16, 1:1, ultra-large) de EVA Overlay. "
                           "Interface texte façon Evangelion : 6 champs (Titre, Sous-titre, Kanji, Label, Infos, "
                           "Bandeau ; « / » pour aller à la ligne) mis en page dans 9 presets animés (carte titre, "
                           "alerte, MAGI, Sound Only, synchro, activité, Pattern Blue, bandeau, terminal), "
                           "défilement auto avec transitions. Fond transparent ou noir.")
    patch["ui"]["selection"] = []

    PATCH_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / SHADER, PATCH_DIR / SHADER)
    shutil.copy2(HERE / ATLAS, PATCH_DIR / ATLAS)
    out = PATCH_DIR / f"{NAME}.wire"
    out.write_text(json.dumps(wire, ensure_ascii=False, indent="\t"), encoding="utf-8")
    print(f"{len(nodes)} nodes, {len(conns)} connections -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--patches", type=Path, default=PATCHES,
                    help="Resolume Wire patches folder (default: %(default)s)")
    PATCH_DIR = ap.parse_args().patches / NAME
    build_wire()
