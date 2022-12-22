import argparse
import json
import logging

from compact_json import EolStyle, Formatter, _get_version


def command_line_parser():
    parser = argparse.ArgumentParser(
        description="Format JSON into compact, human readble form"
    )
    parser.add_argument("-V", "--version", action="store_true")
    parser.add_argument(
        "--crlf",
        default=False,
        action="store_true",
        help="Use Windows-style CRLR line endings",
    )
    parser.add_argument(
        "--max-inline-length",
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
        "--max-compact-list-complexity",
        metavar="N",
        type=int,
        default=1,
        help="Maximum nesting over multiple lines (default 1)",
    )
    parser.add_argument(
        "--bracket-padding",
        choices=["simple", "nested"],
        default="nested",
        help="If nested padding, add spaces inside outside brackes for nested lists/dicts",
    )
    parser.add_argument(
        "--indent", metavar="N", type=int, default=4, help="Indent N spaces (default=4)"
    )
    parser.add_argument(
        "--tab-indent", default=False, action="store_true", help="Use tabs to indent"
    )
    parser.add_argument(
        "--justify-numbers",
        default=False,
        action="store_true",
        help="Right-align numbers with matching precision",
    )
    parser.add_argument(
        "--prefix-string",
        metavar="STRING",
        help="String attached to the beginning of every line",
    )
    parser.add_argument(
        "--align-properties",
        default=False,
        action="store_true",
        help="Align property names of expanded dicts",
    )
    parser.add_argument(
        "--east-asian-chars",
        default=False,
        action="store_true",
        help="Treat strings as unicode East Asian characters",
    )
    parser.add_argument(
        "--no-ensure-ascii",
        default=False,
        action="store_true",
        help="Characters will be output as-is without ASCII conversion",
    )
    parser.add_argument(
        "--debug", default=False, action="store_true", help="Enable debug logging"
    )

    parser.add_argument("json", nargs="*", help="JSON file(s) to dump")

    return parser


def main():  # noqa: C901
    parser = command_line_parser()
    args = parser.parse_args()

    if args.version:
        print(_get_version())
    elif len(args.json) == 0:
        parser.print_help()
    else:
        formatter = Formatter()
        formatter.max_inline_length = args.max_inline_length
        formatter.max_inline_complexity = args.max_inline_complexity
        formatter.max_compact_list_complexity = args.max_compact_list_complexity
        formatter.indent_spaces = args.indent
        if args.crlf:
            formatter.json_eol_style = EolStyle.CRLF
        if args.align_properties:
            Formatter.align_expanded_property_names = True
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
        formatter.east_asian_string_widths = args.east_asian_chars 
        formatter.ensure_ascii = not args.no_ensure_ascii

        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.ERROR)

        formatter.table_dict_minimum_similarity = 30
        formatter.table_list_minimum_similarity = 50

        for filename in args.json:
            with open(filename, "r") as f:
                obj = json.load(f)
                json_string = formatter.serialize(obj)
                if args.crlf:
                    print(json_string, end="\r\n")
                else:
                    print(json_string, end="\n")


if __name__ == "__main__": # pragma: no cover
    # execute only if run as a script
    main()
