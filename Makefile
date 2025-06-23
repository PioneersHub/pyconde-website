build:
	lektor build -O tmp
run:
	lektor server -O tmp -p 5001 || (cd content && lektor server -O tmp -p 5001)
fetch-submissions:
	python utils/talks.py
	python utils/social_card_img_gen.py
sponsor-pages:
	python utils/sponsors.py
activate-conference:
	utils/activate-conference
disable-conference:
	./utils/disable-conference
landing-page:
	python utils/landing_page.py
