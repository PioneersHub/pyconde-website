# Detect if uv is available and set up run command prefix
HAVE_UV := $(shell command -v uv 2> /dev/null)
ifdef HAVE_UV
    RUN = PYTHONWARNINGS=ignore::ResourceWarning uv run
else
    RUN = PYTHONWARNINGS=ignore::ResourceWarning
endif

build: redirects tracks topic-hubs lektor-build pagefind

lektor-build:
	$(RUN) lektor build -O site

pagefind:
	@echo "Building Pagefind index..."
	$(RUN) python -m pagefind --site site --output-subdir pagefind --quiet

redirects:
	@echo "Generating redirect pages + nginx/Caddy snippets..."
	$(RUN) python utils/generate_redirects.py

tracks:
	@echo "Regenerating per-track content folders..."
	$(RUN) python utils/generate_tracks.py
topic-hubs:
	@echo "Regenerating cross-edition topic-hub pages..."
	$(RUN) python utils/generate_topic_hubs.py

clean-plugin-cache:
	@echo "Clearing plugin and Lektor caches..."
	@rm -rf packages/yaml-databags/__pycache__
	@rm -rf site/.lektor
	@echo "Cache cleared!"

run: clean-plugin-cache
	$(RUN) lektor server -O site -p 5001 || (cd content && $(RUN) lektor server -O site -p 5001)
# Build the site, then serve the built site/ directory on a random
# local port (port 0 -> the OS picks a free ephemeral port). The
# chosen port is printed by the server on startup. Ctrl-C to stop.
serve: build
	@echo "Serving the built site/ on a random local port (Ctrl-C to stop)..."
	$(RUN) python -m http.server 0 --bind 127.0.0.1 --directory site
fetch-submissions:
	$(RUN) python utils/talks.py
	$(RUN) python utils/social_card_img_gen.py
sponsor-pages:
	$(RUN) python utils/sponsors.py
	@new_files=$$(git ls-files --others --exclude-standard content/sponsors/); \
	if [ -n "$$new_files" ]; then \
		echo "Adding new sponsor pages to git:"; \
		echo "$$new_files"; \
		echo "$$new_files" | xargs git add; \
	fi
flip-pricing:
	$(RUN) python utils/flip_pricing.py $(if $(PERIOD),--period $(PERIOD))
publish-video-batch:
	@if [ -z "$(YEAR)" ] || [ -z "$(BATCH)" ]; then \
		echo "Usage: make publish-video-batch YEAR=2026 BATCH=llm-agents"; \
		exit 2; \
	fi
	$(RUN) python utils/publish_video_batch.py --year $(YEAR) --batch $(BATCH)
