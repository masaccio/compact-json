from dataclasses import dataclass
import json

from decimal import Decimal, InvalidOperation
from enum import Enum
from logging import debug
from typing import List
from wcwidth import wcswidth


class EolStyle(Enum):
    CRLF = 1
    LF = 2


class JsonValueKind(Enum):
    UNDEFINED = 1
    DICT = 2
    LIST = 3
    STRING = 3
    INT = 4
    FLOAT = 5
    BOOLEAN = 6
    NULL = 7


class Format(Enum):
    INLINE = 1
    INLINE_TABULAR = 2
    MULTILINE_COMPACT = 3
    EXPANDED = 4


class FormattedNode:
    """Data about a JSON element and how we've formatted it"""

    def __init__(self):
        self.name = ""
        self.name_length = 0
        self.value = ""
        self.value_length = 0
        self.complexity = 0
        self.depth = 0
        self.kind = JsonValueKind.UNDEFINED
        self.format = Format.INLINE
        self.children = []

    def cleanup(self):
        if self.format != Format.INLINE:
            self.children = []
        for child in self.children:
            child.children = []


def _fixed_value(value, num_decimals: int):
    if num_decimals > 0:
        quantize_str = "0." + ("0" * (num_decimals - 1)) + "1"
    else:
        quantize_str = "0"

    try:
        return str(Decimal(value).quantize(Decimal(quantize_str)))
    except InvalidOperation:  # pragma: no cover
        return "*ERROR*"


class ColumnStats:
    """Used in figuring out how to format properties/list items as columns in a table format."""

    def __init__(self):
        debug("ColumnStats()")
        self.prop_name = ""
        self.prop_name_length = 0
        self.order_sum = 0
        self.count = 0
        self.max_value_size = 0
        self.kind = JsonValueKind.NULL
        self.chars_before_dec = 0
        self.chars_after_dec = 0

    def update(self, prop_node: FormattedNode, index: int):
        """Add stats about this FormattedNode to this PropertyStats."""
        self.order_sum += index
        self.count += 1
        debug("update()")
        debug(f"  value={prop_node.value}¶")
        debug(f"  max_value_size={self.max_value_size}")
        debug(f"  value_length={prop_node.value_length}")
        self.max_value_size = max([self.max_value_size, prop_node.value_length])
        self.kind = prop_node.kind

        if prop_node.kind == JsonValueKind.FLOAT:
            (whole, frac) = str(prop_node.value).split(".")
            self.chars_after_dec = max([self.chars_after_dec, len(frac)])
            self.chars_before_dec = max([self.chars_before_dec, len(whole)])
            debug(f"  chars_after_dec={self.chars_after_dec}")
            debug(f"  chars_before_dec={self.chars_before_dec}")
        elif prop_node.kind == JsonValueKind.INT:
            self.chars_before_dec = max([self.chars_before_dec, len(prop_node.value)])
            debug(f"  chars_before_dec={self.chars_before_dec}")

    def format_value(self, value: str, value_length: int, dont_justify: bool) -> str:
        debug("format_value()")
        debug(f"  value={value}¶")
        debug(f"  value_length={value_length}")
        debug(
            "  is_numeric="
            + str(
                self.kind == JsonValueKind.FLOAT or self.kind == JsonValueKind.INT
            ).lower()
        )

        if (
            self.kind == JsonValueKind.FLOAT or self.kind == JsonValueKind.INT
        ) and not dont_justify:
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
            + "¶"
        )
        return value.ljust(self.max_value_size - (value_length - len(value)))


