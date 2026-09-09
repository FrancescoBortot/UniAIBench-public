PYTHON ?= python3

.PHONY: check check-strict validate-configs validate-rubric-template \
	validate-judgment-template validate-model-catalog test check-analysis \
	check-model-docs figures paper

check: validate-configs validate-rubric-template validate-judgment-template \
	validate-model-catalog test check-analysis check-model-docs
	$(PYTHON) tools/validate_public_repository.py
	$(PYTHON) benchmark_harness.py --help >/dev/null

check-strict: check
	$(PYTHON) tools/validate_public_repository.py --strict

validate-rubric-template:
	$(PYTHON) tools/validate_rubric.py rubrics/templates/rubric.template.json --template

validate-judgment-template:
	$(PYTHON) tools/validate_judgment.py schemas/judgment.template.json --template

validate-configs:
	$(PYTHON) tools/validate_config.py configs/benchmark_config.template.json
	$(PYTHON) tools/validate_config.py configs/google_benchmark_config.template.json

validate-model-catalog:
	$(PYTHON) tools/validate_model_catalog.py

test:
	$(PYTHON) -m unittest discover -s tests -v

check-analysis:
	$(PYTHON) paper/scripts/build_item_difficulty_figure.py
	git diff --exit-code -- paper/figures/item_difficulty.tex

check-model-docs:
	$(PYTHON) analysis/scripts/build_model_catalog_docs.py --check

figures:
	$(PYTHON) analysis/scripts/build_model_catalog_docs.py
	$(PYTHON) analysis/scripts/build_selected_charts.py
	$(PYTHON) analysis/scripts/build_selected_token_cost_charts.py
	$(PYTHON) analysis/scripts/build_token_cost_focus_charts.py
	$(PYTHON) analysis/scripts/build_response_time_focus_charts.py
	$(PYTHON) analysis/scripts/build_main_chart_collection.py
	$(PYTHON) analysis/scripts/build_model_specifications_pdf.py
	$(PYTHON) analysis/scripts/build_website_benchmark_data.py
	cp analysis/grafici_selezionati/output/pdf/selected_correctness_charts.pdf paper/figures/
	cp analysis/grafici_token_costi_focus/output/pdf/focused_token_cost_charts.pdf paper/figures/
	cp analysis/grafici_tempo_risposta_focus/output/pdf/focused_response_time_charts.pdf paper/figures/

paper: figures
	$(PYTHON) paper/scripts/build_item_difficulty_figure.py
	$(MAKE) -C paper publication
