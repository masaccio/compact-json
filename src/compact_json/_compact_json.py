from compact_json import Formatter, EolStyle, _get_version

import argparse
import json


def command_line_parser():
    parser = argparse.ArgumentParser(
        description="Format JSON into compact, human readble form"
    )
    parser.add_argument("-V", "--version", action="store_true")
    parser.add_argument(
        "--indent", metavar="N", type=int, default=4, help="Indent N spaces (default=4)"
    )
    parser.add_argument(
        "--max-inline-length",
        metavar="N",
        type=int,
        default=50,
        help="Limit inline elements to N chars, excluding "
        "indentation and leading property names (default=50)",
    )
    parser.add_argument("json", nargs="*", help="JSON file(s) to dump")
    return parser


def main():
    parser = command_line_parser()
    args = parser.parse_args()

    if args.version:
        print(_get_version())
    elif len(args.json) == 0:
        parser.print_help()
    else:
        formatter = Formatter()
        if args.indent is not None:
            formatter.indent_spaces = args.indent
        formatter.max_inline_length = 110
        formatter.max_inline_complexity = 10
        formatter.max_compact_list_complexity = 1
        formatter.table_dict_minimum_similarity = 30
        formatter.table_list_minimum_similarity = 50
        formatter.json_eol_style = EolStyle.LF

        for filename in args.json:
            with open(filename, "r") as f:
                obj = json.load(f)
                json_string = formatter.serialize(obj)
                print(json_string)


if __name__ == "__main__":
    # execute only if run as a script
    main()
