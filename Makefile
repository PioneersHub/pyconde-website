build:
	lektor build -O tmp
run:
	lektor server -O tmp -p 5001
fetch-submissions:
	python utils/talks.py
	find ./assets/static/media/social/talks/*.png ! -name 'social-card.png' -type f -exec rm {} +
	python utils/social_card_img_gen.py
