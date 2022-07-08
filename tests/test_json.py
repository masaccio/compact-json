import pytest
import pytest_check as check
import json

from compact_json import Formatter
from pathlib import Path


def test_json():
    for filename in Path("tests/data").rglob("*.json"):
        formatter = Formatter()
        formatter.indent_spaces = 2
        formatter.max_inline_length = 120

        ref_filename = str(filename).replace(".json", ".ref")
        ref = open(ref_filename).read().rstrip()

        with open(filename) as f:
            obj = json.load(f)
            json_string = formatter.serialize(obj)

        check.equal(json_string, ref)
