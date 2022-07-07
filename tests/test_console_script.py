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
    assert "Format JSON into compact, human readble form" in ret.stdout
    assert "Indent N" in ret.stdout
    assert ret.stderr == ""
