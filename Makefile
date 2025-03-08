# convenient makefile

SHELL	= /bin/bash
.ONESHELL:

MODULE	= ProxyPatternPool

F.md	= $(wildcard *.md)
F.pdf	= $(F.md:%.md=%.pdf)

# PYTHON	= /snap/bin/pypy3
# PYTHON	= python3
PYTHON	= python
PYTEST	= pytest --log-level=debug --capture=tee-sys
PYTOPT	=

.PHONY: check.mypy
check.mypy: dev
	source venv/bin/activate
	mypy --implicit-optional $(MODULE).py

.PHONY: check.pyright
check.pyright: dev
	source venv/bin/activate
	pyright $(MODULE).py

IGNORE = E227,E402,E501,W504

.PHONY: check.ruff
check.ruff: dev
	source venv/bin/activate
	ruff check $(MODULE).py

.PHONY: check.flake8
check.flake8: dev
	source venv/bin/activate
	flake8 --ignore=E128,$(IGNORE) $(MODULE).py

.PHONY: check.black
check.black: dev
	source venv/bin/activate
	black --check $(MODULE).py

.PHONY: check.pytest
check.pytest: dev
	source venv/bin/activate
	$(PYTEST) $(PYTOPT) test.py

# expected coverage may be overriden
COVER   = 100.0

.PHONY: check.coverage
check.coverage: dev
	source venv/bin/activate
	coverage run -m $(PYTEST) $(PYTOPT) test.py
	# coverage html $(MODULE).py
	coverage report --fail-under=$(COVER) --show-missing --precision=1 --include='*/$(MODULE).py'

.PHONY: check.pymarkdown
check.pymarkdown: dev
	source venv/bin/activate
	pymarkdown scan $(F.md)

# check.black check.pyright
.PHONY: check
check: check.pyright check.pymarkdown check.ruff check.pytest check.coverage

.PHONY: clean
clean:
	$(RM) -r __pycache__ */__pycache__ dist build .mypy_cache .pytest_cache .coverage htmlcov .ruff_cache
	$(RM) $(F.pdf)

.PHONY: clean.venv
clean.venv: clean
	$(RM) -r venv *.egg-info

.PHONY: clean.dev
clean.dev: clean.venv

venv:
	$(PYTHON) -m venv venv
	source venv/bin/activate
	pip install -U pip

.PHONY: dev
dev: venv/.dev

venv/.dev: venv
	source venv/bin/activate
	pip install -e .[dev,local]
	touch $@

.PHONY: pub
pub: venv/.pub

# only on local venv
venv/.pub: dev
	source venv/bin/activate
	pip install -e .[pub]
	touch $@

# generate source and built distribution
dist: pub
	source venv/bin/activate
	$(PYTHON) -m build

.PHONY: publish
publish: dist
	# provide pypi login/pw or token somewhere…
	echo venv/bin/twine upload dist/*

# generate pdf doc
MD2PDF  = pandoc -f markdown -t latex -V papersize:a4 -V geometry:hmargin=2.5cm -V geometry:vmargin=3cm

%.pdf: %.md
	$(MD2PDF) -o $@ $<
