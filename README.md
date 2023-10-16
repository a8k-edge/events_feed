# Run
- streamlit run src\ui.py

# Setup
The app using custom streamlit component
Run to build component:
- yarn build or npm build

# Tools
- pytest src\test.py --cov-report html --cov=.
- pre-commit run --all-files
- mypy --strict ./ --ignore-missing-imports
