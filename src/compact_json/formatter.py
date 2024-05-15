"""Compact JSON formatter."""

from __future__ import annotations

import json
import logging
import re
import warnings
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum, IntEnum, auto
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from wcwidth import wcswidth

if TYPE_CHECKING:
    from pathlib import PosixPath

logger = logging.getLogger(__name__)
debug = logger.debug


@lru_cache(4096)
def _wcswidth(s: str) -> int:
    return wcswidth(s)


class EolStyle(IntEnum):
    """End of line style enumeration."""

    CRLF = auto()
    LF = auto()


class JsonValueKind(IntEnum):
    """JSON token enumeration."""

    UNDEFINED = auto()
    DICT = auto()
    LIST = auto()
    STRING = auto()
    INT = auto()
    FLOAT = auto()
    BOOLEAN = auto()
    NULL = auto()


class Format(IntEnum):
    """Format type enumeration."""

    INLINE = auto()
    INLINE_TABULAR = auto()
    MULTILINE_COMPACT = auto()
    EXPANDED = auto()


class FormattedNode:
    """Data about a JSON element and how we've formatted it."""

    def __init__(self: FormattedNode) -> None:
        """Initialise a new formating node."""
        self.name = ""
        self.name_length = 0
        self.value = ""
        self.value_length = 0
        self.complexity = 0
        self.depth = 0
        self.kind = JsonValueKind.UNDEFINED
        self.format = Format.INLINE
        self.children: list[FormattedNode] = []

    def cleanup(self: FormattedNode) -> None:
        """Cleanup children."""
        if self.format != Format.INLINE:
            self.children = []
        for child in self.children:
            child.children = []


def _fixed_value(value: str, num_decimals: int) -> str:
    if "e" in value:
        return value

    quantize_str = "0." + "0" * (num_decimals - 1) + "1" if num_decimals > 0 else "0"

    try:
        return str(Decimal(value).quantize(Decimal(quantize_str)))
    except InvalidOperation:  # pragma: no cover
        warnings.warn(
            "handled quantize error (please report an issue)",
            RuntimeWarning,
            stacklevel=2,
        )
        return value


class ColumnStats:
    """Used in figuring out how to format properties/list items as columns in a table format."""

    def __init__(self: ColumnStats, dont_justify: bool) -> None:
        """Create a new column stats object."""
        debug("ColumnStats()")
        self.dont_justify = dont_justify
        self.prop_name = ""
        self.prop_name_length = 0
        self.order_sum = 0
        self.count = 0
        self.max_value_size = 0
        self.kind = JsonValueKind.NULL
        self.chars_before_dec = 0
        self.chars_after_dec = 0

    def update(self: ColumnStats, prop_node: FormattedNode, index: int) -> None:
        """Add stats about this FormattedNode to this PropertyStats."""
        self.order_sum += index
        self.count += 1
        debug("update()")
        debug(f"  value={prop_node.value}¶")
        debug(f"  max_value_size={self.max_value_size}")
        debug(f"  value_length={prop_node.value_length}")
        self.max_value_size = max([self.max_value_size, prop_node.value_length])
        if self.kind == JsonValueKind.NULL:
            self.kind = prop_node.kind
        elif (
            self.kind == JsonValueKind.FLOAT
            and prop_node.kind == JsonValueKind.INT
            or self.kind == JsonValueKind.INT
            and prop_node.kind == JsonValueKind.FLOAT
        ):
            self.kind = JsonValueKind.FLOAT
        elif self.kind != prop_node.kind:
            self.kind = JsonValueKind.UNDEFINED

        if prop_node.kind == JsonValueKind.FLOAT:
            if "." in prop_node.value:
                (whole, frac) = prop_node.value.split(".")
            else:
                (whole, frac) = (prop_node.value, "")
            self.chars_after_dec = max([self.chars_after_dec, len(frac)])
            self.chars_before_dec = max([self.chars_before_dec, len(whole)])
            debug(f"  chars_after_dec={self.chars_after_dec}")
            debug(f"  chars_before_dec={self.chars_before_dec}")
        elif prop_node.kind == JsonValueKind.INT:
            self.chars_before_dec = max([self.chars_before_dec, len(prop_node.value)])
            debug(f"  chars_before_dec={self.chars_before_dec}")

    @property
    def max_value_size(self: ColumnStats) -> int:
        """Return max size of a node."""
        if self.dont_justify:
            return self._max_value_size
        if self.kind == JsonValueKind.FLOAT:
            return self.chars_before_dec + self.chars_after_dec + 1
        if self.kind == JsonValueKind.INT:
            return self.chars_before_dec
        return self._max_value_size

    @max_value_size.setter
    def max_value_size(self: ColumnStats, v: int) -> None:
        """Set max size of a node."""
        self._max_value_size = v

    def format_value(self: ColumnStats, value: str, value_length: int) -> str:
        """Format a value based on its column position."""
        debug("format_value()")
        debug(f"  value={value}¶")
        debug(f"  value_length={value_length}")
        debug(
            "  is_numeric="
            + str(
                self.kind in (JsonValueKind.FLOAT, JsonValueKind.INT),
            ).lower(),
        )

        if (
            self.kind in (JsonValueKind.FLOAT, JsonValueKind.INT)
        ) and not self.dont_justify:
            adjusted_val = _fixed_value(value, self.chars_after_dec)
            total_length = self.chars_before_dec + self.chars_after_dec
            total_length += 1 if self.chars_after_dec > 0 else 0
            debug(f"  adjusted_val={adjusted_val}")
            debug(f"  chars_before_dec={self.chars_before_dec}")
            debug(f"  chars_after_dec={self.chars_after_dec}")
            debug(f"  total_length={total_length}")
            debug("  value=" + adjusted_val.rjust(total_length) + "¶")
            return adjusted_val.rjust(total_length)

        debug(f"  max_value_size={self.max_value_size}")
        debug(f"  len(value)={len(value)}")
        debug(
            "  value="
            + value.ljust(self.max_value_size - (value_length - len(value)))
            + "¶",
        )
        return value.ljust(self.max_value_size - (value_length - len(value)))


