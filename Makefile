.PHONY: run test validate baseline serve clean

run:
	python run.py --data data --out predictions.csv

serve:
	python run.py --serve --port 8000

validate:
	python validate_submission.py predictions.csv

test:
	python -m pytest tests/ -v

baseline:
	python baseline_3sigma.py --data data --out baseline_predictions.csv
	python validate_submission.py baseline_predictions.csv

clean:
	rm -rf __pycache__ .pytest_cache
