import pytest
import re

from compact_json import _get_version


def test_version(script_runner):
    ret = script_runner.run("compact-json", "--version", print_result=False)
    assert ret.success
    assert ret.stdout == _get_version() + "\n"
    assert ret.stderr == ""


def test_help(script_runner):
    ret = script_runner.run("compact-json", "--help", print_result=False)
    assert ret.success
    assert "Format JSON into compact, human readble form" in ret.stdout
    assert "Indent N" in ret.stdout
    assert ret.stderr == ""


REF_ARG_TEST = """//{
//	"ObjectColumnsArrayRows": {
//		"Katherine": [ "blue"      , "lightblue", "black"        ],
//		"Logan"    : [ "yellow"    , "blue"     , "black", "red" ],
//		"Erik"     : [ "red"       , "purple"                    ],
//		"Jean"     : [ "lightgreen", "yellow"   , "black"        ]
//	},
//	"ArrayColumnsArrayRows": [
//		[ 0.1, 3.5, 10.5, 6.5, 2.5, 0.6 ], [ 0.1, 0.1, 1.2, 2.1, 6.7, 4.4 ], [ 0.4, 1.9, 4.4, 5.4, 2.35, 2.01 ], 
//		[ 7.4, 1.2, 0.01, 0.1, 2.91, 0.2 ]
//	],
//	"DissimilarArrayRows": {
//		"primes"     : [ 2, 3, 5, 7, 11                   ],
//		"powersOf2"  : [ 1, 2, 4, 8, 16, 32, 64, 128, 256 ],
//		"factorsOf12": [ 2, 2, 3                          ],
//		"someZeros"  : [ 0, 0, 0, 0                       ]
//	}
//}
"""


def test_args(script_runner, pytestconfig):
    ret = script_runner.run(
        "compact-json",
        "--indent=2",
        "--tab-indent",
        "--crlf",
        "--justify-numbers",
        "--prefix-string=//",
        "--align-properties",
        "--bracket-padding=simple",
        "--max-compact-list-complexity=2",
        "--max-inline-length=120",
        "tests/data/test-12.json",
        print_result=False,
    )

    if pytestconfig.getoption("test_verbose") and ret.stdout != REF_ARG_TEST:
        json_string_dbg = ">" + re.sub(r"\n", "<\n>", ret.stdout) + "<"
        ref_json_dbg = ">" + re.sub(r"\n", "<\n>", REF_ARG_TEST) + "<"
        print(f"===== TEST")
        print(json_string_dbg)
        print(f"===== REF")
        print(ref_json_dbg)
        print(f"=====")

    assert ret.success
    assert ret.stdout == REF_ARG_TEST
    assert ret.stderr == ""
