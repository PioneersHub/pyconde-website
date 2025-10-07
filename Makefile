# Detect if uv is available and set up run command prefix
HAVE_UV := $(shell command -v uv 2> /dev/null)
ifdef HAVE_UV
    RUN = PYTHONWARNINGS=ignore::ResourceWarning uv run
else
    RUN = PYTHONWARNINGS=ignore::ResourceWarning
endif

build:
	$(RUN) lektor build -O tmp
run:
	$(RUN) lektor server -O tmp -p 5001 || (cd content && $(RUN) lektor server -O tmp -p 5001)
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
