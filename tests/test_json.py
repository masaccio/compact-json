import pytest
import pytest_check as check
import json
import re

from compact_json import Formatter
from pathlib import Path


def test_json():
    test_data_path = Path("tests/data")
    for source_filename in test_data_path.rglob("*.json"):
        if source_filename.match("*.ref*"):
            continue
        # source_filename = Path("tests/data/test-15.json")
        with open(source_filename) as f:
            obj = json.load(f)

        for ref_filename in test_data_path.rglob(source_filename.stem + ".ref*"):
            formatter = Formatter()
            print(f"\n*** {ref_filename}")
            # ref_filename = "tests/data/test-15.ref.1"
            with open(ref_filename) as f:
                ref_json = ""
                for line in f.readlines():
                    if line.startswith("@"):
                        (param, value) = line[1:].split("=")
                        value = value.strip()
                        exec(f"formatter.{param} = {value}")
                    else:
                        ref_json += line
            # No final newline
            ref_json = ref_json.rstrip()

            json_string = formatter.serialize(obj)

            if json_string != ref_json:
                json_string = re.sub("^", ">>", json_string, flags=re.MULTILINE)
                json_string = re.sub("$", "<<", json_string, flags=re.MULTILINE)
                ref_json = re.sub("^", ">>", ref_json, flags=re.MULTILINE)
                ref_json = re.sub("$", "<<", ref_json, flags=re.MULTILINE)
                print(f"\n=============== {ref_filename} ===============")
                print("=============== Result ===============")
                print(json_string)
                print("\n=============== Reference ===============")
                print(ref_json)
                print("==================================\n")
                assert False
