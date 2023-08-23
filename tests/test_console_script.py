import re

import pytest

from compact_json import _get_version


def test_version(script_runner):
    ret = script_runner.run("compact-json", "--version", print_result=False)
    assert ret.success
    assert ret.stdout == _get_version() + "\n"
    assert ret.stderr == ""


def test_help(script_runner):
    ret = script_runner.run("compact-json", "--help", print_result=False)
    assert ret.success
    assert "Format JSON into compact, human readable form" in ret.stdout
    assert "Indent N" in ret.stdout
    assert ret.stderr == ""


REF_ARG_TEST = """//{
//	"ObjectColumnsArrayRows": {
//		"Katherine": [ "blue"      , "lightblue", "black"        ], 
//		"Logan"    : [ "yellow"    , "blue"     , "black", "red" ], 
//		"Erik"     : [ "red"       , "purple"                    ], 
//		"Jean"     : [ "lightgreen", "yellow"   , "black"        ]
//	}, 
//	"ArrayColumnsArrayRows" : [
//		[ 0.1, 3.5, 10.50, 6.5, 2.50, 0.60 ], [ 0.1, 0.1,  1.20, 2.1, 6.70, 4.40 ], [ 0.4, 1.9,  4.40, 5.4, 2.35, 2.01 ], 
//		[ 7.4, 1.2,  0.01, 0.1, 2.91, 0.20 ]
//	], 
//	"DissimilarArrayRows"   : {
//		"primes"     : [ 2, 3, 5, 7, 11                   ], 
//		"powersOf2"  : [ 1, 2, 4, 8, 16, 32, 64, 128, 256 ], 
//		"factorsOf12": [ 2, 2, 3                          ], 
//		"someZeros"  : [ 0, 0, 0, 0                       ]
//	}
//}
"""

REF_UNICODE_TEST = """{
    "Thai": {
        "Abkhazia": "อับฮาเซีย", 
        "Afghanistan": "อัฟกานิสถาน", 
        "Albania": "แอลเบเนีย"
    }, 
    "Lao": {"Afghanistan": "ອັຟການິດສະຖານ"}, 
    "Uyghur": {"Albania": "ئالبانىيە"}, 
    "Hindi, Marathi, Sanskrit": {"Albania": "अल्बानिया"}, 
    "Western Armenian": {"Albania": "Ալբանիա"}
}
"""


def test_args(script_runner, pytestconfig):
    ret = script_runner.run(
        "compact-json",
        "--indent=2",
        "--tab-indent",
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
        print("===== TEST")
        print(json_string_dbg)
        print("===== REF")
        print(ref_json_dbg)
        print("=====")

    assert ret.stderr == ""
    assert ret.success
    assert ret.stdout == REF_ARG_TEST


def test_unicode(script_runner):
    ret = script_runner.run(
        "compact-json",
        "--east-asian-chars",
        "--no-ensure-ascii",
        "--crlf",
        "tests/data/test-issue-4a.json",
        print_result=False,
    )
    assert ret.stderr == ""
    assert ret.success
    ref = REF_UNICODE_TEST.replace("\n", "\r\n")
    assert ret.stdout == ref


def test_help(script_runner):
    ret = script_runner.run("compact-json")
    assert ret.stderr == ""
    assert ret.success
    assert "[--prefix-string STRING] [--align-properties]" in ret.stdout


def test_debug(script_runner):
    ret = script_runner.run("compact-json", "--debug", "tests/data/test-1.json")
    assert "DEBUG:compact_json.formatter:format_table_dict_list" in ret.stderr
    assert ret.success
    assert '"title": "Sample Konfabulator Widget"' in ret.stdout


@pytest.mark.script_launch_mode("subprocess")
def test_main(script_runner):
    ret = script_runner.run("python3", "-m", "compact_json", "--help")
    assert ret.stderr == ""
    assert ret.success
    assert "[-h] [-V] [--output-filename" in ret.stdout


@pytest.mark.script_launch_mode("subprocess")
def test_stdin(script_runner):
    with open("tests/data/test-bool.json") as fh:
        ret = script_runner.run("compact-json", "-", stdin=fh)
        assert ret.stderr == ""
        assert ret.success
        assert ret.stdout == '{ "bools": {"true": true, "false": false} }\n'


def test_multifile(script_runner):
    ret = script_runner.run(
        "compact-json",
        "tests/data/test-bool.json",
        "tests/data/test-bool.json",
    )
    assert ret.stderr == ""
    assert ret.success
    assert ret.stdout == '{ "bools": {"true": true, "false": false} }\n' * 2
