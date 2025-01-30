build:
	lektor build -O tmp
run:
	lektor server -O tmp -p 5001
fetch-submissions:
	python utils/talks.py
