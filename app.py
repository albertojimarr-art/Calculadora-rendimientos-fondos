from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
META_FILE = DATA_DIR / "last_upload.json"
SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}

st.set_page_config(
    page_title="Dashboard de Fondos",
    page_icon="📊",
    layout="wide",
)

DATA_DIR.mkdir(exist_ok=True)


# -----------------------------
# Utilidades de carga y guardado
# -----------------------------
def guardar_ultima_base(nombre: str, contenido: bytes) -> Path:
    extension = Path(nombre).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Formato de archivo no soportado.")

    for archivo in DATA_DIR.glob("last_base.*"):
        archivo.unlink(missing_ok=True)

    destino = DATA_DIR / f"last_base{extension}"
    destino.write_bytes(contenido)

    META_FILE.write_text(
        json.dumps(
            {"original_name": nombre, "stored_name": destino.name},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return destino


def obtener_base_guardada() -> tuple[Optional[Path], Optional[str]]:
    if not META_FILE.exists():
        return None, None

    try:
        meta = json.loads(META_FILE.read_text(encoding="utf-8"))
        ruta = DATA_DIR / meta["stored_name"]
        if ruta.exists():
            return ruta, meta.get("original_name", ruta.name)
    except Exception:
        pass

    return None, None


@st.cache_data(show_spinner=False)
def hojas_excel_desde_bytes(contenido: bytes) -> list[str]:
    return pd.ExcelFile(io.BytesIO(contenido)).sheet_names


@st.cache_data(show_spinner=False)
def leer_archivo_bytes(
    contenido: bytes,
    extension: str,
    hoja: Optional[str] = None,
) -> pd.DataFrame:
    buffer = io.BytesIO(contenido)
    extension = extension.lower()

    if extension == ".csv":
        try:
            return pd.read_csv(buffer)
        except UnicodeDecodeError:
            buffer.seek(0)
            return pd.read_csv(buffer, encoding="latin-1")

    return pd.read_excel(buffer, sheet_name=hoja)


def preparar_base(df: pd.DataFrame, columna_fecha: str) -> pd.DataFrame:
    base = df.copy()
    base.columns = [str(c).strip() for c in base.columns]
    columna_fecha = str(columna_fecha).strip()

    base[columna_fecha] = pd.to_datetime(
        base[columna_fecha],
        errors="coerce",
        dayfirst=True,
    )
    base = base.dropna(subset=[columna_fecha])
    base = base.sort_values(columna_fecha)
    base = base.drop_duplicates(subset=[columna_fecha], keep="last")
    base = base.set_index(columna_fecha)

    for columna in base.columns:
        base[columna] = pd.to_numeric(base[columna], errors="coerce")
        base.loc[base[columna] <= 0, columna] = np.nan

    return base


def serie_valida(base: pd.DataFrame, fondo: str) -> pd.Series:
    return base[fondo].dropna().sort_index()


def precio_en_o_antes(serie: pd.Series, fecha: pd.Timestamp) -> Optional[float]:
    datos = serie.loc[:fecha]
    if datos.empty:
        return None
    return float(datos.iloc[-1])


def rendimiento_entre(
    serie: pd.Series,
    fecha_inicial: pd.Timestamp,
    fecha_final: pd.Timestamp,
) -> Optional[float]:
    precio_inicial = precio_en_o_antes(serie, fecha_inicial)
    precio_final = precio_en_o_antes(serie, fecha_final)

    if precio_inicial is None or precio_final is None or precio_inicial <= 0:
        return None

    return (precio_final / precio_inicial) - 1


def metricas_fondo(
    serie: pd.Series,
    fecha_corte: pd.Timestamp,
) -> dict[str, Optional[float]]:
    serie = serie.loc[:fecha_corte].dropna().sort_index()

    if serie.empty:
        return {
            "YTD": None,
            "1 mes": None,
            "3 meses": None,
            "6 meses": None,
            "1 año": None,
            "Volatilidad": None,
            "Máximo drawdown": None,
            "Mejor mes": None,
            "Peor mes": None,
        }

    inicio_ano = pd.Timestamp(year=fecha_corte.year, month=1, day=1)

    retornos_diarios = serie.pct_change().dropna()
    volatilidad = (
        float(retornos_diarios.std(ddof=1) * np.sqrt(360))
        if len(retornos_diarios) >= 2
        else None
    )

    maximos = serie.cummax()
    drawdown = (serie / maximos) - 1
    max_drawdown = float(drawdown.min()) if not drawdown.empty else None

    precios_mensuales = serie.resample("ME").last()
    retornos_mensuales = precios_mensuales.pct_change().dropna()

    mejor_mes = (
        float(retornos_mensuales.max())
        if not retornos_mensuales.empty
        else None
    )
    peor_mes = (
        float(retornos_mensuales.min())
        if not retornos_mensuales.empty
        else None
    )

    return {
        "YTD": rendimiento_entre(serie, inicio_ano, fecha_corte),
        "1 mes": rendimiento_entre(
            serie, fecha_corte - pd.DateOffset(months=1), fecha_corte
        ),
        "3 meses": rendimiento_entre(
            serie, fecha_corte - pd.DateOffset(months=3), fecha_corte
        ),
        "6 meses": rendimiento_entre(
            serie, fecha_corte - pd.DateOffset(months=6), fecha_corte
        ),
        "1 año": rendimiento_entre(
            serie, fecha_corte - pd.DateOffset(years=1), fecha_corte
        ),
        "Volatilidad": volatilidad,
        "Máximo drawdown": max_drawdown,
        "Mejor mes": mejor_mes,
        "Peor mes": peor_mes,
    }


def porcentaje(valor: Optional[float], decimales: int = 2) -> str:
    if valor is None or pd.isna(valor):
        return "N/D"
    return f"{valor:.{decimales}%}"


def fechas_validas(serie: pd.Series) -> list:
    return serie.index.date.tolist()


def normalizar_base_100(df: pd.DataFrame) -> pd.DataFrame:
    resultado = df.copy()
    for columna in resultado.columns:
        serie = resultado[columna].dropna()
        if not serie.empty:
            resultado[columna] = resultado[columna] / serie.iloc[0] * 100
    return resultado


# -----------------------------
# Encabezado y carga de archivo
# -----------------------------
st.title("📊 Dashboard de Fondos de Inversión")
st.caption(
    "Calculadora individual y comparador multífondo con precios históricos."
)

ruta_guardada, nombre_guardado = obtener_base_guardada()

with st.sidebar:
    st.header("Base de precios")

    archivo_subido = st.file_uploader(
        "Sube tu archivo Excel o CSV",
        type=["xlsx", "xls", "csv"],
    )

    contenido: Optional[bytes] = None
    nombre_archivo: Optional[str] = None
    extension: Optional[str] = None

    if archivo_subido is not None:
        contenido = archivo_subido.getvalue()
        nombre_archivo = archivo_subido.name
        extension = Path(nombre_archivo).suffix.lower()

        try:
            guardar_ultima_base(nombre_archivo, contenido)
            st.success("Base cargada y guardada.")
        except Exception as exc:
            st.warning(f"La base se cargó, pero no pudo guardarse: {exc}")

    elif ruta_guardada is not None:
        contenido = ruta_guardada.read_bytes()
        nombre_archivo = nombre_guardado or ruta_guardada.name
        extension = ruta_guardada.suffix.lower()
        st.info(f"Usando la última base guardada: {nombre_archivo}")

    else:
        base_repo = next(
            (
                p for p in [
                    DATA_DIR / "base_predeterminada.xlsx",
                    DATA_DIR / "base_predeterminada.xls",
                    DATA_DIR / "base_predeterminada.csv",
                ]
                if p.exists()
            ),
            None,
        )
        if base_repo is not None:
            contenido = base_repo.read_bytes()
            nombre_archivo = base_repo.name
            extension = base_repo.suffix.lower()
            st.info("Usando la base predeterminada del repositorio.")

if contenido is None or extension is None:
    st.info(
        "Sube tu base desde la barra lateral. La aplicación guardará una copia "
        "local para reutilizarla en la siguiente sesión."
    )
    st.stop()

try:
    if extension in {".xlsx", ".xls"}:
        hojas = hojas_excel_desde_bytes(contenido)
        with st.sidebar:
            hoja = st.selectbox("Hoja del archivo", hojas)
    else:
        hoja = None

    df_raw = leer_archivo_bytes(contenido, extension, hoja)

except Exception as exc:
    st.error("No fue posible leer el archivo.")
    st.exception(exc)
    st.stop()

if df_raw.empty:
    st.error("El archivo no contiene datos.")
    st.stop()

with st.sidebar:
    columna_fecha = st.selectbox(
        "Columna de fecha",
        options=[str(c).strip() for c in df_raw.columns],
        index=0,
    )

try:
    base_precios = preparar_base(df_raw, columna_fecha)
except Exception as exc:
    st.error("No fue posible preparar la base de precios.")
    st.exception(exc)
    st.stop()

fondos = [
    columna for columna in base_precios.columns
    if base_precios[columna].notna().any()
]

if not fondos:
    st.error("No se encontraron columnas con precios válidos.")
    st.stop()

with st.sidebar:
    st.caption(
        f"{len(fondos)} fondos válidos · "
        f"{base_precios.index.min():%d/%m/%Y} a "
        f"{base_precios.index.max():%d/%m/%Y}"
    )
    st.warning(
        "En Streamlit Cloud, el archivo guardado localmente puede perderse "
        "cuando la aplicación se reinicia o se vuelve a desplegar."
    )


# -----------------------------
# Pestañas
# -----------------------------
tab_calculadora, tab_comparador = st.tabs(
    ["📊 Calculadora de rendimiento", "📈 Comparador de fondos"]
)


with tab_calculadora:
    col_a, col_b = st.columns([2, 1])

    with col_a:
        fondo = st.selectbox(
            "Selecciona el fondo",
            fondos,
            key="fondo_individual",
        )

    with col_b:
        tipo_fondo = st.radio(
            "Tipo de fondo",
            ["Deuda", "Renta variable"],
            horizontal=True,
            key="tipo_individual",
        )

    serie = serie_valida(base_precios, fondo)
    lista_fechas = fechas_validas(serie)

    st.caption(
        f"Rango disponible: {serie.index.min():%d/%m/%Y} a "
        f"{serie.index.max():%d/%m/%Y} · {len(serie):,} precios válidos"
    )

    c1, c2 = st.columns(2)
    with c1:
        fecha_inicial = st.selectbox(
            "Fecha inicial",
            lista_fechas,
            index=0,
            key="fecha_inicial_individual",
        )
    with c2:
        fecha_final = st.selectbox(
            "Fecha final",
            lista_fechas,
            index=len(lista_fechas) - 1,
            key="fecha_final_individual",
        )

    fi = pd.Timestamp(fecha_inicial)
    ff = pd.Timestamp(fecha_final)

    if ff <= fi:
        st.error("La fecha final debe ser posterior a la fecha inicial.")
    else:
        precio_inicial = float(serie.loc[fi])
        precio_final = float(serie.loc[ff])
        dias = (ff - fi).days
        rendimiento_periodo = (precio_final / precio_inicial) - 1

        if tipo_fondo == "Deuda":
            rendimiento_anualizado = rendimiento_periodo * (360 / dias)
            metodologia = "Simple, base 360"
        else:
            rendimiento_anualizado = (
                (1 + rendimiento_periodo) ** (360 / dias)
            ) - 1
            metodologia = "Compuesta, base 360"

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Precio inicial", f"{precio_inicial:.6f}")
        r2.metric("Precio final", f"{precio_final:.6f}")
        r3.metric("Rendimiento periodo", porcentaje(rendimiento_periodo, 4))
        r4.metric("Rendimiento anualizado", porcentaje(rendimiento_anualizado, 4))

        st.caption(f"{dias} días naturales · Metodología {metodologia}")

        metricas = metricas_fondo(serie, ff)

        st.subheader("Indicadores al cierre seleccionado")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("YTD", porcentaje(metricas["YTD"]))
        m2.metric("1 mes", porcentaje(metricas["1 mes"]))
        m3.metric("3 meses", porcentaje(metricas["3 meses"]))
        m4.metric("6 meses", porcentaje(metricas["6 meses"]))
        m5.metric("1 año", porcentaje(metricas["1 año"]))

        n1, n2, n3, n4 = st.columns(4)
        n1.metric("Volatilidad anualizada", porcentaje(metricas["Volatilidad"]))
        n2.metric("Máximo drawdown", porcentaje(metricas["Máximo drawdown"]))
        n3.metric("Mejor mes", porcentaje(metricas["Mejor mes"]))
        n4.metric("Peor mes", porcentaje(metricas["Peor mes"]))

        periodo = serie.loc[fi:ff].to_frame(name=fondo)

        modo = st.radio(
            "Visualización",
            ["Índice base 100", "Precio con escala ajustada"],
            horizontal=True,
            key="modo_grafica_individual",
        )

        grafica = periodo.copy()
        if modo == "Índice base 100":
            grafica["Valor"] = grafica[fondo] / grafica[fondo].iloc[0] * 100
            eje_y = "Índice base 100"
        else:
            grafica["Valor"] = grafica[fondo]
            eje_y = "Precio"

        grafica = grafica.reset_index()
        fig = px.line(
            grafica,
            x=columna_fecha,
            y="Valor",
            title=f"{fondo} · {modo}",
            labels={columna_fecha: "Fecha", "Valor": eje_y},
        )

        minimo = grafica["Valor"].min()
        maximo = grafica["Valor"].max()
        amplitud = maximo - minimo
        margen = amplitud * 0.10 if amplitud > 0 else max(abs(minimo) * 0.001, 0.001)

        fig.update_yaxes(range=[minimo - margen, maximo + margen])
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        resultado = pd.DataFrame(
            {
                "Fondo": [fondo],
                "Tipo": [tipo_fondo],
                "Fecha inicial": [fi.date()],
                "Precio inicial": [precio_inicial],
                "Fecha final": [ff.date()],
                "Precio final": [precio_final],
                "Días": [dias],
                "Rendimiento periodo": [rendimiento_periodo],
                "Rendimiento anualizado": [rendimiento_anualizado],
                "YTD": [metricas["YTD"]],
                "1 mes": [metricas["1 mes"]],
                "3 meses": [metricas["3 meses"]],
                "6 meses": [metricas["6 meses"]],
                "1 año": [metricas["1 año"]],
                "Volatilidad anualizada": [metricas["Volatilidad"]],
                "Máximo drawdown": [metricas["Máximo drawdown"]],
                "Mejor mes": [metricas["Mejor mes"]],
                "Peor mes": [metricas["Peor mes"]],
            }
        )

        st.download_button(
            "Descargar resultado individual",
            data=resultado.to_csv(index=False).encode("utf-8-sig"),
            file_name="resultado_fondo.csv",
            mime="text/csv",
        )


with tab_comparador:
    fondos_comparar = st.multiselect(
        "Selecciona los fondos a comparar",
        fondos,
        default=fondos[: min(3, len(fondos))],
    )

    if len(fondos_comparar) < 2:
        st.info("Selecciona al menos dos fondos.")
    else:
        datos_comparador = base_precios[fondos_comparar].copy()

        fecha_minima = datos_comparador.dropna(how="all").index.min().date()
        fecha_maxima = datos_comparador.dropna(how="all").index.max().date()

        d1, d2 = st.columns(2)
        with d1:
            fecha_inicio_comp = st.date_input(
                "Fecha inicial de comparación",
                value=fecha_minima,
                min_value=fecha_minima,
                max_value=fecha_maxima,
                key="fecha_inicio_comparador",
            )
        with d2:
            fecha_fin_comp = st.date_input(
                "Fecha final de comparación",
                value=fecha_maxima,
                min_value=fecha_minima,
                max_value=fecha_maxima,
                key="fecha_fin_comparador",
            )

        fic = pd.Timestamp(fecha_inicio_comp)
        ffc = pd.Timestamp(fecha_fin_comp)

        if ffc <= fic:
            st.error("La fecha final debe ser posterior a la fecha inicial.")
        else:
            periodo_comp = datos_comparador.loc[fic:ffc].copy()

            series_ajustadas = {}
            resumen = []

            for nombre in fondos_comparar:
                serie_fondo = periodo_comp[nombre].dropna()

                if len(serie_fondo) < 2:
                    continue

                serie_base100 = serie_fondo / serie_fondo.iloc[0] * 100
                series_ajustadas[nombre] = serie_base100

                fecha_real_inicial = serie_fondo.index[0]
                fecha_real_final = serie_fondo.index[-1]
                rendimiento_periodo = (
                    serie_fondo.iloc[-1] / serie_fondo.iloc[0]
                ) - 1

                met = metricas_fondo(
                    serie_valida(base_precios, nombre),
                    fecha_real_final,
                )

                resumen.append(
                    {
                        "Fondo": nombre,
                        "Fecha inicial usada": fecha_real_inicial.date(),
                        "Fecha final usada": fecha_real_final.date(),
                        "Rendimiento periodo": rendimiento_periodo,
                        "YTD": met["YTD"],
                        "1 mes": met["1 mes"],
                        "3 meses": met["3 meses"],
                        "6 meses": met["6 meses"],
                        "1 año": met["1 año"],
                        "Volatilidad anualizada": met["Volatilidad"],
                        "Máximo drawdown": met["Máximo drawdown"],
                        "Mejor mes": met["Mejor mes"],
                        "Peor mes": met["Peor mes"],
                    }
                )

            if not series_ajustadas:
                st.warning("No hay suficientes datos válidos en el periodo.")
            else:
                base100 = pd.concat(series_ajustadas, axis=1)
                base100.index.name = columna_fecha

                grafica_larga = (
                    base100.reset_index()
                    .melt(
                        id_vars=columna_fecha,
                        var_name="Fondo",
                        value_name="Índice base 100",
                    )
                    .dropna()
                )

                fig_comp = px.line(
                    grafica_larga,
                    x=columna_fecha,
                    y="Índice base 100",
                    color="Fondo",
                    title="Comparación normalizada · Base 100",
                    labels={columna_fecha: "Fecha"},
                )
                fig_comp.update_layout(hovermode="x unified")
                st.plotly_chart(fig_comp, use_container_width=True)

                tabla = pd.DataFrame(resumen).sort_values(
                    "Rendimiento periodo",
                    ascending=False,
                )

                columnas_pct = [
                    "Rendimiento periodo",
                    "YTD",
                    "1 mes",
                    "3 meses",
                    "6 meses",
                    "1 año",
                    "Volatilidad anualizada",
                    "Máximo drawdown",
                    "Mejor mes",
                    "Peor mes",
                ]

                tabla_mostrar = tabla.copy()
                for col in columnas_pct:
                    tabla_mostrar[col] = tabla_mostrar[col].map(
                        lambda x: porcentaje(x)
                    )

                st.subheader("Resumen comparativo")
                st.dataframe(
                    tabla_mostrar,
                    use_container_width=True,
                    hide_index=True,
                )

                st.download_button(
                    "Descargar comparativo",
                    data=tabla.to_csv(index=False).encode("utf-8-sig"),
                    file_name="comparativo_fondos.csv",
                    mime="text/csv",
                )
