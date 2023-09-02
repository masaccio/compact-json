import pytest


def pytest_addoption(parser):
    parser.addoption("--test-file", action="store", default=None)
    parser.addoption("--test-verbose", action="store_true", default=False)
    parser.addoption("--test-debug", action="store_true", default=False)
