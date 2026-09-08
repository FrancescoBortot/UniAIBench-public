PYTHON ?= python3

.PHONY: check check-strict validate-rubric-template validate-judgment-template paper

check: validate-rubric-template validate-judgment-template
	$(PYTHON) tools/validate_public_repository.py
	$(PYTHON) benchmark_harness.py --help >/dev/null

check-strict: check
	$(PYTHON) tools/validate_public_repository.py --strict

validate-rubric-template:
	$(PYTHON) tools/validate_rubric.py rubrics/templates/rubric.template.json --template

validate-judgment-template:
	$(PYTHON) tools/validate_judgment.py schemas/judgment.template.json --template

paper:
	$(MAKE) -C paper publication

