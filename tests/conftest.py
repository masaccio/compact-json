import pytest


def pytest_addoption(parser):
    parser.addoption("--test-file", action="store", default=None)
