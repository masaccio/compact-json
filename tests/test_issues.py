import json
import re

from compact_json import Formatter
from pathlib import Path

REF_ISSUE_7 = '{ "100": "mary", "200": "had", "300": ["a", "little", "lamb"] }'

def test_issue_7(pytestconfig):
    obj = {100: "mary", 200: "had", 300: ["a", "little", "lamb"]}
    formatter = Formatter(indent_spaces=2, max_inline_length=100)
    json_string = formatter.serialize(obj)
    assert json_string == REF_ISSUE_7
