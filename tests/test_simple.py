import pytest
import json

from compact_json import Formatter

REF_JSON_1 = """{
  "widget": {
    "debug": "on",
    "window": {"title": "Sample Konfabulator Widget", "name": "main_window", "width": 500, "height": 500},
    "image": {"src": "Images/Sun.png", "name": "sun1", "hOffset": 250, "vOffset": 250, "alignment": "center"},
    "text": {
      "data": "Click Here",
      "size": 36,
      "style": "bold",
      "name": "text1",
      "hOffset": 250,
      "vOffset": 100,
      "alignment": "center",
      "onMouseUp": "sun1.opacity = (sun1.opacity / 100) * 90;"
    }
  }
}"""


def test_simple_format():
    formatter = Formatter()
    formatter.indent_spaces = 2
    formatter.max_inline_length = 120

    with open("tests/data/test-1.json") as f:
        obj = json.load(f)
        json_string = formatter.serialize(obj)

    assert json_string == REF_JSON_1
