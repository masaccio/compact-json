import json
import logging
import re
from pathlib import Path

import compact_json
from compact_json import Formatter

logger = logging.getLogger(compact_json.__name__)


test_data_path = Path("tests/data")


def test_json(pytestconfig):
    if pytestconfig.getoption("test_verbose"):
        print("\n")

    if pytestconfig.getoption("test_debug"):
        logger.setLevel("DEBUG")

    if pytestconfig.getoption("test_file") is not None:
        ref_filename = pytestconfig.getoption("test_file")
        source_filenames = [Path(re.sub(r"[.]ref.*", ".json", ref_filename))]
    else:
        source_filenames = sorted(test_data_path.rglob("*.json"))

    for source_filename in source_filenames:
        if source_filename.match("*.ref*"):
            continue

        if pytestconfig.getoption("test_verbose"):
            print(f"*** Overriding source file: {source_filename}")

        with open(source_filename) as f:
            obj = json.load(f)

        if pytestconfig.getoption("test_file") is not None:
            ref_filenames = [pytestconfig.getoption("test_file")]
        else:
            ref_filenames = test_data_path.rglob(source_filename.stem + ".ref*")

        for ref_filename in ref_filenames:
            if pytestconfig.getoption("test_verbose"):
                print(f"*** Testing {ref_filename}")
            formatter = Formatter()
            with open(ref_filename) as f:
                ref_json = ""
                for line in f.readlines():
                    if line.startswith("@"):
                        (param, value) = re.split(r"\s*=\s*", line[1:])
                        value = value.strip()
                        exec(f"formatter.{param} = {value}")
                    else:
                        ref_json += line
            # No final newline
            ref_json = ref_json.rstrip()

            json_string = formatter.serialize(obj)

            if pytestconfig.getoption("test_verbose") and json_string != ref_json:
                json_string_dbg = ">" + re.sub(r"\n", "<\n>", json_string) + "<"
                ref_json_dbg = ">" + re.sub(r"\n", "<\n>", ref_json) + "<"
                print("===== TEST")
                print(json_string_dbg)
                print("===== REF")
                print(ref_json_dbg)
                print("=====")

            assert json_string == ref_json


def test_dump(tmp_path):
    tmp_file = tmp_path / "test.json"
    source_filename = test_data_path / "test-bool.json"
    with open(source_filename) as f:
        obj = json.load(f)
    formatter = Formatter()
    formatter.dump(obj, output_file=tmp_file, newline_at_eof=False)
    assert tmp_file.read_text() == '{ "bools": {"true": true, "false": false} }'
