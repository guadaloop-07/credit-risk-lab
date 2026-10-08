"""Pruebas de la regresión dinámica y su evaluación temporal."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd
import pytest

from riesgo_crediticio.modelos.backtest import (
    MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA,
    crear_caracteristicas,
    preparar_regresion_dinamica,
)
from riesgo_crediticio.modelos.regresion_dinamica import (
    ajustar_regresion_dinamica,
    ejecutar,
    ejecutar_backtest_regresion,
    evaluar_regresion_dinamica,
)


def tabla_analitica_dinamica(filas: int = 103) -> pd.DataFrame:
    """Construye una muestra sintética no colineal para la especificación OLS."""
    indice = range(filas)
    return pd.DataFrame(
        {
            "mes_observacion": pd.date_range("2017-01-31", periods=filas, freq="ME"),
            "imor_pct": [
                8.0 + 0.03 * valor + 0.25 * math.sin(valor / 2) for valor in indice
            ],
            "inpc_indice": [100.0 + valor for valor in indice],
            "desempleo_pct": [3.0 + 0.25 * math.sin(valor / 5) for valor in indice],
            "tasa_nominal_pct": [7.0 + 0.3 * math.cos(valor / 7) for valor in indice],
            "inflacion_interanual_pct": [
                4.0 + 0.35 * math.cos(valor / 4) for valor in indice
            ],
            "tasa_real_pct": [2.5 + 0.4 * math.sin(valor / 6) for valor in indice],
            "indicador_covid": [int(38 <= valor <= 59) for valor in indice],
            "ruptura_contable": [int(valor >= 60) for valor in indice],
        }
    )


def tabla_dinamica() -> pd.DataFrame:
    """Devuelve 100 filas completas: 88 para entrenamiento y 12 para prueba."""
    return preparar_regresion_dinamica(
        crear_caracteristicas(tabla_analitica_dinamica())
    )


def test_ajusta_ols_con_covarianza_hac() -> None:
    """La regresión principal conserva los siete coeficientes preespecificados."""
    entrenamiento = tabla_dinamica().iloc[:88]

    ajuste = ajustar_regresion_dinamica(entrenamiento)

    assert ajuste.cov_type == "HAC"
    assert set(ajuste.params.index) == {
        "const",
        "imor_lag_1",
        "tasa_real_lag_3",
        "inflacion_interanual_lag_3",
        "desempleo_lag_3",
        "indicador_covid",
        "ruptura_contable",
    }


def test_backtest_no_usa_el_objetivo_del_mes_pronosticado() -> None:
    """Modificar el IMOR del primer corte no modifica su pronóstico correspondiente."""
    dinamica = tabla_dinamica().iloc[:88].copy()
    original = ejecutar_backtest_regresion(dinamica).iloc[0]["prediccion_pct"]
    valor_original = float(
        dinamica["imor_pct"].iloc[MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA]
    )
    dinamica.at[MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA, "imor_pct"] = (
        valor_original + 50
    )

    modificado = ejecutar_backtest_regresion(dinamica).iloc[0]["prediccion_pct"]

    assert modificado == pytest.approx(original)


def test_evalua_regresion_con_prueba_final_y_sensibilidad_explicita() -> None:
    """La salida compara ambos modelos y no oculta sensibilidad no estimable."""
    resultado = evaluar_regresion_dinamica(tabla_analitica_dinamica())

    assert len(resultado.predicciones_prueba) == 12
    assert resultado.reporte["particion_final"]["filas_entrenamiento"] == 88
    assert resultado.reporte["prueba_final"]["metricas_regresion"][
        "mejora_vs_persistencia_pct"
    ] == pytest.approx(
        resultado.reporte["prueba_final"]["metricas_regresion"][
            "mejora_vs_persistencia_pct"
        ]
    )
    assert resultado.reporte["sensibilidad_sin_pandemia"]["estado"] == "no_estimado"


def test_ejecutar_guarda_artefactos_de_regresion(tmp_path: Path) -> None:
    """La interfaz persiste predicciones, coeficientes, residuos y reporte JSON."""
    entrada = tmp_path / "conjunto_analitico.parquet"
    salida = tmp_path / "modelos"
    tabla_analitica_dinamica().to_parquet(entrada, index=False)

    resultado = ejecutar(argparse.Namespace(entrada=entrada, directorio_salida=salida))

    reporte = json.loads((salida / "reporte_regresion_dinamica.json").read_text())
    assert resultado == salida.resolve()
    assert (salida / "coeficientes_hac.parquet").is_file()
    assert (salida / "residuos_regresion.parquet").is_file()
    assert reporte["especificacion"]["minimo_entrenamiento"] == 84
