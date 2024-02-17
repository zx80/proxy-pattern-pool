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

.PHONY: check check.mypy check.flake8 check.black check.pytest check.demo check.coverage check.pymarkdown
check.mypy: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	mypy --implicit-optional $(MODULE).py

check.flake8: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	# flake8 --ignore=E127,E402,E501,F401 $(MODULE).py
	flake8 --ignore=E127,E128,E227,E402,E501 $(MODULE).py

check.black: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	black --check $(MODULE).py

check.pytest: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	$(PYTEST) $(PYTOPT) test.py

check.coverage: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	coverage run -m $(PYTEST) $(PYTOPT) test.py
	coverage html $(MODULE).py
	coverage report --fail-under=100 --show-missing --include='*/$(MODULE).py'

check.pymarkdown: $(VENV)
	[ "$(VENV)" ] && source $(VENV)/bin/activate
	pymarkdown scan $(F.md)

# check.black
check: check.mypy check.pymarkdown check.flake8 check.pytest check.coverage

.PHONY: clean clean.venv
clean:
	$(RM) -r __pycache__ */__pycache__ dist build .mypy_cache .pytest_cache .coverage htmlcov
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
	echo twine upload dist/*

# generate pdf doc
MD2PDF  = pandoc -f markdown -t latex -V papersize:a4 -V geometry:hmargin=2.5cm -V geometry:vmargin=3cm

%.pdf: %.md
	$(MD2PDF) -o $@ $<
