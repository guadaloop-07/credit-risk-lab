"""Pruebas de normalización de las fuentes externas."""

from __future__ import annotations

import json
import ssl
import zipfile
from email.message import Message
from io import BytesIO
from unittest.mock import patch

import pandas as pd
import pytest

from riesgo_crediticio.datos.calidad import evaluar_tabla
from riesgo_crediticio.datos.ingesta import (
    ErrorIngesta,
    _extraer_imor_exportacion_cnbv,
    construir_tabla,
    descargar_excel_cnbv,
    normalizar_banxico,
    normalizar_inegi,
    normalizar_inpc_csv,
)


class RespuestaHTTPFalsa:
    """Respuesta HTTP mínima para probar descargas sin acceder a la red."""

    def __init__(self, contenido: bytes, tipo_contenido: str) -> None:
        self._contenido = contenido
        self.headers = Message()
        self.headers["Content-Type"] = tipo_contenido
        self.headers["ETag"] = '"version-1"'
        self.headers["Last-Modified"] = "Tue, 08 Sep 2026 16:36:23 GMT"

    def __enter__(self) -> RespuestaHTTPFalsa:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._contenido


def _xlsx_minimo() -> bytes:
    contenido = BytesIO()
    with zipfile.ZipFile(contenido, "w") as archivo:
        archivo.writestr("[Content_Types].xml", "<Types />")
    return contenido.getvalue()


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


def test_descarga_excel_cnbv_valida_formato_y_metadatos() -> None:
    """La descarga automática conserva los metadatos HTTP del XLSX oficial."""
    contenido = _xlsx_minimo()
    respuesta = RespuestaHTTPFalsa(
        contenido,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    with patch("riesgo_crediticio.datos.ingesta.urlopen", return_value=respuesta):
        resultado = descargar_excel_cnbv("https://ejemplo.gob.mx/imor.xlsx")

    assert resultado.contenido == contenido
    assert resultado.etag == '"version-1"'
    assert resultado.ultima_modificacion == "Tue, 08 Sep 2026 16:36:23 GMT"


def test_descarga_excel_cnbv_conserva_verificacion_tls() -> None:
    """La excepción de cadena incompleta no desactiva TLS ni hostnames."""
    respuesta = RespuestaHTTPFalsa(
        _xlsx_minimo(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    with patch(
        "riesgo_crediticio.datos.ingesta.urlopen", return_value=respuesta
    ) as urlopen:
        descargar_excel_cnbv("https://ejemplo.gob.mx/imor.xlsx")

    contexto = urlopen.call_args.kwargs["context"]
    assert isinstance(contexto, ssl.SSLContext)
    assert contexto.check_hostname is True
    assert contexto.verify_mode == ssl.CERT_REQUIRED


def test_descarga_excel_cnbv_rechaza_respuesta_que_no_es_xlsx() -> None:
    """Una respuesta HTML no se debe archivar ni intentar interpretar como Excel."""
    respuesta = RespuestaHTTPFalsa(b"<html>error</html>", "text/html")

    with patch("riesgo_crediticio.datos.ingesta.urlopen", return_value=respuesta):
        with pytest.raises(ErrorIngesta, match="tipo de contenido XLSX"):
            descargar_excel_cnbv("https://ejemplo.gob.mx/imor.xlsx")


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
