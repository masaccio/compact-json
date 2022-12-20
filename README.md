# compact-json

[![build:](https://github.com/masaccio/compact-json/actions/workflows/run-all-tests.yml/badge.svg)](https://github.com/masaccio/compact-json/actions/workflows/run-all-tests.yml)
[![build:](https://github.com/masaccio/compact-json/actions/workflows/codeql.yml/badge.svg)](https://github.com/masaccio/compact-json/actions/workflows/codeql.yml)
[![codecov](https://codecov.io/gh/masaccio/compact-json/branch/main/graph/badge.svg?token=EKIUFGT05E)](https://codecov.io/gh/masaccio/compact-json)

`compact-json` is a JSON formatter that produces configurably compact JSON that remains human-readable.

Any given container is formatted in one of three ways:

* Python lists or dicts will be written on a single line, if their contents aren't too complex and the resulting line wouldn't be too long.
* lists can be written on multiple lines, with multiple items per line, as long as those items aren't too complex.
* Otherwise, each dict property or array item is written beginning on its own line, indented one step deeper than its parent.

The following JSON is the standard output from running `python3 -mjson.tool`:

``` JSON
{
    "widget": {
        "debug": "on",
        "window": {
            "title": "Sample Konfabulator Widget",
            "name": "main_window",
            "width": 500,
            "height": 500
        },
        "image": {
            "src": "Images/Sun.png",
            "name": "sun1",
            "hOffset": 250,
            "vOffset": 250,
            "alignment": "center"
        },
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
}
```

The `window` and `image` objects are fairly short so when formatted with `compact-json` they can be formated on a single line. With the default setting the `text` object is still too long to fit on one line, but this can be configured to be longer:

``` JSON
{
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
}
```

## Installation

``` shell
python3 -m pip install compact-json
```

## Usage

As a python package, `compact-json` is instantiated with a `Formatter` class that has a range of properties to configure the formatting:

``` python
from compact_json import Formatter, EolStyle

formatter = Formatter()
formatter.indent_spaces = 2
formatter.max_inline_complexity = 10
formatter.json_eol_style = EolStyle.LF

with open("input.json", "r") as f:
    obj = json.load(f)
    json_string = formatter.serialize(obj)
    print(json_string)
```

## Command-line usage

When installed from `pip` a command-line utility `compact-json` is installed which has some useful defaults and most of the parameters available in `Formatter` can be set on the command-line:

``` shell
usage: _compact_json.py [-h] [-V] [--crlf] [--max-inline-length N]
                        [--max-inline-complexity N]
                        [--max-compact-list-complexity N]
                        [--bracket-padding {simple,nested}] [--indent N]
                        [--tab-indent] [--justify-numbers]
                        [--prefix-string STRING] [--align-properties]
                        [json ...]

Format JSON into compact, human readble form

positional arguments:
  json                  JSON file(s) to dump

optional arguments:
  -h, --help            show this help message and exit
  -V, --version
  --crlf                Use Windows-style CRLR line endings
  --max-inline-length N
                        Limit inline elements to N chars, excluding
                        indentation and leading property names (default=50)
  --max-inline-complexity N
                        Maximum nesting: 0=basic types, 1=dict/list, 2=all
                        (default=2)
  --max-compact-list-complexity N
                        Maximum nesting over multiple lines (default 1)
  --bracket-padding {simple,nested}
                        If nested padding, add speces inside outside brackes
                        for nested lists/dicts
  --indent N            Indent N spaces (default=4)
  --tab-indent          Use tabs to indent
  --justify-numbers     Right-align numbers with matching precision
  --prefix-string STRING
                        String attached to the beginning of every line
  --align-properties    Align property names of expanded dicts
  --unicode             Treat strings as unicode East Asian characters
```

## Format options

The `Formatter` class has the following properties:

### `json_eol_style`

Dictates what sort of line endings to use. `EolStyle.LF` is Unix-style line endings (the default) and `EolStyle.CRLF` Windows-style.

### `max_inline_length`

Maximum length of a complex element on a single line. This includes only the data for the inlined element not indentation or leading property names. The default is 80.

### `max_inline_complexity`

Maximum nesting level that can be displayed on a single line. A primitive type or an empty list or dict has a complexity of 0. A dict or list has a complexity of 1 greater than its most complex child. The default is 2.

### `max_compact_list_complexity`

Maximum nesting level that can be arranged spanning multiple lines, with multiple items per line. The default is 1.

### `nested_bracket_padding`

If an inlined list or dict contains other lists or dicts, setting `nested_bracket_padding` to `True` will include spaces inside the outer brackets. The default is `True`.

See also `simple_bracket_padding`.

### `simple_bracket_padding`

If an inlined list or dict does NOT contain other lists/dicts, setting `simple_bracket_padding` to `True` will include spaces inside the brackets. The default is `False`.

See also `nested_bracket_padding`.

### `colon_padding`

If `True` (the default), includes a space after property colons.

### `comma_padding`

If `True` (the default), includes a space after commas separating list items and dict properties.

### `always_expand_depth`

Depth at which lists/dicts are always fully expanded, regardless of other settings

* -1 = none. This is the default
* 0 = root node only
* 1 = root node and its children.

### `indent_spaces`

Number of spaces to use per indent level (unless `use_tab_to_indent` is `True`). The default is 4.

### `use_tab_to_indent`

Uses a single tab per indent level, instead of spaces. The default is `False`.

### `table_dict_minimum_similarity`

Value from 0 to 100 indicating how similar collections of inline dicts need to be to be formatted as a table. A group of dicts that don't have any property names in common has a similarity of zero. A group of dicts that all contain the exact same property names has a similarity of 100. Setting this to a value > 100 disables table formatting with dicts as rows. The default is 75.

### `table_list_minimum_similarity`

Value from 0 to 100 indicating how similar collections of inline lists need to be to be formatted as a table. Similarity for lists refers to how similar they are in length; if they all have the same length their similarity is 100. Setting this to a value > disables table formatting with lists as rows. The default is 75.

### `align_expanded_property_names`

If `True`, property names of expanded dicts are padded to the same size. The default is `False`.

### `dont_justify_numbers`

If `True`, numbers won't be right-aligned with matching precision. The default is `False`.

### `prefix_string`

String attached to the beginning of every line, before regular indentation.

### `ensure_ascii`

If `True` (the default), the output is guaranteed to have all incoming non-ASCII characters escaped. If `ensure_ascii` is `False`, these characters will be output as-is.

### `east_asian_string_widths`

If `True`, format strings using unicodedata.east_asian_width rather than simple string lengths

## Credits

`compact-json` is primarily a Python port of [FracturedJsonJs](https://github.com/j-brooke/FracturedJsonJs) by [j-brooke](https://github.com/j-brooke). FractureJson is also
an excellent [Visual Studio Code extension](https://marketplace.visualstudio.com/items?itemName=j-brooke.fracturedjsonvsc). This package has no other relationship
with this original code, and hence all the bugs are my own.

## License

All code in this repository is licensed under the [MIT License](https://github.com/masaccio/compact-json/blob/master/LICENSE.rst)
