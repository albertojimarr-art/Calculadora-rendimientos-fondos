# Calculadora de rendimientos de fondos

Aplicación desarrollada en Streamlit para calcular rendimientos a partir de una base histórica de precios diarios.

## Estructura esperada

- Una columna con las fechas, preferentemente llamada `Fecha`.
- Una columna por cada fondo de inversión.
- Una fila por fecha.
- Los precios iguales a cero se tratan como datos no disponibles.

Ejemplo:

| Fecha | Fondo A | Fondo B |
|---|---:|---:|
| 31/12/2019 | 2.811676 | 1.000000 |
| 02/01/2020 | 2.822244 | 1.001500 |

## Metodologías

### Fondos de deuda

Anualización simple con base de 360 días:

```text
((Precio final / Precio inicial) - 1) × (360 / días)
```

### Fondos de renta variable

Anualización compuesta con base de 360 días:

```text
(Precio final / Precio inicial) ^ (360 / días) - 1
```

## Funciones principales

- Carga de archivos `.xlsx`, `.xls` y `.csv`.
- Selección de hoja en archivos Excel.
- Detección automática de la columna `Fecha`.
- Búsqueda y selección de fondo.
- Exclusión automática de precios vacíos, no numéricos o iguales a cero.
- Selección únicamente entre fechas con precio válido para el fondo.
- Rendimiento del periodo y rendimiento anualizado.
- Gráfica histórica del periodo elegido.
- Descarga del resultado en CSV.

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicación en Streamlit Community Cloud

1. Sube todos los archivos del proyecto a un repositorio de GitHub.
2. Crea una nueva aplicación en Streamlit Community Cloud.
3. Selecciona el repositorio y la rama `main`.
4. Usa `app.py` como archivo principal.
5. Presiona **Deploy**.
