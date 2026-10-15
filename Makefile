PYTHON ?= python3

.PHONY: check test

check:
	$(PYTHON) scripts/check.py
	$(PYTHON) scripts/verify_provenance.py
	$(MAKE) test

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v
