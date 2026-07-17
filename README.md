# Dashboard de Fondos de Inversión

Aplicación en Streamlit para analizar una base histórica de precios diarios.

## Funcionalidades

### Calculadora de rendimiento

- Selección de fondo y periodo.
- Rendimiento del periodo.
- Fondos de deuda: anualización simple con base 360.
- Fondos de renta variable: anualización compuesta con base 360.
- Rendimiento YTD, 1 mes, 3 meses, 6 meses y 1 año.
- Volatilidad anualizada con 360 días.
- Máximo drawdown.
- Mejor y peor rendimiento mensual.
- Gráfica de precio con escala ajustada.
- Gráfica normalizada a índice base 100.
- Descarga de resultados en CSV.

### Comparador de fondos

- Comparación de varios fondos.
- Todas las series normalizadas a base 100.
- Tabla comparativa de rendimiento y riesgo.
- Descarga del comparativo en CSV.

## Base de precios

La estructura esperada es:

| Fecha | Fondo A | Fondo B | Fondo C |
|---|---:|---:|---:|
| 31/12/2025 | 1.000000 | 2.000000 | 3.000000 |
| 02/01/2026 | 1.001000 | 2.010000 | 3.005000 |

Los precios vacíos, no numéricos o iguales a cero se consideran no disponibles.

## Persistencia de la última base

La aplicación guarda automáticamente la última base cargada en la carpeta `data/`.

Esto funciona de forma permanente al ejecutar la app localmente o en un servidor con almacenamiento persistente. En Streamlit Community Cloud, el sistema de archivos es temporal; el archivo puede desaparecer después de un reinicio, suspensión o nuevo despliegue.

Para tener siempre una base disponible en Streamlit Cloud, agrega manualmente al repositorio uno de estos archivos:

- `data/base_predeterminada.xlsx`
- `data/base_predeterminada.xls`
- `data/base_predeterminada.csv`

La aplicación la cargará automáticamente cuando no exista una última base guardada.

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Despliegue en Streamlit Cloud

1. Sube todos los archivos a un repositorio de GitHub.
2. En Streamlit Cloud selecciona el repositorio.
3. Usa `app.py` como archivo principal.
4. Pulsa **Deploy**.
