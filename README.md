- streamlit run src\ui.py

- pre-commit run --all-files
- mypy --strict ./ --ignore-missing-imports
- pytest src\test.py --cov-report html --cov=.
