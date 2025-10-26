# Detect if uv is available and set up run command prefix
HAVE_UV := $(shell command -v uv 2> /dev/null)
ifdef HAVE_UV
    RUN = PYTHONWARNINGS=ignore::ResourceWarning uv run
else
    RUN = PYTHONWARNINGS=ignore::ResourceWarning
endif

build:
	$(RUN) lektor build -O site

clean-plugin-cache:
	@echo "Clearing plugin and Lektor caches..."
	@rm -rf packages/yaml-databags/__pycache__
	@rm -rf site/.lektor
	@echo "Cache cleared!"

run: clean-plugin-cache
	$(RUN) lektor server -O site -p 5001 || (cd content && $(RUN) lektor server -O site -p 5001)
fetch-submissions:
	$(RUN) python utils/talks.py
	$(RUN) python utils/social_card_img_gen.py
sponsor-pages:
	$(RUN) python utils/sponsors.py
activate-conference:
	$(RUN) utils/activate-conference
disable-conference:
	$(RUN) ./utils/disable-conference
landing-page:
	$(RUN) python utils/landing_page.py
