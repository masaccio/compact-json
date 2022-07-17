mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
current_dir := $(notdir $(patsubst %/,%,$(dir $(mkfile_path))))

# Change this to the name of a code-signing certificate. A self-signed
# certificate is suitable for this.
IDENTITY=python@figsandfudge.com

RELEASE_TARBALL=dist/compact-json-$(shell python3 setup.py --version).tar.gz

.PHONY: clean test coverage sdist upload

all:
	@echo "make targets:"
	@echo "    test       - run pytest with all tests"
	@echo "    coverage   - run pytest and generate coverage report"
	@echo "    sdist      - build source distribution"
	@echo "    upload     - upload source package to PyPI"
	@echo "    clean      - delete temporary files for test, coverage, etc."

$(RELEASE_TARBALL): sdist

sdist:
	python3 setup.py sdist

upload: $(RELEASE_TARBALL)
	tox
	twine upload $(RELEASE_TARBALL)

docs:
	python3 setup.py build_sphinx

test:
	PYTHONPATH=src python3 -m pytest tests

coverage:
	PYTHONPATH=src python3 -m pytest --cov=compact-json --cov-report=html

clean:
	rm -rf src/compact_json.egg-info
	rm -rf coverage_html_report
	rm -rf dist
	rm -rf build
	rm -rf .tox
	rm -rf .pytest_cache
