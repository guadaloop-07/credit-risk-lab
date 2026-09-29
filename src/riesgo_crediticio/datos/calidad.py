"""Controles de calidad para el conjunto analítico mensual."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import pandas as pd

COLUMNAS_REQUERIDAS = (
    "mes_observacion",
    "imor_pct",
    "inpc_indice",
    "desempleo_pct",
    "tasa_nominal_pct",
    "tasa_real_pct",
    "indicador_covid",
    "ruptura_contable",
)
COLUMNAS_OBSERVADAS = (
    "imor_pct",
    "inpc_indice",
    "desempleo_pct",
    "tasa_nominal_pct",
)


class ReporteCalidad(TypedDict):
    """Forma serializable del reporte de calidad."""

    estado: str
    resumen: dict[str, int | str | None]
    errores: list[str]
    advertencias: list[str]


def _raiz_proyecto() -> Path:
    return Path(__file__).resolve().parents[3]


def evaluar_tabla(tabla: pd.DataFrame, hoy: datetime | None = None) -> ReporteCalidad:
    """Evalúa grano mensual, integridad, rangos y actualidad de la tabla."""
    errores: list[str] = []
    advertencias: list[str] = []
    faltantes = sorted(set(COLUMNAS_REQUERIDAS).difference(tabla.columns))
    if faltantes:
        return {
            "estado": "error",
            "resumen": {"filas": len(tabla), "inicio": None, "fin": None},
            "errores": [f"Faltan columnas requeridas: {', '.join(faltantes)}."],
            "advertencias": [],
        }

    fechas = pd.to_datetime(tabla["mes_observacion"], errors="coerce")
    if fechas.isna().any():
        errores.append("Hay fechas no válidas en mes_observacion.")
    if fechas.duplicated().any():
        errores.append("Hay meses duplicados; el grano debe ser un registro por mes.")
    if not fechas.is_monotonic_increasing:
        errores.append("Los meses no están ordenados de forma creciente.")

    if fechas.notna().all() and not fechas.empty:
        esperado = pd.date_range(fechas.min(), fechas.max(), freq="ME")
        faltantes_mes = esperado.difference(pd.DatetimeIndex(fechas))
        if not faltantes_mes.empty:
            errores.append(
                f"Faltan {len(faltantes_mes)} meses dentro del rango analítico."
            )
    else:
        faltantes_mes = pd.DatetimeIndex([])

    for columna in COLUMNAS_OBSERVADAS:
        nulos = int(tabla[columna].isna().sum())
        if nulos:
            errores.append(f"{columna} tiene {nulos} valores faltantes.")
    for columna in ("tasa_real_pct",):
        nulos = int(tabla[columna].isna().sum())
        if nulos > 12:
            errores.append(
                f"{columna} tiene {nulos} faltantes; se esperan como máximo 12 iniciales."
            )

    if not tabla["imor_pct"].between(0, 100).all():
        errores.append("IMOR tiene valores fuera de [0, 100].")
    if not tabla["desempleo_pct"].between(0, 100).all():
        errores.append("Desempleo tiene valores fuera de [0, 100].")
    if not (tabla["inpc_indice"] > 0).all():
        errores.append("INPC contiene valores no positivos.")
    for columna in ("indicador_covid", "ruptura_contable"):
        if not tabla[columna].isin([0, 1]).all():
            errores.append(f"{columna} sólo puede contener 0 o 1.")

    fecha_fin = fechas.max() if fechas.notna().any() else None
    momento = hoy or datetime.now(UTC)
    umbral_antiguedad = pd.Timestamp(momento).tz_localize(None) - pd.DateOffset(
        months=6
    )
    if fecha_fin is not None and fecha_fin < umbral_antiguedad:
        advertencias.append(
            "La última observación tiene más de seis meses de antigüedad."
        )
    if len(tabla) < 120:
        advertencias.append(
            "La muestra tiene menos de 120 meses; los modelos serán inestables."
        )

    return {
        "estado": "error" if errores else "aprobado",
        "resumen": {
            "filas": len(tabla),
            "inicio": fechas.min().date().isoformat() if fechas.notna().any() else None,
            "fin": fecha_fin.date().isoformat() if fecha_fin is not None else None,
            "meses_faltantes": len(faltantes_mes),
        },
        "errores": errores,
        "advertencias": advertencias,
    }


def guardar_reporte(reporte: ReporteCalidad, ruta: Path) -> None:
    """Escribe el reporte JSON en una ruta reconstruible."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(reporte, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    """Valida un Parquet analítico y falla con un mensaje accionable si no sirve."""
    parser = argparse.ArgumentParser(description=__doc__)
    raiz = _raiz_proyecto()
    parser.add_argument(
        "--entrada",
        type=Path,
        default=raiz / "data" / "processed" / "conjunto_analitico.parquet",
    )
    parser.add_argument(
        "--reporte",
        type=Path,
        default=raiz / "data" / "interim" / "reporte_calidad.json",
    )
    args = parser.parse_args()
    if not args.entrada.is_file():
        raise SystemExit(f"No existe el conjunto analítico: {args.entrada}")
    reporte = evaluar_tabla(pd.read_parquet(args.entrada))
    guardar_reporte(reporte, args.reporte)
    if reporte["estado"] != "aprobado":
        raise SystemExit("La tabla analítica no superó los controles de calidad.")
    print(f"Calidad aprobada. Reporte: {args.reporte}")


if __name__ == "__main__":
    main()
