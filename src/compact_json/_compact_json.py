import argparse
import json
import logging
import sys

import compact_json
from compact_json import EolStyle, Formatter, _get_version

logger = logging.getLogger(compact_json.__name__)


def command_line_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Format JSON into compact, human readable form",
    )
    parser.add_argument("-V", "--version", action="store_true")

    parser.add_argument(
        "--output",
        "-o",
        action="append",
        help="The output file name(s). The number of output file names must match "
        "the number of input files.",
    )
    parser.add_argument(
        "--align-expanded-property-names",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--align-properties",
        default=False,
        action="store_true",
        help="Align property names of expanded dicts",
    )
    parser.add_argument(
        "--always-expand-depth",
        default="never",
        choices=["never", "root", "children"],
        help="Depth at which lists/dicts are always fully expanded",
    )
    parser.add_argument(
        "--bracket-padding",
        choices=["simple", "nested"],
        default="nested",
        help="If nested padding, add spaces inside outside brackes for nested lists/dicts",
    )
    parser.add_argument(
        "--colon-padding",
        action="store_true",
        default=True,
        help="Include a space after property colons",
    )
    parser.add_argument(
        "--comma-padding",
        action="store_true",
        default=True,
        help="Includes a space after commas separating list items and dict properties.",
    )
    parser.add_argument(
        "--crlf",
        default=False,
        action="store_true",
        help="Use Windows-style CRLF line endings",
    )
    parser.add_argument(
        "--debug",
        default=False,
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--east-asian-chars",
        default=False,
        action="store_true",
        help="Treat strings as unicode East Asian characters",
    )
    parser.add_argument(
        "--indent",
        "-i",
        metavar="N",
        type=int,
        default=4,
        help="Indent N spaces (default=4)",
    )
    parser.add_argument(
        "--justify-numbers",
        default=False,
        action="store_true",
        help="Right-align numbers with matching precision",
    )
    parser.add_argument(
        "--max-compact-list-complexity",
        metavar="N",
        type=int,
        default=1,
        help="Maximum nesting over multiple lines (default 1)",
    )
    parser.add_argument(
        "--max-inline-length",
        "-l",
        metavar="N",
        type=int,
        default=50,
        help="Limit inline elements to N chars, excluding "
        "indentation and leading property names (default=50)",
    )
    parser.add_argument(
        "--max-inline-complexity",
        metavar="N",
        type=int,
        default=2,
        help="Maximum nesting: 0=basic types, 1=dict/list, 2=all (default=2)",
    )
    parser.add_argument(
        "--multiline-compact-dict",
        action="store_true",
        default=False,
        help="Format dict into multi-line compact style like list",
    )
    parser.add_argument(
        "--no-ensure-ascii",
        default=False,
        action="store_true",
        help="Characters will be output as-is without ASCII conversion",
    )
    parser.add_argument(
        "--omit-trailing-whitespace",
        default=False,
        action="store_true",
        help="Remove any trailing whitespace from output lines",
    )
    parser.add_argument(
        "--prefix-string",
        metavar="STRING",
        help="String attached to the beginning of every line",
    )
    parser.add_argument(
        "--tab-indent",
        default=False,
        action="store_true",
        help="Use tabs to indent",
    )
    parser.add_argument(
        "--table-dict-minimum-similarity",
        type=int,
        default=75,
        metavar="[0-101]",
        choices=range(102),
        help="Inline dict similarity threshold (101 disables table formatting",
    )
    parser.add_argument(
        "--table-list-minimum-similarity",
        type=int,
        metavar="[0-101]",
        choices=range(102),
        default=75,
        help="Inline list similarity threshold (101 disables table formatting",
    )

    parser.add_argument(
        "json",
        nargs="*",
        type=argparse.FileType("r"),
        help='JSON file(s) to parse (or stdin with "-")',
    )
    return parser


def main() -> None:  # noqa: C901, PLR0915, PLR0912
    parser = command_line_parser()

    def die(message: str) -> None:
        print(f"{parser.prog}: {message}", file=sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    if args.version:
        print(_get_version())
    elif len(args.json) == 0:
        parser.print_help()
    else:
        formatter = Formatter()
        formatter.comma_padding = args.comma_padding
        formatter.colon_padding = args.colon_padding
        formatter.max_inline_length = args.max_inline_length
        formatter.max_inline_complexity = args.max_inline_complexity
        formatter.max_compact_list_complexity = args.max_compact_list_complexity
        formatter.multiline_compact_dict = args.multiline_compact_dict
        formatter.indent_spaces = args.indent
        if args.crlf:
            formatter.json_eol_style = EolStyle.CRLF
        if args.align_properties:
            formatter.align_expanded_property_names = True
        if args.bracket_padding == "simple":
            formatter.nested_bracket_padding = False
            formatter.simple_bracket_padding = True
        else:
            formatter.nested_bracket_padding = True
            formatter.simple_bracket_padding = False
        if args.tab_indent:
            formatter.use_tab_to_indent = True
        if not args.justify_numbers:
            formatter.dont_justify_numbers = False
        if args.prefix_string is not None:
            formatter.prefix_string = args.prefix_string
        formatter.omit_trailing_whitespace = args.omit_trailing_whitespace
        formatter.east_asian_string_widths = args.east_asian_chars
        formatter.ensure_ascii = not args.no_ensure_ascii

        hdlr = logging.StreamHandler()
        hdlr.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
        logger.addHandler(hdlr)
        if args.debug:
            logger.setLevel("DEBUG")
        else:
            logger.setLevel("ERROR")

        formatter.table_dict_minimum_similarity = 30
        formatter.table_list_minimum_similarity = 50

        line_ending = "\r\n" if args.crlf else "\n"

        in_files = args.json
        out_files = args.output

        if out_files is None:
            for fh in args.json:
                obj = json.load(fh)
                json_string = formatter.serialize(obj)
                print(json_string, end=line_ending)
            return

        if len(in_files) != len(out_files):
            die("the numbers of input and output file names do not match")

        for fn_in, fn_out in zip(args.json, args.output):
            obj = json.load(fn_in)
            json_string = formatter.dump(obj, output_file=fn_out)


if __name__ == "__main__":  # pragma: no cover
    # execute only if run as a script
    main()
