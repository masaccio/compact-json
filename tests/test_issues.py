from collections import OrderedDict

import pytest

from compact_json import Formatter

REF_ISSUE_7 = '{ "100": "mary", "200": "had", "300": ["a", "little", "lamb"] }'
REF_TYPES = """{
  "bool": [true, false], 
  "float": 1.234, 
  "int": [100, 200, 300], 
  "string": "value", 
  "ordereddict": {
    "aaa": 100, 
    "bbb": 101, 
    "ccc": 102
  }
}"""


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
        "ordereddict": OrderedDict(aaa=100, bbb=101, ccc=102),
    }
    formatter = Formatter(indent_spaces=2, max_inline_length=30)
    json_string = formatter.serialize(obj)
    assert json_string == REF_TYPES
