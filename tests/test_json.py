import pytest
import pytest_check as check
import json
import re

from compact_json import Formatter
from pathlib import Path


def test_json(pytestconfig):
    test_data_path = Path("tests/data")

    if pytestconfig.getoption("test_file") is not None:
        ref_filename = pytestconfig.getoption("test_file")
        source_filenames = [Path(re.sub("\.ref.*", ".json", ref_filename))]
    else:
        source_filenames = sorted(test_data_path.rglob("*.json"))

    for source_filename in source_filenames:
        if source_filename.match("*.ref*"):
            continue
        with open(source_filename) as f:
            obj = json.load(f)

        if pytestconfig.getoption("test_file") is not None:
            ref_filenames = [pytestconfig.getoption("test_file")]
        else:
            ref_filenames = test_data_path.rglob(source_filename.stem + ".ref*")

        for ref_filename in ref_filenames:
            formatter = Formatter()
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
            assert json_string == ref_json
