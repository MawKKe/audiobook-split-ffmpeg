VENV_DIR := .venv

sync-venv: requirements-dev.txt
	python3 -m venv ${VENV_DIR}
	./${VENV_DIR}/bin/pip install --upgrade pip
	./${VENV_DIR}/bin/pip install -r requirements-dev.txt
	@echo "---"
	@echo "NOTE: Please run 'source ./${VENV_DIR}/bin/activate' to use the env"
	@echo "      or run 'Python: Select Interpreter' from VSCode command palette"

pin-requirements: requirements.txt requirements-dev.txt
	@echo "---------------------------------------------"
	@echo "Done.\n"
	@echo "Remember to commit changes to pyproject.toml,"
	@echo  " requirements.txt, and requirements-dev.txt"
	@echo "---------------------------------------------"

requirements.txt: pyproject.toml
	pip-compile \
	    --generate-hashes \
	    --strip-extras \
	    --output-file=requirements.txt \
	    pyproject.toml

requirements-dev.txt: requirements.txt
	pip-compile \
	    --strip-extras \
	    --constraint requirements.txt \
	    --output-file=requirements-dev.txt \
	    --extra dev \
	    pyproject.toml

# This is basically 'python3 -m build'
build:
	pyproject-build

fmt format:
	ruff format

lint:
	ruff check --output-format=full

test: test-pytest test-mypy

test-pytest:
	pytest --cov=audiobook_split_ffmpeg tests/ -v

test-mypy:
	mypy src

.PHONY: sync-venv pin-requirements build lint test
