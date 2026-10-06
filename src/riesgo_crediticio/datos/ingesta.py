"""Ingesta reproducible de las series macroeconómicas y el IMOR de Sofipos."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import ssl
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from http.cookiejar import CookieJar
from io import BytesIO
from pathlib import Path
from typing import cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

import pandas as pd
import yaml

from riesgo_crediticio.datos.calidad import evaluar_tabla, guardar_reporte

URL_INEGI = (
    "https://www.inegi.org.mx/app/tabulados/serviciocuadros/"
    "wsDataService.svc/listaindicadorbiinegi/"
    "{serie}/false/0700/es/json/{inicio}/{fin}/0/0/3"
)
URL_INPC_EXPORTACION = (
    "https://www.inegi.org.mx/app/tabulados/inp/default.aspx?nc=ca57_2018a&opc=t"
)
URL_BANXICO = (
    "https://www.banxico.org.mx/SieAPIRest/service/v1/series/"
    "{serie}/datos/{inicio}-01-01/{fin}-12-31?token={token}"
)
RUTA_CERTIFICADO_INTERMEDIO_CNBV = "certificados/globalsign-rsa-ov-ssl-ca-2018.pem"


class ErrorIngesta(RuntimeError):
    """Indica que una fuente o archivo no cumple el contrato de ingesta."""


@dataclass(frozen=True)
class SerieConfigurada:
    """Identificadores mínimos para obtener una serie oficial."""

    nombre: str
    identificador: str
    url_fuente: str
    url_descarga: str


@dataclass(frozen=True)
class ArchivoDescargado:
    """Contenido descargado y metadatos HTTP útiles para su trazabilidad."""

    contenido: bytes
    etag: str | None
    ultima_modificacion: str | None


def _raiz_proyecto() -> Path:
    return Path(__file__).resolve().parents[3]


def cargar_series(ruta: Path) -> dict[str, SerieConfigurada]:
    """Lee el catálogo y retorna los identificadores que usa la ingesta."""
    with ruta.open(encoding="utf-8") as archivo:
        contenido = yaml.safe_load(archivo)

    if not isinstance(contenido, dict) or not isinstance(contenido.get("series"), dict):
        raise ErrorIngesta("El catálogo de series no tiene la estructura esperada.")

    resultado: dict[str, SerieConfigurada] = {}
    for nombre, datos in contenido["series"].items():
        if not isinstance(datos, dict):
            raise ErrorIngesta(f"La serie {nombre} no tiene metadatos válidos.")
        identificador = datos.get("identificador")
        url_fuente = datos.get("url_fuente")
        url_descarga = datos.get("url_descarga")
        if (
            not isinstance(identificador, str)
            or not isinstance(url_fuente, str)
            or not isinstance(url_descarga, str)
        ):
            raise ErrorIngesta(
                f"Faltan identificador, URL fuente o URL de descarga para {nombre}."
            )
        resultado[nombre] = SerieConfigurada(
            nombre, identificador, url_fuente, url_descarga
        )
    return resultado


def _extraer_identificador(texto: str, patron: str, nombre: str) -> str:
    coincidencia = re.search(patron, texto)
    if coincidencia is None:
        raise ErrorIngesta(
            f"No se encontró el identificador de {nombre} en el catálogo."
        )
    return coincidencia.group(0)


def descargar_json(url: str) -> bytes:
    """Descarga una respuesta JSON sin incluir secretos en los errores."""
    solicitud = Request(url, headers={"User-Agent": "credit-risk-lab/0.1"})
    try:
        with urlopen(solicitud, timeout=60) as respuesta:
            contenido = cast(bytes, respuesta.read())
    except OSError as error:
        raise ErrorIngesta("No fue posible descargar una serie oficial.") from error

    try:
        json.loads(contenido)
    except json.JSONDecodeError as error:
        raise ErrorIngesta("La fuente no devolvió JSON válido.") from error
    return contenido


def _contexto_tls_cnbv() -> ssl.SSLContext:
    """Crea un contexto estricto con el intermedio omitido por el servidor CNBV."""
    ruta_certificado = _raiz_proyecto() / RUTA_CERTIFICADO_INTERMEDIO_CNBV
    if not ruta_certificado.is_file():
        raise ErrorIngesta(
            "No se encontró el certificado intermedio requerido para CNBV."
        )
    contexto = ssl.create_default_context()
    try:
        contexto.load_verify_locations(cafile=str(ruta_certificado))
    except (OSError, ssl.SSLError) as error:
        raise ErrorIngesta(
            "No fue posible cargar el certificado intermedio de CNBV."
        ) from error
    return contexto


def descargar_excel_cnbv(url: str) -> ArchivoDescargado:
    """Descarga y valida la exportación XLSX oficial de la CNBV mediante TLS."""
    solicitud = Request(url, headers={"User-Agent": "credit-risk-lab/0.1"})
    try:
        with urlopen(solicitud, context=_contexto_tls_cnbv(), timeout=60) as respuesta:
            contenido = cast(bytes, respuesta.read())
            tipo_contenido = respuesta.headers.get_content_type().lower()
            etag = respuesta.headers.get("ETag")
            ultima_modificacion = respuesta.headers.get("Last-Modified")
    except OSError as error:
        raise ErrorIngesta(
            "No fue posible descargar el Excel oficial de IMOR desde CNBV."
        ) from error

    tipos_permitidos = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    }
    if tipo_contenido not in tipos_permitidos:
        raise ErrorIngesta(
            "La descarga de CNBV no reporta un tipo de contenido XLSX válido."
        )
    if not zipfile.is_zipfile(BytesIO(contenido)):
        raise ErrorIngesta("La descarga de CNBV no contiene un archivo XLSX válido.")
    return ArchivoDescargado(contenido, etag, ultima_modificacion)


def descargar_inpc_csv(inicio: int, fin: int) -> bytes:
    """Descarga el CSV oficial vigente del INPC desde su tabulado público."""
    sesion = build_opener(HTTPCookieProcessor(CookieJar()))
    try:
        with sesion.open(
            Request(
                URL_INPC_EXPORTACION, headers={"User-Agent": "credit-risk-lab/0.1"}
            ),
            timeout=60,
        ) as respuesta:
            formulario = cast(bytes, respuesta.read()).decode("latin-1")
        campos_ocultos: dict[str, str] = {}
        for nombre in ("__VIEWSTATE", "__EVENTVALIDATION"):
            coincidencia = re.search(
                rf'name="{nombre}"[^>]*value="([^"]*)"', formulario
            )
            if coincidencia is None:
                raise ErrorIngesta("El formulario de INPC cambió de estructura.")
            campos_ocultos[nombre] = coincidencia.group(1)
        datos = urlencode(
            {
                **campos_ocultos,
                "__VIEWSTATEGENERATOR": "C79B51A4",
                "btndescargacsv": "Descarga CSV",
                "selectperiodoI": str(inicio),
                "selectperiodoF": str(fin),
                "selectTipoInfo": "indices",
                "hdfrecuencia": "mensual",
                "hdtitulo": (
                    "Índice Nacional de Precios al Consumidor, "
                    "clasificación objeto del gasto"
                ),
                "hdsubt": "",
                "hdum": "",
                "hdind": "865541",
            }
        ).encode()
        solicitud = Request(
            URL_INPC_EXPORTACION,
            data=datos,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "credit-risk-lab/0.1",
            },
        )
        with sesion.open(solicitud, timeout=60) as respuesta:
            contenido = cast(bytes, respuesta.read())
    except (AttributeError, OSError) as error:
        raise ErrorIngesta(
            "No fue posible descargar el CSV vigente de INPC."
        ) from error

    if b'"Fecha"' not in contenido:
        raise ErrorIngesta("La exportación de INPC no tiene el formato esperado.")
    return contenido


def normalizar_inegi(contenido: bytes, nombre_columna: str) -> pd.DataFrame:
    """Convierte la respuesta del servicio de tabulados INEGI a fechas mensuales."""
    datos = json.loads(contenido)
    try:
        serie = datos[0]["Data"][0]["Serie"]["Obs"]
    except (IndexError, KeyError, TypeError) as error:
        raise ErrorIngesta("El esquema de respuesta de INEGI cambió.") from error

    resultado = pd.DataFrame(serie)[["TimePeriod", "CurrentValue"]].rename(
        columns={"TimePeriod": "mes_observacion", "CurrentValue": nombre_columna}
    )
    resultado["mes_observacion"] = (
        pd.to_datetime(resultado["mes_observacion"], format="%Y/%m", errors="coerce")
        .dt.to_period("M")
        .dt.to_timestamp("M")
    )
    resultado[nombre_columna] = pd.to_numeric(
        resultado[nombre_columna], errors="coerce"
    )
    return _validar_serie(resultado, nombre_columna)


def normalizar_inpc_csv(contenido: bytes) -> pd.DataFrame:
    """Convierte el CSV de exportación INPC a una serie mensual de niveles."""
    try:
        filas = list(csv.reader(contenido.decode("latin-1").splitlines()))
        indice_fecha = next(
            indice for indice, fila in enumerate(filas) if fila and fila[0] == "Fecha"
        )
    except (StopIteration, UnicodeDecodeError) as error:
        raise ErrorIngesta(
            "El CSV de INPC no contiene la fila de fechas esperada."
        ) from error

    meses = {
        "Ene": "01",
        "Feb": "02",
        "Mar": "03",
        "Abr": "04",
        "May": "05",
        "Jun": "06",
        "Jul": "07",
        "Ago": "08",
        "Sep": "09",
        "Oct": "10",
        "Nov": "11",
        "Dic": "12",
    }
    observaciones: list[dict[str, str]] = []
    for fila in filas[indice_fecha + 1 :]:
        if len(fila) < 2 or not fila[0].strip() or not fila[1].strip():
            continue
        partes = fila[0].strip().split()
        if len(partes) != 2 or partes[0] not in meses or not partes[1].isdigit():
            continue
        observaciones.append(
            {
                "mes_observacion": f"{partes[1]}-{meses[partes[0]]}",
                "inpc_indice": fila[1].strip(),
            }
        )
    resultado = pd.DataFrame(observaciones)
    if resultado.empty:
        raise ErrorIngesta("El CSV de INPC no contiene observaciones mensuales.")
    resultado["mes_observacion"] = (
        pd.to_datetime(resultado["mes_observacion"], format="%Y-%m", errors="coerce")
        .dt.to_period("M")
        .dt.to_timestamp("M")
    )
    resultado["inpc_indice"] = pd.to_numeric(resultado["inpc_indice"], errors="coerce")
    return _validar_serie(resultado, "inpc_indice")


def normalizar_banxico(contenido: bytes, nombre_columna: str) -> pd.DataFrame:
    """Convierte la respuesta SIE de Banxico a fechas mensuales."""
    datos = json.loads(contenido)
    try:
        serie = datos["bmx"]["series"][0]["datos"]
    except (IndexError, KeyError, TypeError) as error:
        raise ErrorIngesta("El esquema de respuesta de Banxico cambió.") from error

    resultado = pd.DataFrame(serie)[["fecha", "dato"]].rename(
        columns={"fecha": "mes_observacion", "dato": nombre_columna}
    )
    resultado["mes_observacion"] = (
        pd.to_datetime(resultado["mes_observacion"], format="%d/%m/%Y", errors="coerce")
        .dt.to_period("M")
        .dt.to_timestamp("M")
    )
    resultado[nombre_columna] = pd.to_numeric(
        resultado[nombre_columna].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )
    return _validar_serie(resultado, nombre_columna)


def _validar_serie(tabla: pd.DataFrame, columna: str) -> pd.DataFrame:
    if tabla["mes_observacion"].isna().any() or tabla[columna].isna().any():
        raise ErrorIngesta(
            f"La serie {columna} contiene fechas o valores no numéricos."
        )
    if tabla["mes_observacion"].duplicated().any():
        raise ErrorIngesta(f"La serie {columna} contiene meses duplicados.")
    return tabla.sort_values("mes_observacion", ignore_index=True)


def _normalizar_nombre(nombre: str) -> str:
    reemplazos = str.maketrans("áéíóúüñ", "aeiouun")
    return re.sub(r"[^a-z0-9]", "", nombre.lower().translate(reemplazos))


def _encontrar_columna(columnas: list[str], candidatas: set[str], etiqueta: str) -> str:
    for columna in columnas:
        if _normalizar_nombre(columna) in candidatas:
            return columna
    disponibles = ", ".join(columnas)
    raise ErrorIngesta(
        f"No se identificó la columna {etiqueta}. Disponibles: {disponibles}"
    )


def leer_imor(
    ruta: Path, columna_fecha: str | None, columna_imor: str | None
) -> pd.DataFrame:
    """Lee el CSV simple o el Excel oficial de la serie histórica de CNBV."""
    if ruta.suffix.lower() == ".xlsx":
        if columna_fecha or columna_imor:
            raise ErrorIngesta(
                "No se usan columnas manuales con el Excel de serie histórica CNBV."
            )
        return _leer_imor_excel_cnbv(ruta)

    try:
        tabla = pd.read_csv(ruta, sep=None, engine="python")
    except (OSError, pd.errors.ParserError) as error:
        raise ErrorIngesta("No fue posible leer el CSV de IMOR de CNBV.") from error

    columnas = [str(columna) for columna in tabla.columns]
    fecha = columna_fecha or _encontrar_columna(
        columnas, {"fecha", "periodo", "mes", "mesobservacion"}, "de fecha"
    )
    imor = columna_imor or _encontrar_columna(
        columnas,
        {"imor", "imorpct", "indicemorosidad", "indicemorosidadpct"},
        "de IMOR",
    )
    if fecha not in tabla.columns or imor not in tabla.columns:
        raise ErrorIngesta("Las columnas de IMOR indicadas no existen en el CSV.")

    resultado = tabla[[fecha, imor]].rename(
        columns={fecha: "mes_observacion", imor: "imor_pct"}
    )
    resultado["mes_observacion"] = (
        pd.to_datetime(resultado["mes_observacion"], dayfirst=True, errors="coerce")
        .dt.to_period("M")
        .dt.to_timestamp("M")
    )
    resultado["imor_pct"] = pd.to_numeric(
        resultado["imor_pct"].astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    )
    resultado = _validar_serie(resultado, "imor_pct")
    if not resultado["imor_pct"].between(0, 100).all():
        raise ErrorIngesta("IMOR contiene valores fuera del rango [0, 100].")
    return resultado


def _leer_imor_excel_cnbv(ruta: Path) -> pd.DataFrame:
    """Extrae IMOR consumo de la pestaña agregada de la exportación oficial."""
    try:
        tabla = pd.read_excel(ruta, sheet_name="Exportación_SH", header=6)
    except (OSError, ValueError, ImportError) as error:
        raise ErrorIngesta(
            "No fue posible leer la hoja Exportación_SH del Excel de CNBV."
        ) from error

    return _extraer_imor_exportacion_cnbv(tabla)


def _extraer_imor_exportacion_cnbv(tabla: pd.DataFrame) -> pd.DataFrame:
    """Normaliza la fila IMOR consumo del formato ancho publicado por CNBV."""
    columnas = [str(columna) for columna in tabla.columns]
    concepto = _encontrar_columna(columnas, {"concepto"}, "de concepto")
    coincidencias = tabla.loc[
        tabla[concepto].astype(str).str.strip().str.casefold() == "imor consumo"
    ]
    if len(coincidencias) != 1:
        raise ErrorIngesta(
            "El Excel CNBV debe contener exactamente una fila agregada 'IMOR consumo'."
        )

    periodos = [
        columna
        for columna in tabla.columns
        if re.fullmatch(r"20\d{4}", str(columna)) is not None
    ]
    if not periodos:
        raise ErrorIngesta("El Excel CNBV no contiene columnas mensuales YYYYMM.")

    fila = coincidencias.iloc[0]
    resultado = pd.DataFrame(
        {
            "mes_observacion": [str(periodo) for periodo in periodos],
            "imor_pct": [fila[periodo] for periodo in periodos],
        }
    )
    resultado["mes_observacion"] = (
        pd.to_datetime(resultado["mes_observacion"], format="%Y%m", errors="coerce")
        .dt.to_period("M")
        .dt.to_timestamp("M")
    )
    resultado["imor_pct"] = pd.to_numeric(resultado["imor_pct"], errors="coerce")
    resultado = _validar_serie(resultado, "imor_pct")
    if not resultado["imor_pct"].between(0, 100).all():
        raise ErrorIngesta("IMOR contiene valores fuera del rango [0, 100].")
    return resultado


def construir_tabla(
    imor: pd.DataFrame,
    inpc: pd.DataFrame,
    desempleo: pd.DataFrame,
    tasa_nominal: pd.DataFrame,
) -> pd.DataFrame:
    """Une las observaciones y calcula inflación anual y tasa real ex post."""
    tabla = imor.merge(inpc, on="mes_observacion", how="inner")
    tabla = tabla.merge(desempleo, on="mes_observacion", how="inner")
    tabla = tabla.merge(tasa_nominal, on="mes_observacion", how="inner")
    tabla = tabla.sort_values("mes_observacion", ignore_index=True)
    tabla["inflacion_interanual_pct"] = tabla["inpc_indice"].pct_change(12) * 100
    tabla["tasa_real_pct"] = (
        tabla["tasa_nominal_pct"] - tabla["inflacion_interanual_pct"]
    )
    tabla["indicador_covid"] = (
        tabla["mes_observacion"]
        .between(pd.Timestamp("2020-03-31"), pd.Timestamp("2021-12-31"))
        .astype("int8")
    )
    tabla["ruptura_contable"] = (
        tabla["mes_observacion"] >= pd.Timestamp("2022-01-31")
    ).astype("int8")
    return tabla


def _url_sin_secreto(url: str) -> str:
    partes = urlsplit(url)
    consulta = [
        (clave, "[REDACTED]" if clave == "token" else valor)
        for clave, valor in parse_qsl(partes.query)
    ]
    return urlunsplit(
        (
            partes.scheme,
            partes.netloc,
            partes.path,
            urlencode(consulta),
            partes.fragment,
        )
    )


def guardar_raw(
    contenido: bytes, directorio: Path, serie: str, extension: str
) -> tuple[Path, str]:
    """Conserva una descarga inmutable, direccionada por su checksum."""
    checksum = hashlib.sha256(contenido).hexdigest()
    ruta = directorio / f"{serie}_{checksum[:16]}.{extension}"
    directorio.mkdir(parents=True, exist_ok=True)
    if not ruta.exists():
        ruta.write_bytes(contenido)
    return ruta, checksum


def registrar_manifiesto(registros: list[dict[str, str]], ruta: Path) -> None:
    """Registra las descargas de la ejecución sin alterar archivos crudos."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(registros[0]))
        escritor.writeheader()
        escritor.writerows(registros)


