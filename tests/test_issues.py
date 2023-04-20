import json
import re
from pathlib import Path

import pytest

from compact_json import Formatter

REF_ISSUE_7 = '{ "100": "mary", "200": "had", "300": ["a", "little", "lamb"] }'
REF_TYPES = """{
  "bool": [true, false], 
  "float": 1.234, 
  "int": [100, 200, 300], 
  "string": "value"
}"""

REF_ISSUE_27 = """{
  "key0": [
    [ "subkey0",          1e-05 ], 
    [ "subkey1",          2e-05 ], 
    [ "subkey2",     3.14159265 ]
  ]
}
"""


@pytest.mark.filterwarnings("ignore:coercing key")
def test_issue_7():
    with pytest.warns(RuntimeWarning) as record:
        obj = {100: "mary", 200: "had", 300: ["a", "little", "lamb"]}
        formatter = Formatter(indent_spaces=2, max_inline_length=100)
        json_string = formatter.serialize(obj)
        assert len(record) == 3
        assert json_string == REF_ISSUE_7


def test_issue_7_part2():
    with pytest.warns(RuntimeWarning) as record:
        obj = {100: "replace", 200: "had", 300: ["a", "little", "lamb"], "100": "mary"}
        formatter = Formatter(indent_spaces=2, max_inline_length=100)
        json_string = formatter.serialize(obj)
        assert json_string == REF_ISSUE_7
        assert len(record) == 4
        assert "converting key value 100 to string" in record[0].message.args[0]
        assert "duplicate key value 100" in record[3].message.args[0]


def test_types():
    obj = {
        "bool": [True, False],
        "float": 1.234,
        "int": [100, 200, 300],
        "string": "value",
    }
    formatter = Formatter(indent_spaces=2, max_inline_length=80)
    json_string = formatter.serialize(obj)
    assert json_string == REF_TYPES


@pytest.mark.script_launch_mode("inprocess")
def test_issue_26(script_runner):
    ret = script_runner.run(
        "compact-json",
        "-l50",
        "-i2",
        "--justify-numbers",
        "tests/data/test-issue-26.json",
    )
    assert ret.stderr == ""
    assert ret.success
    assert ret.stdout == REF_ISSUE_27
