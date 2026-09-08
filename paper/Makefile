TECTONIC ?= tectonic
BUILD_DIR := build
SOURCE := main_publication.tex
OUTPUT := benchmark_publication.pdf

.PHONY: publication clean

publication: $(OUTPUT)

$(OUTPUT): $(SOURCE) figures/publication_benchmark_map.tex \
	figures/rubric_anatomy.tex figures/performance_overview.tex \
	figures/subject_contrast.tex figures/item_difficulty.tex \
	figures/token_ablation.tex figures/resource_frontiers.tex
	mkdir -p $(BUILD_DIR)
	$(TECTONIC) -X compile $(SOURCE) --outdir $(BUILD_DIR)
	cp $(BUILD_DIR)/main_publication.pdf $(OUTPUT)

clean:
	rm -f $(BUILD_DIR)/main_publication.pdf \
		$(BUILD_DIR)/main_publication.log $(OUTPUT)

