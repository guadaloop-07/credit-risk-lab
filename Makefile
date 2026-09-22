.PHONY: setup formato lint pruebas precommit verificar

setup:
	uv sync --all-groups
	uv run pre-commit install

formato:
	uv run ruff check --fix .
	uv run ruff format .

lint:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy src tests

pruebas:
	uv run pytest

precommit:
	uv run pre-commit run --all-files

verificar: lint pruebas