@dataclass
class Formatter:
    """Class that outputs JSON formatted in a compact, user-readable way.

    Any given container is formatted in one of three ways:
    * Arrays or dicts will be written on a single line, if their contents aren't too
      complex and the resulting line wouldn't be too long.
    * Arrays can be written on multiple lines, with multiple items per line, as long as
      those items aren't too complex.
    * Otherwise, each dict property or list item is written beginning on its own line,
      indented one step deeper than its parent.

    Properties:

    json_eol_style:
        Dictates what sort of line endings to use.

    max_inline_length
        Maximum length of a complex element on a single line. This includes only the data
        for the inlined element not indentation or leading property names.

    max_inline_complexity:
        Maximum nesting level that can be displayed on a single line. A primitive type or
        an empty list or dict has a complexity of 0. A dict or list has a complexity
        of 1 greater than its most complex child.

    max_compact_list_complexity:
        Maximum nesting level that can be arranged spanning multiple lines, with multiple
        items per line.

    nested_bracket_padding:
        If an inlined list or dict contains other lists or dicts, setting
        nested_bracket_padding to True will include spaces inside the outer brackets.
        See also simple_bracket_padding.

    simple_bracket_padding:
        If an inlined list or dict does NOT contain other lists/dicts,
        setting simple_bracket_padding to True will include spaces inside the brackets.
        See also nested_bracket_padding

    colon_padding:
        If True, includes a space after property colons.

    comma_padding:
        If True, includes a space after commas separating list items and dict properties.

    always_expand_depth:
        Depth at which lists/dicts are always fully expanded, regardless of other settings.
        -1 = none; 0 = root node only; 1 = root node and its children.

    indent_spaces:
        Number of spaces to use per indent level (unless use_tab_to_indent is True)

    use_tab_to_indent:
        Uses a single tab per indent level, instead of spaces.

    table_dict_minimum_similarity:
        Value from 0 to 100 indicating how similar collections of inline dicts need to be
        to be formatted as a table. A group of dicts that don't have any property names
        in common has a similarity of zero. A group of dicts that all contain the exact
        same property names has a similarity of 100. Setting this to a value > 100 disables
        table formatting with dicts as rows.

    table_list_minimum_similarity:
        Value from 0 to 100 indicating how similar collections of inline lists need to be
        to be formatted as a table. Similarity for lists refers to how similar they are in
        length; if they all have the same length their similarity is 100. Setting this to
        a value > 100 disables table formatting with lists as rows.

    align_expanded_property_names:
        If True, property names of expanded dicts are padded to the same size.

    dont_justify_numbers:
        If True, numbers won't be right-aligned with matching precision.

    prefix_string:
        String attached to the beginning of every line, before regular indentation.

    ensure_ascii:
        If True (the default), the output is guaranteed to have all incoming non-ASCII characters
        escaped. If ensure_ascii is False, these characters will be output as-is.

    east_asian_string_widths
        If True (default is False), format strings using unicodedata.east_asian_width rather
        than simple string lengths

    multiline_compact_dict
        If True (default is False), format dict into multi-line compact style like list

    omit_trailing_whitespace
        If True, strip whitespace at the end of all output lines.
    """

    json_eol_style: EolStyle = EolStyle.LF
    max_inline_length: int = 80
    max_inline_complexity: int = 2
    max_compact_list_complexity: int = 1
    nested_bracket_padding: bool = True
    simple_bracket_padding: bool = False
    colon_padding: bool = True
    comma_padding: bool = True
    always_expand_depth: int = -1
    indent_spaces: int = 4
    use_tab_to_indent: bool = False
    table_dict_minimum_similarity: int = 75
    table_list_minimum_similarity: int = 75
    align_expanded_property_names: bool = False
    dont_justify_numbers: bool = False
    prefix_string: bool = ""
    ensure_ascii: bool = True
    east_asian_string_widths: bool = False
    multiline_compact_dict: bool = False
    omit_trailing_whitespace: bool = False

    def __post_init__(self: Formatter) -> None:
        """Init none-datatype fields."""
        self.eol_str = ""
        self.indent_str = ""
        self.padded_comma_str = ""
        self.padded_colon_str = ""
        self.indent_cache = {}

    def str_len(self: Formatter, s: str) -> int:
        """Return string length supporting east-Asian characters."""
        if not self.east_asian_string_widths or s.isascii():
            return len(s)
        return _wcswidth(s)

    def dump(
        self: Formatter,
        obj: Any,  # noqa: ANN401
        output_file: str | PosixPath,
        newline_at_eof: bool = True,  # noqa: FBT002
    ) -> None:
        """Write JSON to a file."""
        formatted: str = self.serialize(obj)
        if newline_at_eof:
            formatted += self.eol_str

        with open(output_file, "w") as f:
            f.write(formatted)

    def serialize(self: Formatter, value: str) -> str:
        """Serialize a value to formatted JSON."""
        self.init_internals()
        value = self.prefix_string + self.format_element(0, value).value
        if self.omit_trailing_whitespace:
            value = re.sub(r"\s+$", "", value, flags=re.MULTILINE)
        return value

    def init_internals(self: Formatter) -> None:
        """Set up some intermediate fields for efficiency."""
        self.eol_str = "\r\n" if self.json_eol_style == EolStyle.CRLF else "\n"
        self.indent_str = "\t" if self.use_tab_to_indent else " " * self.indent_spaces
        self.padded_comma_str = ", " if self.comma_padding else ","
        self.padded_colon_str = ": " if self.colon_padding else ":"

    def indent(self: Formatter, buffer: list[str], depth: int) -> list[str]:
        """Indent a list of strings."""
        if depth not in self.indent_cache:
            self.indent_cache[depth] = self.indent_str * depth
        buffer += [self.prefix_string, self.indent_cache[depth]]
        return buffer

    def combine(self: Formatter, buffer: list[str]) -> str:
        """Combine a list of strings to a single string."""
        return "".join(buffer)

    def format_element(self: Formatter, depth: int, element: object) -> FormattedNode:
        """Root formmatting function for recursion."""
        if isinstance(element, list):
            formatted_item = self.format_list(depth, element)
        elif isinstance(element, dict):
            formatted_item = self.format_dict(depth, element)
        else:
            formatted_item = self.format_simple(depth, element)

        formatted_item.cleanup()
        return formatted_item

    def format_simple(self: Formatter, depth: int, element: object) -> FormattedNode:
        """Format a JSON element other than an list or dict."""
        simple_node = FormattedNode()
        simple_node.value = json.dumps(element, ensure_ascii=self.ensure_ascii)
        simple_node.value_length = self.str_len(simple_node.value)
        simple_node.complexity = 0
        simple_node.depth = depth

        if element is None:
            simple_node.kind = JsonValueKind.NULL
            return simple_node

        if isinstance(element, bool):
            simple_node.kind = JsonValueKind.BOOLEAN
        elif isinstance(element, int):
            simple_node.kind = JsonValueKind.INT
        elif isinstance(element, float):
            simple_node.kind = JsonValueKind.FLOAT
        else:
            simple_node.kind = JsonValueKind.STRING

        return simple_node

    def format_list(self: Formatter, depth: int, element: list) -> FormattedNode:
        """Recursively format all of this list's elements."""
        items = [self.format_element(depth + 1, child) for child in element]
        if len(items) == 0:
            return self.empty_list(depth)

        item = FormattedNode()
        item.kind = JsonValueKind.LIST
        item.complexity = max([fn.complexity for fn in items]) + 1
        item.depth = depth
        item.children = items

        if self.format_list_inline(item):
            return item

        self.justify_parallel_numbers(item.children)

        if self.format_table_list_dict(item):
            return item

        if self.format_table_list_list(item):
            return item

        if self.format_list_multiline_compact(item):
            return item

        self.format_list_expanded(item)
        return item

    def format_dict(self: Formatter, depth: int, element: dict) -> FormattedNode:
        """Recursively format all of this dict's property values."""
        items = []
        keys = {}
        for k, v in element.items():
            elem = self.format_element(depth + 1, v)
            if isinstance(k, Enum):
                k = k.value  # noqa: PLW2901
            if not isinstance(k, str):
                warnings.warn(
                    f"converting key value {k} to string",
                    RuntimeWarning,
                    stacklevel=2,
                )
            k = str(k)  # noqa: PLW2901
            elem.name = json.dumps(k, ensure_ascii=self.ensure_ascii)
            elem.name_length = self.str_len(elem.name)
            if k in keys:
                warnings.warn(
                    f"duplicate key value {k}",
                    RuntimeWarning,
                    stacklevel=2,
                )
                items[keys[k]] = elem
            else:
                keys[k] = len(items)
                items.append(elem)

        if len(items) == 0:
            return self.empty_dict(depth)

        item = FormattedNode()
        item.kind = JsonValueKind.DICT
        item.complexity = max([fn.complexity for fn in items]) + 1
        item.depth = depth
        item.children = items

        if self.format_dict_inline(item):
            return item

        if self.format_table_dict_dict(item):
            return item

        if self.format_table_dict_list(item):
            return item

        if self.format_dict_multiline_compact(item):
            return item

        self.format_dict_expanded(item, False)
        return item

    def empty_list(self: Formatter, depth: int) -> FormattedNode:
        """Create an empty list node."""
        arr = FormattedNode()
        arr.value = "[]"
        debug("empty_list: value_length = 2")
        arr.value_length = 2
        arr.complexity = 0
        arr.depth = depth
        arr.kind = JsonValueKind.LIST
        arr.format = Format.INLINE
        return arr

    def format_list_inline(self: Formatter, item: FormattedNode) -> bool:
        """Try to format this list in a single line, if possible."""
        if (
            item.depth <= self.always_expand_depth
            or item.complexity > self.max_inline_complexity
        ):
            return False

        if any(fn.format != Format.INLINE for fn in item.children):
            return False

        if item.complexity >= 2:  # noqa: PLR2004
            use_bracket_padding = self.nested_bracket_padding
        else:
            use_bracket_padding = self.simple_bracket_padding
        line_length = 2 + (2 if use_bracket_padding else 0)
        line_length += (len(item.children) - 1) * len(self.padded_comma_str)
        line_length += sum([fn.value_length for fn in item.children])

        if line_length > self.max_inline_length:
            return False

        buffer = ["["]

        if use_bracket_padding:
            buffer += " "

        first_elem = True
        for child in item.children:
            if not first_elem:
                buffer += self.padded_comma_str
            buffer += child.value
            first_elem = False

        if use_bracket_padding:
            buffer += " "
        buffer += "]"

        item.value = self.combine(buffer)
        debug(f"format_list_inline: value_length = {line_length}")
        item.value_length = line_length
        item.format = Format.INLINE
        return True

    def format_list_multiline_compact(self: Formatter, item: FormattedNode) -> bool:
        """Try to format this list.

        Span multiple lines, but with several items per line, if possible.
        """
        debug("format_list_multiline_compact()")
        if (
            item.depth <= self.always_expand_depth
            or item.complexity > self.max_compact_list_complexity
        ):
            return False

        buffer = ["[", self.eol_str]
        self.indent(buffer, item.depth + 1)

        line_length_so_far = 0
        child_index = 0
        while child_index < len(item.children):
            not_last_item = child_index < (len(item.children) - 1)

            item_length = item.children[child_index].value_length
            segment_length = item_length + len(self.padded_comma_str)
            if child_index != 0:
                flag_new_line = False
                if item.children[child_index].format not in [
                    Format.INLINE,
                    Format.INLINE_TABULAR,
                ]:
                    if item.children[child_index - 1].format in [
                        Format.INLINE,
                        Format.INLINE_TABULAR,
                    ]:
                        flag_new_line = True
                elif item.children[child_index - 1].format not in [
                    Format.INLINE,
                    Format.INLINE_TABULAR,
                ]:
                    flag_new_line = True
                elif (
                    line_length_so_far + segment_length
                    > self.max_inline_length + len(self.padded_comma_str)
                    and line_length_so_far > 0
                ):
                    debug(f"  max_inline_length={self.max_inline_length}")
                    debug(f"  line_length_so_far={line_length_so_far}")
                    debug(f"  segment_length={segment_length}")
                    debug(f"  buffer={buffer}¶")
                    flag_new_line = True
                if flag_new_line:
                    buffer += self.eol_str
                    self.indent(buffer, item.depth + 1)
                    line_length_so_far = 0
            buffer += item.children[child_index].value
            if not_last_item:
                buffer += self.padded_comma_str

            child_index += 1
            line_length_so_far += segment_length

        buffer += self.eol_str
        self.indent(buffer, item.depth)
        buffer += "]"

        item.value = self.combine(buffer)
        item.format = Format.MULTILINE_COMPACT
        return True

    def format_table_list_dict(self: Formatter, item: FormattedNode) -> bool:
        """Format this list with one child dict per line.

        Those dicts are padded to line up nicely.
        """
        if self.table_dict_minimum_similarity > 100.5:  # noqa: PLR2004
            return False

        # Gather stats about our children's property order and width, if they're eligible dicts.
        col_stats = self.get_property_stats(item)
        if not col_stats:
            return False

        value_length = (
            sum([col.prop_name_length + col.max_value_size for col in col_stats])
            + len(self.padded_colon_str) * len(col_stats)
            + len(self.padded_comma_str) * (len(col_stats) - 1)
            + 4
        )

        # Reformat our immediate children using the width info we've computed. Their
        # children aren't recomputed, so this part isn't recursive.
        for child in item.children:
            self.format_dict_table_row(child, col_stats)
            child.value_length = value_length

        if self.format_list_multiline_compact(item):
            return item
        return self.format_list_expanded(item)

    def format_table_list_list(self: Formatter, item: FormattedNode) -> bool:
        """Format a list of lists."""
        debug("format_table_list_list()")
        if self.table_list_minimum_similarity > 100:  # noqa: PLR2004
            return False

        # Gather stats about our children's item widths, if they're eligible lists.
        column_stats = self.get_list_stats(item)
        if not column_stats:
            return False

        value_length = (
            sum([col.max_value_size for col in column_stats])
            + len(self.padded_comma_str) * (len(column_stats) - 1)
            + 4
        )

        # Reformat our immediate children using the width info we've computed. Their
        # children aren't recomputed, so this part isn't recursive.
        for child in item.children:
            self.format_list_table_row(child, column_stats)
            child.value_length = value_length

        if self.format_list_multiline_compact(item):
            return item
        return self.format_list_expanded(item)

    def format_list_table_row(
        self: Formatter,
        item: FormattedNode,
        column_stats_list: list[ColumnStats],
    ) -> None:
        """Format this list in a single line, with padding to line up with siblings."""
        buffer = ["[ "]

        debug("format_list_table_row()")
        # Write the elements that actually exist in this list.
        for index, child in enumerate(item.children):
            if index:
                buffer += self.padded_comma_str

            column_stats = column_stats_list[index]
            buffer += column_stats.format_value(
                child.value,
                child.value_length,
            )

        # Write padding for elements that exist in siblings but not this list.
        for index in range(len(item.children), len(column_stats_list)):
            debug("Write padding for elements that exist")
            pad_size = column_stats_list[index].max_value_size
            pad_size += 0 if index == 0 else len(self.padded_comma_str)
            buffer += " " * pad_size

        buffer += " ]"

        debug("...format_list_table_row()")
        item.value = self.combine(buffer)
        item.value_length = (
            sum([col.max_value_size for col in column_stats_list])
            + len(self.padded_comma_str) * (len(column_stats_list) - 1)
            + 4
        )
        debug(f"  value={item.value}¶")
        item.format = Format.INLINE_TABULAR

    def format_list_expanded(self: Formatter, item: FormattedNode) -> bool:
        """Write this list with each element starting on its own line.

        They might be multiple lines themselves
        """
        buffer = ["[", self.eol_str]
        first_elem = True
        for child in item.children:
            if not first_elem:
                buffer += [self.padded_comma_str, self.eol_str]
            self.indent(buffer, child.depth).append(child.value)
            first_elem = False

        buffer += self.eol_str
        self.indent(buffer, item.depth).append("]")

        item.value = self.combine(buffer)
        item.format = Format.EXPANDED
        return True

    def empty_dict(self: Formatter, depth: int) -> None:
        """Create an empty dict node."""
        obj = FormattedNode()
        obj.value = "{}"
        obj.value_length = 2
        obj.complexity = 0
        obj.depth = depth
        obj.kind = JsonValueKind.DICT
        obj.format = Format.INLINE
        return obj

    def format_dict_inline(self: Formatter, item: FormattedNode) -> bool:
        """Format this dict as a single line, if possible."""
        if (
            item.depth <= self.always_expand_depth
            or item.complexity > self.max_inline_complexity
        ):
            return False

        if any(fn.format != Format.INLINE for fn in item.children):
            return False

        use_bracket_padding = (
            self.nested_bracket_padding
            if item.complexity >= 2  # noqa: PLR2004
            else self.simple_bracket_padding
        )

        line_length = 2 + (2 if use_bracket_padding else 0)
        line_length += len(item.children) * len(self.padded_colon_str)
        line_length += (len(item.children) - 1) * len(self.padded_comma_str)
        line_length += sum([fn.name_length for fn in item.children])
        line_length += sum([fn.value_length for fn in item.children])
        if line_length > self.max_inline_length:
            return False

        buffer = ["{"]

        if use_bracket_padding:
            buffer += " "

        first_elem = True
        for prop in item.children:
            if not first_elem:
                buffer += self.padded_comma_str
            buffer += [prop.name, self.padded_colon_str, prop.value]
            first_elem = False

        if use_bracket_padding:
            buffer += " "
        buffer += "}"

        item.value = self.combine(buffer)
        debug(f"format_dict_inline: value_length = {line_length}")
        item.value_length = line_length
        item.format = Format.INLINE
        return True

    def format_dict_multiline_compact(  # noqa: C901
        self: Formatter,
        item: FormattedNode,
        force_expand_prop_names: bool = False,  # noqa: FBT002
    ) -> bool:
        """Try to format this dict spanning multiple lines.

        This may have several items per line, if possible.
        """
        debug("format_dict_multiline_compact()")
        if (
            not self.multiline_compact_dict
            or item.depth <= self.always_expand_depth
            or item.complexity > self.max_compact_list_complexity
        ):
            return False

        max_prop_name_length = max([fn.name_length for fn in item.children])

        buffer = ["{", self.eol_str]
        self.indent(buffer, item.depth + 1)

        line_length_so_far = 0
        child_index = 0
        while child_index < len(item.children):
            not_last_item = child_index < (len(item.children) - 1)
            prop = item.children[child_index]
            prop_buffer = [
                prop.name,
                self.padded_colon_str,
                prop.value,
            ]
            if force_expand_prop_names:
                prop_buffer.insert(1, " " * (max_prop_name_length - prop.name_length))
                prop.name_length = max_prop_name_length
            segment_length = (
                prop.name_length
                + len(self.padded_colon_str)
                + prop.value_length
                + len(self.padded_comma_str)
            )
            if child_index != 0:
                flag_new_line = False
                if prop.format not in [
                    Format.INLINE,
                    Format.INLINE_TABULAR,
                ]:
                    if item.children[child_index - 1].format in [
                        Format.INLINE,
                        Format.INLINE_TABULAR,
                    ]:
                        flag_new_line = True
                elif item.children[child_index - 1].format not in [
                    Format.INLINE,
                    Format.INLINE_TABULAR,
                ]:
                    flag_new_line = True
                elif (
                    line_length_so_far + segment_length
                    > self.max_inline_length + len(self.padded_comma_str)
                    and line_length_so_far > 0
                ):
                    debug(f"  max_inline_length={self.max_inline_length}")
                    debug(f"  line_length_so_far={line_length_so_far}")
                    debug(f"  segment_length={segment_length}")
                    debug(f"  buffer={buffer}¶")
                    flag_new_line = True
                if flag_new_line:
                    buffer += self.eol_str
                    self.indent(buffer, item.depth + 1)
                    line_length_so_far = 0
            buffer += prop_buffer
            if not_last_item:
                buffer += self.padded_comma_str

            child_index += 1
            line_length_so_far += segment_length

        buffer += self.eol_str
        self.indent(buffer, item.depth)
        buffer += "}"

        item.value = self.combine(buffer)
        item.format = Format.MULTILINE_COMPACT
        return True

    def format_table_dict_dict(self: Formatter, item: FormattedNode) -> bool:
        """Format this dict with one child dict per line.

        Those dicts are padded to line up nicely.
        """
        if self.table_dict_minimum_similarity > 100:  # noqa: PLR2004
            return False

        # Gather stats about our children's property order and width, if they're eligible dicts.
        prop_stats = self.get_property_stats(item)
        if not prop_stats:
            return False

        value_length = (
            sum([col.prop_name_length + col.max_value_size for col in prop_stats])
            + len(self.padded_colon_str) * len(prop_stats)
            + len(self.padded_comma_str) * (len(prop_stats) - 1)
            + 4
        )

        # Reformat our immediate children using the width info we've computed. Their
        # children aren't recomputed, so this part isn't recursive.
        for child in item.children:
            self.format_dict_table_row(child, prop_stats)
            child.value_length = value_length

        if self.format_dict_multiline_compact(item, True):
            return item
        return self.format_dict_expanded(item, True)

    def format_table_dict_list(self: Formatter, item: FormattedNode) -> bool:
        """Format this dict with one child list per line.

        Those lists are padded to line up nicely.
        """
        debug("format_table_dict_list()")
        if self.table_list_minimum_similarity > 100:  # noqa: PLR2004
            return False

        # Gather stats about our children's widths, if they're eligible lists.
        column_stats = self.get_list_stats(item)
        if not column_stats:
            return False

        value_length = (
            sum([col.max_value_size for col in column_stats])
            + len(self.padded_comma_str) * (len(column_stats) - 1)
            + 4
        )

        # Reformat our immediate children using the width info we've computed.
        # Their children aren't recomputed, so this part isn't recursive.
        for child in item.children:
            self.format_list_table_row(child, column_stats)
            child.value_length = value_length

        if self.format_dict_multiline_compact(item, True):
            return item
        return self.format_dict_expanded(item, True)

    def format_dict_table_row(
        self: Formatter,
        item: FormattedNode,
        column_stats_list: list[ColumnStats],
    ) -> None:
        """Format this dict in a single line, with padding to line up with siblings."""
        # Bundle up each property name, value, quotes, colons, etc., or equivalent empty space.
        highest_non_blank_index = -1
        prop_segment_strings = []
        for col_index, column_stats in enumerate(column_stats_list):
            buffer = []
            filtered_prop_nodes = list(
                filter(lambda fn: fn.name == column_stats.prop_name, item.children),
            )
            if len(filtered_prop_nodes) == 0:
                # This dict doesn't have this particular property. Pad it out.
                skip_length = (
                    column_stats.prop_name_length
                    + len(self.padded_colon_str)
                    + column_stats.max_value_size
                )
                buffer += " " * skip_length
            else:
                prop_node = filtered_prop_nodes[0]
                buffer += [column_stats.prop_name, self.padded_colon_str]
                buffer += column_stats.format_value(
                    prop_node.value,
                    prop_node.value_length,
                )

                highest_non_blank_index = col_index

            prop_segment_strings.append(self.combine(buffer))

        buffer = ["{ "]

        # Put them all together with commas in the right places.
        first_elem = True
        needs_comma = False
        for segment_index, segment_string in enumerate(prop_segment_strings):
            if needs_comma and segment_index <= highest_non_blank_index:
                buffer += self.padded_comma_str
            elif not first_elem:
                buffer += " " * len(self.padded_comma_str)
            buffer += segment_string
            needs_comma = len(segment_string.strip()) != 0
            first_elem = False

        buffer += " }"

        item.value = self.combine(buffer)
        item.format = Format.INLINE_TABULAR

    def format_dict_expanded(
        self: Formatter,
        item: FormattedNode,
        force_expand_prop_names: bool,
    ) -> bool:
        """Write this dict with each element starting on its own line.

        They might be multiple lines.
        """
        max_prop_name_length = max([fn.name_length for fn in item.children])

        buffer = ["{", self.eol_str]
        first_item = True
        for prop in item.children:
            if not first_item:
                buffer += [self.padded_comma_str, self.eol_str]
            self.indent(buffer, prop.depth).append(prop.name)

            if self.align_expanded_property_names or force_expand_prop_names:
                buffer += " " * (max_prop_name_length - prop.name_length)

            buffer += [self.padded_colon_str, prop.value]
            first_item = False

        buffer += self.eol_str
        self.indent(buffer, item.depth).append("}")

        item.value = self.combine(buffer)
        item.format = Format.EXPANDED
        return True

    def justify_parallel_numbers(
        self: Formatter,
        item_list: list[FormattedNode],
    ) -> None:
        """If the given nodes are all numbers and not too big or small.

        Format them to the same precision and width.
        """
        if len(item_list) < 2 or self.dont_justify_numbers:  # noqa: PLR2004
            return

        column_stats = ColumnStats(self.dont_justify_numbers)
        for prop_node in item_list:
            column_stats.update(prop_node, 0)

        if column_stats.kind not in (JsonValueKind.INT, JsonValueKind.FLOAT):
            return

        for prop_node in item_list:
            prop_node.value = column_stats.format_value(
                prop_node.value,
                prop_node.value_length,
            )
            debug(
                f"justify_parallel_numbers: value_length = {column_stats.max_value_size}",
            )
            prop_node.value_length = column_stats.max_value_size

    def get_property_stats(self: Formatter, item: FormattedNode) -> list[ColumnStats]:
        """Check if this node's dict children can be formatted as a table.

        If so, return stats about their properties, such as max width.
        Returns None if they're not eligible.
        """
        if len(item.children) < 2:  # noqa: PLR2004
            return None

        # Record every property across all dicts, count them, tabulate their
        # order, and find the longest.
        props = {}
        for child in item.children:
            if child.kind != JsonValueKind.DICT or child.format != Format.INLINE:
                return None

            for index, prop_node in enumerate(child.children):
                if prop_node.name not in props:
                    prop_stats = ColumnStats(self.dont_justify_numbers)
                    prop_stats.prop_name = prop_node.name
                    prop_stats.prop_name_length = prop_node.name_length
                    props[prop_stats.prop_name] = prop_stats
                else:
                    prop_stats = props[prop_node.name]

                prop_stats.update(prop_node, index)

        # Decide the order of the properties by sorting by the average index. It's a crude metric,
        # but it should handle the occasional missing property well enough.
        ordered_props = sorted(props.values(), key=lambda x: x.order_sum / x.count)
        total_prop_count = sum([cs.count for cs in ordered_props])

        # Calculate a score based on how many of all possible properties are present.
        # If the score is too low, these dicts are too different to try to line
        # up as a table.
        try:
            score = 100 * total_prop_count / (len(ordered_props) * len(item.children))
        except ZeroDivisionError:  # pragma: no cover
            return None
        if score < self.table_dict_minimum_similarity:
            return None

        # If the formatted lines would be too long, bail out.
        # Outer brackets & spaces
        line_length = 4
        # Property names
        line_length += sum([cs.prop_name_length for cs in ordered_props])
        # Colons
        line_length += len(self.padded_colon_str) * len(ordered_props)
        # Values
        line_length += sum([cs.max_value_size for cs in ordered_props])
        # Commas
        line_length += len(self.padded_comma_str) * (len(ordered_props) - 1)
        if line_length > self.max_inline_length:
            return None

        return ordered_props

    def get_list_stats(self: Formatter, item: FormattedNode) -> list[ColumnStats]:
        """Check if this node's list children can be formatted as a table.

        If so, gather stats like max width.
        Returns None if they're not eligible.
        """
        if len(item.children) < 2:  # noqa: PLR2004
            return None

        valid = all(
            fn.kind == JsonValueKind.LIST and fn.format == Format.INLINE
            for fn in item.children
        )
        if not valid:
            return None

        number_of_columns = max([len(fn.children) for fn in item.children])
        col_stats_list = [
            ColumnStats(self.dont_justify_numbers) for x in range(number_of_columns)
        ]

        for row_node in item.children:
            for index, child in enumerate(row_node.children):
                col_stats_list[index].update(child, index)

        # Calculate a score based on how rectangular the lists are. If they differ
        # too much in length, it probably doesn't make sense to format them together.
        total_elem_count = sum([len(fn.children) for fn in item.children])
        try:
            similarity = (
                100 * total_elem_count / (len(item.children) * number_of_columns)
            )
        except ZeroDivisionError:  # pragma: no cover
            return None
        if similarity < self.table_list_minimum_similarity:
            return None

        # If the formatted lines would be too long, bail out.
        line_length = 4
        line_length += sum([cs.max_value_size for cs in col_stats_list])
        line_length += (len(col_stats_list) - 1) * len(self.padded_comma_str)
        if line_length > self.max_inline_length:
            return None

        return col_stats_list
