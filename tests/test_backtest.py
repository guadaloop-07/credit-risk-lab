"""Pruebas del benchmark de persistencia y su evaluación temporal."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd
import pytest

from riesgo_crediticio.modelos.backtest import (
    ErrorModelo,
    calcular_metricas,
    crear_caracteristicas,
    ejecutar,
    pronosticar_persistencia,
    separar_prueba_final,
)


def tabla_analitica(filas: int = 115) -> pd.DataFrame:
    """Construye una tabla mensual sintética con historia suficiente para evaluar."""
    indice = range(filas)
    return pd.DataFrame(
        {
            "mes_observacion": pd.date_range("2017-01-31", periods=filas, freq="ME"),
            "imor_pct": [8.0 + 0.05 * valor for valor in indice],
            "inpc_indice": [100.0 + valor for valor in indice],
            "desempleo_pct": [3.0 + 0.01 * valor for valor in indice],
            "tasa_nominal_pct": [7.0 + 0.02 * valor for valor in indice],
            "inflacion_interanual_pct": [4.0 + 0.01 * valor for valor in indice],
            "tasa_real_pct": [3.0 + 0.01 * valor for valor in indice],
            "indicador_covid": [0 for _ in indice],
            "ruptura_contable": [1 for _ in indice],
        }
    )


def test_crea_rezagos_sin_usar_valores_contemporaneos() -> None:
    """Las variables macro de la primera fila útil pertenecen a t-3."""
    resultado = crear_caracteristicas(tabla_analitica(8))

    primera_con_macro = resultado.iloc[2]
    assert primera_con_macro["mes_observacion"] == pd.Timestamp("2017-04-30")
    assert primera_con_macro["imor_lag_1"] == pytest.approx(8.1)
    assert primera_con_macro["tasa_real_lag_3"] == pytest.approx(3.0)
    assert primera_con_macro["inflacion_interanual_lag_3"] == pytest.approx(4.0)
    assert primera_con_macro["desempleo_lag_3"] == pytest.approx(3.0)


def test_particion_reduce_prueba_a_doce_meses_si_hay_menos_de_120_filas() -> None:
    """La prueba final conserva al menos 96 observaciones de entrenamiento."""
    particion = separar_prueba_final(crear_caracteristicas(tabla_analitica()))

    assert particion.meses_prueba == 12
    assert len(particion.entrenamiento) == 102
    assert len(particion.prueba) == 12


def test_persistencia_usa_exclusivamente_el_imor_del_mes_anterior() -> None:
    """Cada predicción a un paso coincide con el rezago observado, no con el objetivo."""
    caracteristicas = crear_caracteristicas(tabla_analitica(8))
    predicciones = pronosticar_persistencia(caracteristicas)

    assert predicciones["prediccion_pct"].tolist() == pytest.approx(
        [8.0, 8.05, 8.1, 8.15, 8.2, 8.25, 8.3]
    )
    assert (
        predicciones["prediccion_pct"].tolist()
        != predicciones["imor_observado_pct"].tolist()
    )


def test_metricas_calculan_errores_en_puntos_porcentuales() -> None:
    """MAE, RMSE y sesgo conservan la convención de signo documentada."""
    predicciones = pd.DataFrame({"error_pp": [1.0, -2.0]})

    metricas = calcular_metricas(predicciones, escala_mase=0.5)

    assert metricas["mae_pp"] == pytest.approx(1.5)
    assert metricas["rmse_pp"] == pytest.approx(math.sqrt(2.5))
    assert metricas["sesgo_pp"] == pytest.approx(-0.5)
    assert metricas["mase"] == pytest.approx(3.0)
    assert metricas["mejora_vs_persistencia_pct"] == 0.0


def test_ejecutar_guarda_predicciones_y_reporte_reproducibles(tmp_path: Path) -> None:
    """La interfaz guarda artefactos y documenta la partición aplicada."""
    entrada = tmp_path / "conjunto_analitico.parquet"
    salida = tmp_path / "modelos"
    tabla_analitica().to_parquet(entrada, index=False)

    resultado = ejecutar(argparse.Namespace(entrada=entrada, directorio_salida=salida))

    reporte = json.loads((salida / "reporte_persistencia.json").read_text())
    assert resultado == salida.resolve()
    assert (salida / "predicciones_persistencia_backtest.parquet").is_file()
    assert (salida / "predicciones_persistencia_prueba.parquet").is_file()
    assert reporte["particion_final"]["meses_prueba"] == 12


def test_rechaza_muestra_que_no_conserva_minimo_de_entrenamiento() -> None:
    """No se reduce la prueba por debajo de doce meses para ocultar poca muestra."""
    with pytest.raises(ErrorModelo, match="mínimo de 96"):
        separar_prueba_final(crear_caracteristicas(tabla_analitica(98)))
