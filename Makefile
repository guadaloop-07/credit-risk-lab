.PHONY: setup formato lint pruebas precommit verificar datos validar modelar

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

datos:
	uv run python -m riesgo_crediticio.datos.ingesta $(if $(IMOR_CSV),--imor-csv "$(IMOR_CSV)") $(if $(IMOR_FECHA),--columna-fecha "$(IMOR_FECHA)") $(if $(IMOR_VALOR),--columna-imor "$(IMOR_VALOR)")

validar:
	uv run python -m riesgo_crediticio.datos.calidad

modelar:
	uv run python -m riesgo_crediticio.modelos.backtest