def ejecutar(args: argparse.Namespace) -> Path:
    """Descarga fuentes macro, incorpora IMOR local y produce un Parquet analítico."""
    raiz = _raiz_proyecto()
    series = cargar_series(raiz / "config" / "series.yml")
    anio_fin = args.anio_fin

    desempleo_id = _extraer_identificador(
        series["desempleo_desestacionalizado"].identificador, r"\d+", "desempleo"
    )
    tiie_id = _extraer_identificador(
        series["tasa_nominal_fondeo"].identificador, r"SF\d+", "TIIE"
    )
    token_banxico = os.environ.get("BANXICO_API_TOKEN")
    if not token_banxico:
        raise ErrorIngesta("Falta la variable de entorno BANXICO_API_TOKEN.")

    url_desempleo = URL_INEGI.format(
        serie=desempleo_id, inicio=args.anio_inicio, fin=anio_fin
    )
    url_tiie = URL_BANXICO.format(
        serie=tiie_id, inicio=args.anio_inicio, fin=anio_fin, token=token_banxico
    )
    descargas: list[tuple[str, str, bytes, str, str | None, str | None]] = [
        (
            "inpc",
            URL_INPC_EXPORTACION,
            descargar_inpc_csv(args.anio_inicio, anio_fin),
            "csv",
            None,
            None,
        ),
        (
            "desempleo_desestacionalizado",
            url_desempleo,
            descargar_json(url_desempleo),
            "json",
            None,
            None,
        ),
        (
            "tasa_nominal_fondeo",
            url_tiie,
            descargar_json(url_tiie),
            "json",
            None,
            None,
        ),
    ]

    if args.imor_csv:
        ruta_imor = Path(args.imor_csv).expanduser().resolve()
        if not ruta_imor.is_file():
            raise ErrorIngesta(
                "--imor-csv debe apuntar a una exportación CSV o XLSX existente de CNBV."
            )
        extension_imor = ruta_imor.suffix.lower().removeprefix(".")
        if extension_imor not in {"csv", "xlsx"}:
            raise ErrorIngesta("--imor-csv debe ser un archivo CSV o XLSX de CNBV.")
        descargas.append(
            (
                "imor_consumo_sofipos",
                str(ruta_imor),
                ruta_imor.read_bytes(),
                extension_imor,
                None,
                None,
            )
        )
    else:
        descarga_imor = descargar_excel_cnbv(
            series["imor_consumo_sofipos"].url_descarga
        )
        descargas.append(
            (
                "imor_consumo_sofipos",
                series["imor_consumo_sofipos"].url_descarga,
                descarga_imor.contenido,
                "xlsx",
                descarga_imor.etag,
                descarga_imor.ultima_modificacion,
            )
        )

    directorio_raw = raiz / "data" / "raw"
    registros: list[dict[str, str]] = []
    rutas_raw: dict[str, Path] = {}
    for nombre, url, contenido, extension, etag, ultima_modificacion in descargas:
        ruta_raw, checksum = guardar_raw(contenido, directorio_raw, nombre, extension)
        rutas_raw[nombre] = ruta_raw
        registros.append(
            {
                "serie": nombre,
                "proveedor": series[nombre].url_fuente,
                "url": _url_sin_secreto(url),
                "fecha_descarga_utc": datetime.now(UTC).isoformat(),
                "ruta_local": str(ruta_raw.relative_to(raiz)),
                "sha256": checksum,
                "tamanio_bytes": str(len(contenido)),
                "etag": etag or "",
                "ultima_modificacion": ultima_modificacion or "",
            }
        )

    tabla = construir_tabla(
        leer_imor(
            rutas_raw["imor_consumo_sofipos"], args.columna_fecha, args.columna_imor
        ),
        normalizar_inpc_csv(descargas[0][2]),
        normalizar_inegi(descargas[1][2], "desempleo_pct"),
        normalizar_banxico(descargas[2][2], "tasa_nominal_pct"),
    )
    reporte_calidad = evaluar_tabla(tabla)
    guardar_reporte(reporte_calidad, raiz / "data" / "interim" / "reporte_calidad.json")
    if reporte_calidad["estado"] != "aprobado":
        raise ErrorIngesta("La tabla resultante no superó los controles de calidad.")
    salida = (
        Path(args.salida).resolve()
        if args.salida
        else raiz / "data" / "processed" / "conjunto_analitico.parquet"
    )
    salida.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_parquet(salida, index=False)
    registrar_manifiesto(
        registros, raiz / "data" / "interim" / "manifiesto_descargas.csv"
    )
    return salida


def argumentos() -> argparse.ArgumentParser:
    """Construye la interfaz de línea de comandos de la ingesta."""
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument(
        "--imor-csv",
        help=(
            "Exportación CSV o Excel local de CNBV. Si se omite, se descarga el "
            "Excel oficial configurado."
        ),
    )
    analizador.add_argument(
        "--columna-fecha", help="Nombre exacto de la columna de fecha del CSV CNBV."
    )
    analizador.add_argument(
        "--columna-imor", help="Nombre exacto de la columna IMOR del CSV CNBV."
    )
    analizador.add_argument("--anio-inicio", type=int, default=2008)
    analizador.add_argument("--anio-fin", type=int, default=datetime.now(UTC).year)
    analizador.add_argument(
        "--salida", help="Ruta alternativa para el Parquet analítico."
    )
    return analizador


def main() -> None:
    """Ejecuta la ingesta y muestra la ruta del conjunto analítico."""
    try:
        salida = ejecutar(argumentos().parse_args())
    except ErrorIngesta as error:
        raise SystemExit(f"Error de ingesta: {error}") from error
    print(f"Conjunto analítico generado: {salida}")


if __name__ == "__main__":
    main()
