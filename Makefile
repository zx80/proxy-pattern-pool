# convenient makefile

SHELL	= /bin/bash
.ONESHELL:

MODULE	= ProxyPatternPool
VENV    = venv

F.md	= $(wildcard *.md)
F.pdf	= $(F.md:%.md=%.pdf)

# PYTHON	= /snap/bin/pypy3
# PYTHON	= python3
PYTHON	= python
PYTEST	= pytest --log-level=debug --capture=tee-sys
PYTOPT	=

.PHONY: check.mypy
check.mypy: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	mypy --implicit-optional $(MODULE).py

.PHONY: check.pyright
check.pyright: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	pyright $(MODULE).py

IGNORE = E227,E402,E501

.PHONY: check.ruff
check.ruff: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	ruff check --ignore=$(IGNORE) $(MODULE).py

.PHONY: check.flake8
check.flake8: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	flake8 --ignore=E127,E128,$(IGNORE) $(MODULE).py

.PHONY: check.black
check.black: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	black --check $(MODULE).py

.PHONY: check.pytest
check.pytest: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	$(PYTEST) $(PYTOPT) test.py

.PHONY: check.coverage
check.coverage: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	coverage run -m $(PYTEST) $(PYTOPT) test.py
	coverage html $(MODULE).py
	coverage report --fail-under=100 --show-missing --precision=1 --include='*/$(MODULE).py'

.PHONY: check.pymarkdown
check.pymarkdown: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	pymarkdown scan $(F.md)

# check.black check.pyright
.PHONY: check
check: check.mypy check.pyright check.pymarkdown check.ruff check.pytest check.coverage

.PHONY: clean clean.venv
clean:
	$(RM) -r __pycache__ */__pycache__ dist build .mypy_cache .pytest_cache .coverage htmlcov .ruff_cache
	$(RM) $(F.pdf)

clean.venv: clean
	$(RM) -r venv *.egg-info

# for local testing
venv:
	$(PYTHON) -m venv venv
	source venv/bin/activate
	pip install -U pip
	pip install -e .[dev,pub,local]

# generate source and built distribution
dist: $(VENV)
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
