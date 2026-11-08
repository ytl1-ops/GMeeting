"""Ressources Android : erreurs que seule la compilation (CI) détectait jusqu'ici. Vérifiées à chaque exécution des tests, sans SDK Android."""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

RES = Path(__file__).resolve().parent.parent / "android" / "app" / "src" / "main" / "res"


def strings(folder):
    root = ET.parse(RES / folder / "strings.xml").getroot()
    return {s.get("name"): (s.text or "") for s in root.findall("string")}


def test_every_apostrophe_is_escaped_as_aapt_requires():
    for folder in ("values", "values-fr"):
        for name, text in strings(folder).items():
            if text.startswith('"') and text.endswith('"'):
                continue                                                                       # chaîne entre guillemets : apostrophes libres
            assert not re.search(r"(?<!\\)'", text), f"{folder}/{name} : apostrophe non échappée (écrire \\') : {text!r}"


def test_french_and_english_have_exactly_the_same_strings():
    en, fr = strings("values"), strings("values-fr")
    assert set(en) == set(fr), (sorted(set(en) ^ set(fr)))


def test_translations_keep_the_same_format_arguments():
    en, fr = strings("values"), strings("values-fr")
    arg = re.compile(r"%\d\$[sd]")
    for name in en:
        assert sorted(arg.findall(en[name])) == sorted(arg.findall(fr[name])), f"{name} : arguments de format différents entre l'anglais et le français"


def test_no_string_contains_markup_that_breaks_the_build():
    for folder in ("values", "values-fr"):
        for name, text in strings(folder).items():
            assert "<" not in text and "\n\n\n" not in text, f"{folder}/{name}"
