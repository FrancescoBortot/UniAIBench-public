PYTHON ?= .venv/bin/python

TOOLKIT := benchmark-toolkit
STUDY := uniaibench
ANALYSIS := $(STUDY)/analysis
PAPER := $(STUDY)/paper

.PHONY: check check-strict check-toolkit check-uniaibench check-publication \
	check-publication-strict check-boundaries check-site-figures figure-families \
	validate-configs validate-rubric-template validate-judgment-template \
	validate-study-release validate-model-catalog test test-toolkit test-uniaibench test-publication check-analysis \
	check-model-docs tables check-tables figures paper

check: check-boundaries check-toolkit check-uniaibench check-publication

check-strict: check check-site-figures
	$(PYTHON) tools/validate_public_repository.py --strict

check-toolkit: validate-configs validate-rubric-template validate-judgment-template test-toolkit
	$(PYTHON) $(TOOLKIT)/harness/benchmark_harness.py --help >/dev/null
	$(PYTHON) $(TOOLKIT)/harness/google_benchmark_harness.py --help >/dev/null

check-uniaibench: validate-study-release validate-model-catalog check-tables test-uniaibench check-analysis check-model-docs

check-publication: test-publication
	$(PYTHON) tools/validate_public_repository.py

check-publication-strict: test-publication
	$(PYTHON) tools/validate_public_repository.py --strict

check-boundaries:
	$(PYTHON) tools/check_dependency_direction.py

figure-families:
	$(PYTHON) $(ANALYSIS)/scripts/build_selected_charts.py
	$(PYTHON) $(ANALYSIS)/scripts/build_selected_token_cost_charts.py
	$(PYTHON) $(ANALYSIS)/scripts/build_token_cost_focus_charts.py
	$(PYTHON) $(ANALYSIS)/scripts/build_response_time_focus_charts.py
	$(PYTHON) $(ANALYSIS)/scripts/build_main_chart_collection.py

check-site-figures: figure-families
	git diff --exit-code -- $(ANALYSIS)/figures

validate-rubric-template:
	$(PYTHON) $(TOOLKIT)/tools/validate_rubric.py $(TOOLKIT)/templates/rubric.template.json --template

validate-judgment-template:
	$(PYTHON) $(TOOLKIT)/tools/validate_judgment.py $(TOOLKIT)/templates/judgment.template.json --template

validate-configs:
	$(PYTHON) $(TOOLKIT)/tools/validate_config.py $(abspath $(TOOLKIT)/configs/benchmark_config.template.json)
	$(PYTHON) $(TOOLKIT)/tools/validate_config.py $(abspath $(TOOLKIT)/configs/google_benchmark_config.template.json)

validate-model-catalog:
	$(PYTHON) $(ANALYSIS)/tools/validate_model_catalog.py

validate-study-release:
	$(PYTHON) $(ANALYSIS)/tools/validate_study_release.py

test: test-toolkit test-publication

test-toolkit:
	$(PYTHON) -m unittest discover -s $(TOOLKIT)/tests -v

test-uniaibench:
	$(PYTHON) -m unittest discover -s $(ANALYSIS)/tests -v

test-publication:
	$(PYTHON) -m unittest discover -s tests -v

check-analysis:
	$(PYTHON) $(PAPER)/scripts/build_item_difficulty_figure.py
	git diff --exit-code -- $(PAPER)/figures/item_difficulty.tex

check-model-docs:
	$(PYTHON) $(ANALYSIS)/scripts/build_model_catalog_docs.py --check

tables:
	$(PYTHON) $(ANALYSIS)/scripts/build_public_tables.py --write

check-tables:
	$(PYTHON) $(ANALYSIS)/scripts/build_public_tables.py --check

figures: tables figure-families
	$(PYTHON) $(ANALYSIS)/scripts/build_model_catalog_docs.py
	$(PYTHON) $(ANALYSIS)/scripts/build_model_specifications_pdf.py
	$(PYTHON) $(ANALYSIS)/scripts/build_website_benchmark_data.py

paper:
	$(PYTHON) $(PAPER)/scripts/build_item_difficulty_figure.py
	$(MAKE) -C $(PAPER) publication
