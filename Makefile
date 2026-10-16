.PHONY: check
check:
	python3 tools/verify_reference.py
	python3 tools/verify_follow_reference.py
