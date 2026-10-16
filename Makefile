.PHONY: check
check:
	python3 tools/verify_reference.py
	python3 tools/verify_harmony_reference.py
	python3 modules/midi-harmony/generate.py --check
	python3 modules/midi-harmony/degrees/generate.py --check
