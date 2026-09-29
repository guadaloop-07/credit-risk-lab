"""Pruebas de normalización de las fuentes externas."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from riesgo_crediticio.datos.calidad import evaluar_tabla
from riesgo_crediticio.datos.ingesta import (
    _extraer_imor_exportacion_cnbv,
    construir_tabla,
    normalizar_banxico,
    normalizar_inegi,
    normalizar_inpc_csv,
)


def test_extrae_imor_consumo_del_formato_ancho_cnbv() -> None:
    """La exportación oficial conserva sólo la fila agregada de IMOR consumo."""
    exportacion = pd.DataFrame(
        {
            "Tema": [5, 5],
            "Concepto": ["IMOR consumo", "IMORA consumo"],
            202401: [8.2, 9.1],
            202402: [8.4, 9.2],
        }
    )

    resultado = _extraer_imor_exportacion_cnbv(exportacion)

    assert resultado.to_dict("records") == [
        {"mes_observacion": pd.Timestamp("2024-01-31"), "imor_pct": 8.2},
        {"mes_observacion": pd.Timestamp("2024-02-29"), "imor_pct": 8.4},
    ]


def test_normaliza_respuesta_inegi() -> None:
    """La respuesta de tabulados se transforma a una serie mensual ordenada."""
    contenido = json.dumps(
        [
            {
                "Data": [
                    {
                        "Serie": {
                            "Obs": [
                                {"TimePeriod": "2024/02", "CurrentValue": "2.5"},
                                {"TimePeriod": "2024/01", "CurrentValue": "2.7"},
                            ]
                        }
                    }
                ]
            }
        ]
    ).encode()

    resultado = normalizar_inegi(contenido, "desempleo_pct")

    assert resultado["mes_observacion"].tolist() == [
        pd.Timestamp("2024-01-31"),
        pd.Timestamp("2024-02-29"),
    ]
    assert resultado["desempleo_pct"].tolist() == [2.7, 2.5]


def test_normaliza_csv_vigente_de_inpc() -> None:
    """La exportación del INPC conserva meses y niveles tras sus metadatos."""
    contenido = (
        '"Instituto Nacional de Estadística y Geografía",\r\n'
        '"Periodicidad","Mensual"\r\n'
        '"Fecha"," 865541 "\r\n'
        '"Ene 2024","132.1"\r\n'
        '"Feb 2024","132.4"\r\n'
    ).encode("latin-1")

    resultado = normalizar_inpc_csv(contenido)

    assert resultado.to_dict("records") == [
        {"mes_observacion": pd.Timestamp("2024-01-31"), "inpc_indice": 132.1},
        {"mes_observacion": pd.Timestamp("2024-02-29"), "inpc_indice": 132.4},
    ]


def test_normaliza_respuesta_banxico() -> None:
    """La respuesta del SIE conserva su tasa promedio mensual."""
    contenido = json.dumps(
        {"bmx": {"series": [{"datos": [{"fecha": "31/01/2024", "dato": "11.48"}]}]}}
    ).encode()

    resultado = normalizar_banxico(contenido, "tasa_nominal_pct")

    assert resultado.to_dict("records") == [
        {"mes_observacion": pd.Timestamp("2024-01-31"), "tasa_nominal_pct": 11.48}
    ]


def test_construye_inflacion_y_tasa_real() -> None:
    """La tasa real resta inflación anual sin modificar las observaciones base."""
    fechas = pd.date_range("2023-01-31", periods=13, freq="ME")
    base = pd.DataFrame({"mes_observacion": fechas})
    resultado = construir_tabla(
        base.assign(imor_pct=10.0),
        base.assign(inpc_indice=[100.0] * 12 + [104.0]),
        base.assign(desempleo_pct=3.0),
        base.assign(tasa_nominal_pct=8.0),
    )

    assert pd.isna(resultado.loc[11, "inflacion_interanual_pct"])
    assert resultado.loc[12, "inflacion_interanual_pct"] == pytest.approx(4.0)
    assert resultado.loc[12, "tasa_real_pct"] == pytest.approx(4.0)


def test_detecta_mes_faltante_en_tabla_analitica() -> None:
    """El control bloquea una tabla que pierde un mes entre observaciones."""
    tabla = pd.DataFrame(
        {
            "mes_observacion": [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-03-31")],
            "imor_pct": [10.0, 10.1],
            "inpc_indice": [100.0, 101.0],
            "desempleo_pct": [3.0, 3.1],
            "tasa_nominal_pct": [8.0, 8.0],
            "tasa_real_pct": [None, None],
            "indicador_covid": [0, 0],
            "ruptura_contable": [1, 1],
        }
    )

    reporte = evaluar_tabla(tabla)

    assert reporte["estado"] == "error"
    assert any("Faltan 1 meses" in error for error in reporte["errores"])
