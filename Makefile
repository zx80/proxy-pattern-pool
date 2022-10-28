# convenient makefile

SHELL	= /bin/bash
.ONESHELL:

MODULE	= ProxyPatternPool

F.md	= $(wildcard *.md)
F.pdf	= $(F.md:%.md=%.pdf)

# PYTHON	= /snap/bin/pypy3
# PYTHON	= python3
PYTHON	= python
PIP		= venv/bin/pip

PYTEST	= pytest
PYTOPT	=

.PHONY: check check.mypy check.flake8 check.black check.pytest check.demo check.coverage check.pymarkdown
check.mypy: venv
	source venv/bin/activate
	mypy $(MODULE).py

check.flake8: venv
	source venv/bin/activate
	# flake8 --ignore=E127,E402,E501,F401 $(MODULE).py
	flake8 $(MODULE).py

check.black: venv
	source venv/bin/activate
	black --check $(MODULE).py

check.pytest: venv
	source venv/bin/activate
	$(PYTEST) $(PYTOPT) test.py

check.coverage: venv
	source venv/bin/activate
	coverage run -m $(PYTEST) $(PYTOPT) test.py
	coverage html $(MODULE).py
	coverage report --fail-under=100 --include='*/$(MODULE).py'

check.pymarkdown:
	source venv/bin/activate
	pymarkdown scan $(F.md)

check: check.mypy check.pymarkdown check.black check.flake8 check.pytest check.coverage

.PHONY: clean clean.venv
clean:
	$(RM) -r __pycache__ */__pycache__ *.egg-info dist build .mypy_cache .pytest_cache .coverage htmlcov
	$(RM) $(F.pdf)

clean.venv: clean
	$(RM) -r venv

# for local testing
venv:
	$(PYTHON) -m venv venv
	$(PIP) install -U pip
	$(PIP) install -e .
	$(PIP) install -r dev-requirements.txt

$(MODULE).egg-info: venv
	$(PIP) install -e .

# generate source and built distribution
dist:
	$(PYTHON) setup.py sdist bdist_wheel

.PHONY: publish
publish: dist
	# provide pypi login/pw or token somewhere…
	echo twine upload --repository $(MODULE) dist/*

# generate pdf doc
MD2PDF  = pandoc -f markdown -t latex -V papersize:a4 -V geometry:hmargin=2.5cm -V geometry:vmargin=3cm

%.pdf: %.md
	$(MD2PDF) -o $@ $<