@dataclass
class Formatter:
    """
    Class that outputs JSON formatted in a compact, user-readable way. Any given container
    is formatted in one of three ways:
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
        a value > disables table formatting with lists as rows.

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

    def __post_init__(self):
        self.eol_str = ""
        self.indent_str = ""
        self.padded_comma_str = ""
        self.padded_colon_str = ""
        self.indent_cache = {}

    def serialize(self, value) -> str:
        self.init_internals()
        return self.prefix_string + self.format_element(0, value).value

    def init_internals(self):
        """Set up some intermediate fields for efficiency."""
        self.eol_str = "\r\n" if self.json_eol_style == EolStyle.CRLF else "\n"
        self.indent_str = "\t" if self.use_tab_to_indent else " " * self.indent_spaces
        self.padded_comma_str = ", " if self.comma_padding else ","
        self.padded_colon_str = ": " if self.colon_padding else ":"

    def indent(self, buffer: List[str], depth: int) -> List[str]:
        if depth not in self.indent_cache:
            self.indent_cache[depth] = self.indent_str * depth
        buffer += [self.prefix_string, self.indent_cache[depth]]
        return buffer

    def combine(self, buffer: List[str]) -> str:
        return "".join(buffer)

    def format_element(self, depth: int, element) -> FormattedNode:
        """Base of recursion. Nearly everything comes through here."""
        if type(element) == list:
            formatted_item = self.format_list(depth, element)
        elif type(element) == dict:
            formatted_item = self.format_dict(depth, element)
        else:
            formatted_item = self.format_simple(depth, element)

        formatted_item.cleanup()
        return formatted_item

    def format_simple(self, depth: int, element) -> FormattedNode:
        """Formats a JSON element other than an list or dict."""
        simple_node = FormattedNode()
        simple_node.value = json.dumps(element, ensure_ascii=self.ensure_ascii)
        if self.east_asian_string_widths:
            simple_node.value_length = wcswidth(simple_node.value)
        else:
            simple_node.value_length = len(simple_node.value)
        simple_node.complexity = 0
        simple_node.depth = depth

        if element is None:
            simple_node.kind = JsonValueKind.NULL
            return simple_node

        if type(element) == bool:
            simple_node.kind = JsonValueKind.BOOLEAN
        elif type(element) == int:
            simple_node.kind = JsonValueKind.INT
        elif type(element) == float:
            simple_node.kind = JsonValueKind.FLOAT
        else:
            simple_node.kind = JsonValueKind.STRING

        return simple_node

    def format_list(self, depth: int, element) -> FormattedNode:
        # Recursively format all of this list's elements.
        items = list(map(lambda child: self.format_element(depth + 1, child), element))
        if len(items) == 0:
            return self.empty_list(depth)

        item = FormattedNode()
        item.kind = JsonValueKind.LIST
        item.complexity = max([fn.complexity for fn in items]) + 1
        item.depth = depth
        item.children = items

        if item.depth > self.always_expand_depth:
            if self.format_list_inline(item):
                return item

        self.justify_parallel_numbers(item.children)

        if item.depth > self.always_expand_depth:
            if self.format_list_multiline_compact(item):
                return item

        if self.format_table_list_dict(item):
            return item

        if self.format_table_list_list(item):
            return item

        self.format_list_expanded(item)
        return item

    def format_dict(self, depth: int, element: dict) -> FormattedNode:
        # Recursively format all of this dict's property values.
        items = []
        for k, v in element.items():
            elem = self.format_element(depth + 1, v)
            elem.name = json.dumps(str(k), ensure_ascii=self.ensure_ascii)
            if self.east_asian_string_widths:
                elem.name_length = wcswidth(elem.name)
            else:
                elem.name_length = len(elem.name)
            items.append(elem)

        if len(items) == 0:
            return self.empty_dict(depth)

        item = FormattedNode()
        item.kind = JsonValueKind.DICT
        item.complexity = max([fn.complexity for fn in items]) + 1
        item.depth = depth
        item.children = items

        if item.depth > self.always_expand_depth:
            if self.format_dict_inline(item):
                return item

        if self.format_table_dict_dict(item):
            return item

        if self.format_table_dict_list(item):
            return item

        self.format_dict_expanded(item, False)
        return item

    def empty_list(self, depth: int) -> FormattedNode:
        arr = FormattedNode()
        arr.value = "[]"
        debug("empty_list: value_length = 2")
        arr.value_length = 2
        arr.complexity = 0
        arr.depth = depth
        arr.kind = JsonValueKind.LIST
        arr.format = Format.INLINE
        return arr

    def format_list_inline(self, item: FormattedNode) -> bool:
        """Try to format this list in a single line, if possible."""
        if item.complexity > self.max_inline_complexity:
            return False

        if any([fn.format != Format.INLINE for fn in item.children]):
            return False

        if item.complexity >= 2:
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
        if len(item.value) != item.value_length:
            debug(
                f"MISMATCH: {len(item.value)} != {item.value_length} value={item.value}"
            )
        return True

    def format_list_multiline_compact(self, item: FormattedNode) -> bool:
        """Try to format this list, spanning multiple lines, but with several items
        per line, if possible."""
        debug("format_list_multiline_compact()")
        if item.complexity > self.max_compact_list_complexity:
            return False

        if any([fn.format != Format.INLINE for fn in item.children]):
            return False

        buffer = ["[", self.eol_str]
        self.indent(buffer, item.depth + 1)

        line_length_so_far = 0
        child_index = 0
        while child_index < len(item.children):
            not_last_item = child_index < (len(item.children) - 1)

            item_length = item.children[child_index].value_length
            # segment_length = (
            #     item_length + len(self.padded_comma_str) if not_last_item else 0
            # )
            segment_length = item_length + len(self.padded_comma_str)
            if (
                line_length_so_far + segment_length > self.max_inline_length
                and line_length_so_far > 0
            ):
                debug(f"  max_inline_length={self.max_inline_length}")
                debug(f"  line_length_so_far={line_length_so_far}")
                debug(f"  segment_length={segment_length}")
                debug(f"  buffer={buffer}¶")
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

    def format_table_list_dict(self, item: FormattedNode) -> bool:
        """Format this list with one child dict per line, and those dicts
        padded to line up nicely."""
        if self.table_dict_minimum_similarity > 100.5:
            return False

        # Gather stats about our children's property order and width, if they're eligible dicts.
        col_stats = self.get_property_stats(item)
        if not col_stats:
            return False

        # Reformat our immediate children using the width info we've computed. Their
        # children aren't recomputed, so this part isn't recursive.
        for child in item.children:
            self.format_dict_table_row(child, col_stats)

        return self.format_list_expanded(item)

    def format_table_list_list(self, item: FormattedNode) -> bool:
        debug("format_table_list_list()")
        if self.table_list_minimum_similarity > 100.5:
            return False

        # Gather stats about our children's item widths, if they're eligible lists.
        column_stats = self.get_list_stats(item)
        if not column_stats:
            return False

        # Reformat our immediate children using the width info we've computed. Their
        # children aren't recomputed, so this part isn't recursive.
        for child in item.children:
            self.format_list_table_row(child, column_stats)

        return self.format_list_expanded(item)

    def format_list_table_row(
        self, item: FormattedNode, column_stats_list: List[ColumnStats]
    ):
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
                self.dont_justify_numbers,
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
        debug(f"  value={item.value}¶")
        item.format = Format.INLINE_TABULAR

    def format_list_expanded(self, item: FormattedNode) -> bool:
        """Write this list with each element starting on its own line.
        They might be multiple lines themselves"""
        buffer = ["[", self.eol_str]
        first_elem = True
        for child in item.children:
            if not first_elem:
                buffer += [",", self.eol_str]
            self.indent(buffer, child.depth).append(child.value)
            first_elem = False

        buffer += self.eol_str
        self.indent(buffer, item.depth).append("]")

        item.value = self.combine(buffer)
        item.format = Format.EXPANDED
        return True

    def empty_dict(self, depth: int):
        obj = FormattedNode()
        obj.value = "{}"
        obj.value_length = 2
        obj.complexity = 0
        obj.depth = depth
        obj.kind = JsonValueKind.DICT
        obj.format = Format.INLINE
        return obj

    def format_dict_inline(self, item: FormattedNode) -> bool:
        """Format this dict as a single line, if possible."""
        if item.complexity > self.max_inline_complexity:
            return False

        if any([fn.format != Format.INLINE for fn in item.children]):
            return False

        use_bracket_padding = (
            self.nested_bracket_padding
            if item.complexity >= 2
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

    def format_table_dict_dict(self, item: FormattedNode) -> bool:
        """Format this dict with one child dict per line, and those dicts
        padded to line up nicely."""
        if self.table_dict_minimum_similarity > 100.5:
            return False

        # Gather stats about our children's property order and width, if they're eligible dicts.
        prop_stats = self.get_property_stats(item)
        if not prop_stats:
            return False

        # Reformat our immediate children using the width info we've computed. Their
        # children aren't recomputed, so this part isn't recursive.
        for child in item.children:
            self.format_dict_table_row(child, prop_stats)

        return self.format_dict_expanded(item, True)

    def format_table_dict_list(self, item: FormattedNode) -> bool:
        """Format this dict with one child list per line, and those lists padded to
        line up nicely."""
        debug("format_table_dict_list()")
        if self.table_list_minimum_similarity > 100.5:
            return False

        # Gather stats about our children's widths, if they're eligible lists.
        column_stats = self.get_list_stats(item)
        if not column_stats:
            return False

        # Reformat our immediate children using the width info we've computed.
        # Their children aren't recomputed, so this part isn't recursive.
        for child in item.children:
            self.format_list_table_row(child, column_stats)

        return self.format_dict_expanded(item, True)

    def format_dict_table_row(
        self, item: FormattedNode, column_stats_list: List[ColumnStats]
    ):
        """Format this dict in a single line, with padding to line up with siblings."""
        # Bundle up each property name, value, quotes, colons, etc., or equivalent empty space.
        highest_non_blank_index = -1
        prop_segment_strings = []
        for col_index, column_stats in enumerate(column_stats_list):
            buffer = []
            filtered_prop_nodes = list(
                filter(lambda fn: fn.name == column_stats.prop_name, item.children)
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
                    self.dont_justify_numbers,
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
        self, item: FormattedNode, force_expand_prop_names: bool
    ) -> bool:
        """Write this dict with each element starting on its own line.
        They might be multiple lines"""
        max_prop_name_length = max([fn.name_length for fn in item.children])

        # debug(f"format_dict_expanded(): max_prop_name_length={max_prop_name_length}")

        buffer = ["{", self.eol_str]
        first_item = True
        for prop in item.children:
            if not first_item:
                buffer += [",", self.eol_str]
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

    def justify_parallel_numbers(self, item_list: List[FormattedNode]):
        """If the given nodes are all numbers and not too big or small, format them
        to the same precision and width."""
        if len(item_list) < 2 or self.dont_justify_numbers:
            return

        column_stats = ColumnStats()
        for prop_node in item_list:
            column_stats.update(prop_node, 0)

        if (
            column_stats.kind != JsonValueKind.INT
            and column_stats.kind != JsonValueKind.FLOAT
        ):
            return

        for prop_node in item_list:
            prop_node.value = column_stats.format_value(
                prop_node.value, prop_node.value_length, self.dont_justify_numbers
            )
            debug(
                f"justify_parallel_numbers: value_length = {column_stats.max_value_size}"
            )
            prop_node.value_length = column_stats.max_value_size

    def get_property_stats(self, item: FormattedNode) -> List[ColumnStats]:
        """Check if this node's dict children can be formatted as a table, and
        if so, return stats about their properties, such as max width.
        Returns None if they're not eligible."""
        if len(item.children) < 2:
            return None

        # Record every property across all dicts, count them, tabulate their
        # order, and find the longest.
        props = {}
        for child in item.children:
            if child.kind != JsonValueKind.DICT or child.format != Format.INLINE:
                return None

            for index, prop_node in enumerate(child.children):
                if prop_node.name not in props:
                    prop_stats = ColumnStats()
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

    def get_list_stats(self, item: FormattedNode) -> List[ColumnStats]:
        """Check if this node's list children can be formatted as a table, and if
        so, gather stats like max width.
        Returns None if they're not eligible."""
        if len(item.children) < 2:
            return None

        valid = all(
            [
                fn.kind == JsonValueKind.LIST and fn.format == Format.INLINE
                for fn in item.children
            ]
        )
        if not valid:
            return None

        number_of_columns = max([len(fn.children) for fn in item.children])
        col_stats_list = [ColumnStats() for x in range(number_of_columns)]

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
