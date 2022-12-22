import json
import re

from compact_json import Formatter
from pathlib import Path

REF_ISSUE_7 = '{ "100": "mary", "200": "had", "300": ["a", "little", "lamb"] }'
REF_TYPES = """{
  "bool": [true, false],
  "float": 1.234,
  "int": [100, 200, 300],
  "string": "value"
}"""

def test_issue_7(pytestconfig):
    obj = {100: "mary", 200: "had", 300: ["a", "little", "lamb"]}
    formatter = Formatter(indent_spaces=2, max_inline_length=100)
    json_string = formatter.serialize(obj)
    assert json_string == REF_ISSUE_7

def test_types(pytestconfig):
    obj = {"bool": [True, False], "float": 1.234, "int": [100, 200, 300], "string": "value"}
    formatter = Formatter(indent_spaces=2, max_inline_length=80)
    json_string = formatter.serialize(obj)
    assert json_string == REF_TYPES
