from __future__ import annotations

from io import BytesIO
from typing import Final

import pandas as pd
import streamlit as st

BASE_ANUAL: Final[int] = 360

st.set_page_config(
    page_title="Calculadora de rendimientos de fondos",
    page_icon="📈",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def cargar_archivo(contenido: bytes, nombre: str, hoja: str | None = None) -> pd.DataFrame:
    """Carga un archivo Excel o CSV y devuelve una copia del DataFrame."""
    archivo = BytesIO(contenido)

    if nombre.lower().endswith(".csv"):
        return pd.read_csv(archivo)

    return pd.read_excel(archivo, sheet_name=hoja or 0)


@st.cache_data(show_spinner=False)
def obtener_hojas(contenido: bytes) -> list[str]:
    """Obtiene las hojas disponibles de un archivo Excel."""
    return pd.ExcelFile(BytesIO(contenido)).sheet_names


def detectar_columna_fecha(columnas: list[str]) -> int:
    """Devuelve el índice de la columna que probablemente contiene las fechas."""
    for indice, columna in enumerate(columnas):
        if str(columna).strip().lower() in {"fecha", "date", "fechas"}:
            return indice
    return 0


def preparar_fondo(df: pd.DataFrame, columna_fecha: str, fondo: str) -> pd.DataFrame:
    """Limpia fechas y precios; considera ceros como datos no disponibles."""
    datos = df[[columna_fecha, fondo]].copy()

    datos[columna_fecha] = pd.to_datetime(
        datos[columna_fecha],
        errors="coerce",
        dayfirst=True,
    )
    datos[fondo] = pd.to_numeric(datos[fondo], errors="coerce")

    datos = datos.dropna(subset=[columna_fecha, fondo])
    datos = datos[datos[fondo] > 0]
    datos = datos.sort_values(columna_fecha)
    datos = datos.drop_duplicates(subset=[columna_fecha], keep="last")

    return datos.reset_index(drop=True)


def calcular_rendimientos(
    precio_inicial: float,
    precio_final: float,
    dias: int,
    tipo_fondo: str,
) -> tuple[float, float, str]:
    """Calcula rendimiento del periodo y anualizado con base de 360 días."""
    rendimiento_periodo = (precio_final / precio_inicial) - 1

    if tipo_fondo == "Deuda":
        rendimiento_anualizado = rendimiento_periodo * (BASE_ANUAL / dias)
        metodologia = "Simple, base 360"
    else:
        rendimiento_anualizado = (precio_final / precio_inicial) ** (BASE_ANUAL / dias) - 1
        metodologia = "Compuesta, base 360"

    return rendimiento_periodo, rendimiento_anualizado, metodologia


st.title("📈 Calculadora de rendimientos de fondos")
st.caption(
    "Carga una base histórica con fechas en filas y fondos en columnas. "
    "Los precios iguales a cero se consideran datos no disponibles."
)

with st.expander("Metodologías utilizadas"):
    st.markdown(
        """
        **Fondos de deuda — anualización simple, base 360**

        `((Precio final / Precio inicial) - 1) × (360 / días)`

        **Fondos de renta variable — anualización compuesta, base 360**

        `(Precio final / Precio inicial) ^ (360 / días) - 1`
        """
    )

archivo = st.file_uploader(
    "Sube tu base de precios diarios",
    type=["xlsx", "xls", "csv"],
    help="La primera fila debe contener los nombres de los fondos.",
)

if archivo is None:
    st.info("Carga un archivo Excel o CSV para comenzar.")
    st.stop()

contenido = archivo.getvalue()
es_csv = archivo.name.lower().endswith(".csv")

try:
    hoja = None
    if not es_csv:
        hojas = obtener_hojas(contenido)
        hoja = st.selectbox("Hoja de trabajo", hojas)

    df = cargar_archivo(contenido, archivo.name, hoja)
except Exception as exc:
    st.error("No fue posible leer el archivo. Verifica que no esté dañado o protegido.")
    st.exception(exc)
    st.stop()

if df.empty or len(df.columns) < 2:
    st.error("La base debe contener una columna de fechas y al menos una columna de precios.")
    st.stop()

columnas = [str(columna) for columna in df.columns]
df.columns = columnas
indice_fecha = detectar_columna_fecha(columnas)

col_config_1, col_config_2 = st.columns([1, 2])
with col_config_1:
    columna_fecha = st.selectbox(
        "Columna de fecha",
        columnas,
        index=indice_fecha,
    )

fondos = [columna for columna in columnas if columna != columna_fecha]
with col_config_2:
    fondo = st.selectbox(
        "Fondo",
        fondos,
        help="Puedes escribir dentro del selector para buscar el nombre del fondo.",
    )

datos = preparar_fondo(df, columna_fecha, fondo)

if datos.empty:
    st.error("El fondo seleccionado no contiene precios válidos mayores a cero.")
    st.stop()

fecha_min = datos[columna_fecha].min().date()
fecha_max = datos[columna_fecha].max().date()
numero_observaciones = len(datos)

m1, m2, m3 = st.columns(3)
m1.metric("Primera fecha disponible", fecha_min.strftime("%d/%m/%Y"))
m2.metric("Última fecha disponible", fecha_max.strftime("%d/%m/%Y"))
m3.metric("Precios válidos", f"{numero_observaciones:,}")

st.divider()

tipo_fondo = st.radio(
    "Tipo de fondo",
    options=["Deuda", "Renta variable"],
    horizontal=True,
    help=(
        "Deuda utiliza anualización simple. "
        "Renta variable utiliza anualización compuesta. Ambas usan base 360."
    ),
)

fechas_validas = datos[columna_fecha].dt.date.tolist()

col_fecha_1, col_fecha_2 = st.columns(2)
with col_fecha_1:
    fecha_inicial = st.selectbox(
        "Fecha inicial",
        fechas_validas,
        index=0,
        format_func=lambda fecha: fecha.strftime("%d/%m/%Y"),
    )

with col_fecha_2:
    indice_final_predeterminado = len(fechas_validas) - 1
    fecha_final = st.selectbox(
        "Fecha final",
        fechas_validas,
        index=indice_final_predeterminado,
        format_func=lambda fecha: fecha.strftime("%d/%m/%Y"),
    )

if fecha_final <= fecha_inicial:
    st.warning("La fecha final debe ser posterior a la fecha inicial.")
    st.stop()

fila_inicial = datos.loc[datos[columna_fecha].dt.date == fecha_inicial].iloc[-1]
fila_final = datos.loc[datos[columna_fecha].dt.date == fecha_final].iloc[-1]

precio_inicial = float(fila_inicial[fondo])
precio_final = float(fila_final[fondo])
dias = (pd.Timestamp(fecha_final) - pd.Timestamp(fecha_inicial)).days

rendimiento_periodo, rendimiento_anualizado, metodologia = calcular_rendimientos(
    precio_inicial,
    precio_final,
    dias,
    tipo_fondo,
)

st.subheader("Resultados")

r1, r2, r3, r4 = st.columns(4)
r1.metric("Precio inicial", f"{precio_inicial:,.6f}")
r2.metric("Precio final", f"{precio_final:,.6f}")
r3.metric("Días naturales", f"{dias:,}")
r4.metric("Metodología", metodologia)

r5, r6 = st.columns(2)
r5.metric("Rendimiento del periodo", f"{rendimiento_periodo:.4%}")
r6.metric("Rendimiento anualizado", f"{rendimiento_anualizado:.4%}")

with st.expander("Ver detalle del cálculo"):
    st.write(f"**Fondo:** {fondo}")
    st.write(
        f"**Periodo:** {fecha_inicial.strftime('%d/%m/%Y')} a "
        f"{fecha_final.strftime('%d/%m/%Y')}"
    )
    st.code(
        f"Rendimiento del periodo\n"
        f"({precio_final:.6f} / {precio_inicial:.6f}) - 1\n"
        f"= {rendimiento_periodo:.6%}\n\n"
        + (
            f"Rendimiento anualizado simple, base 360\n"
            f"{rendimiento_periodo:.6%} × (360 / {dias})\n"
            f"= {rendimiento_anualizado:.6%}"
            if tipo_fondo == "Deuda"
            else
            f"Rendimiento anualizado compuesto, base 360\n"
            f"({precio_final:.6f} / {precio_inicial:.6f}) ^ (360 / {dias}) - 1\n"
            f"= {rendimiento_anualizado:.6%}"
        )
    )

st.subheader("Evolución del precio")
datos_periodo = datos[
    (datos[columna_fecha].dt.date >= fecha_inicial)
    & (datos[columna_fecha].dt.date <= fecha_final)
].set_index(columna_fecha)
st.line_chart(datos_periodo[[fondo]], height=360)

resultado = pd.DataFrame(
    {
        "Fondo": [fondo],
        "Tipo de fondo": [tipo_fondo],
        "Fecha inicial": [fecha_inicial.strftime("%d/%m/%Y")],
        "Precio inicial": [precio_inicial],
        "Fecha final": [fecha_final.strftime("%d/%m/%Y")],
        "Precio final": [precio_final],
        "Días naturales": [dias],
        "Rendimiento del periodo": [rendimiento_periodo],
        "Rendimiento anualizado": [rendimiento_anualizado],
        "Metodología": [metodologia],
    }
)

st.download_button(
    "Descargar resultado en CSV",
    data=resultado.to_csv(index=False).encode("utf-8-sig"),
    file_name="resultado_rendimiento.csv",
    mime="text/csv",
)
