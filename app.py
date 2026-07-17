# Ver README.md
# Esta versión requiere:
# streamlit, pandas, plotly, openpyxl, xlrd

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Calculadora de Rendimientos",layout="wide")
st.title("Calculadora de Rendimientos de Fondos")

f=st.file_uploader("Sube tu base",type=["xlsx","xls","csv"])
if f:
    if f.name.endswith(".csv"):
        df=pd.read_csv(f)
    else:
        xls=pd.ExcelFile(f)
        hoja=st.selectbox("Hoja",xls.sheet_names)
        df=pd.read_excel(f,sheet_name=hoja)

    fecha_col=df.columns[0]
    df[fecha_col]=pd.to_datetime(df[fecha_col],dayfirst=True,errors="coerce")
    fondos=[c for c in df.columns if c!=fecha_col]
    fondo=st.selectbox("Fondo",fondos)
    tipo=st.radio("Tipo",["Deuda","Renta variable"],horizontal=True)

    df[fondo]=pd.to_numeric(df[fondo],errors="coerce")
    df=df[(df[fondo].notna())&(df[fondo]!=0)].sort_values(fecha_col)

    fechas=df[fecha_col].dt.date.tolist()
    fi=st.selectbox("Fecha inicial",fechas,0)
    ff=st.selectbox("Fecha final",fechas,len(fechas)-1)

    if st.button("Calcular"):
        pi=float(df.loc[df[fecha_col].dt.date==fi,fondo].iloc[0])
        pf=float(df.loc[df[fecha_col].dt.date==ff,fondo].iloc[0])
        dias=(pd.Timestamp(ff)-pd.Timestamp(fi)).days
        rp=(pf/pi)-1
        ra=rp*(360/dias) if tipo=="Deuda" else (1+rp)**(360/dias)-1
        c1,c2,c3=st.columns(3)
        c1.metric("Periodo",f"{rp:.4%}")
        c2.metric("Anualizado",f"{ra:.4%}")
        c3.metric("Días",dias)

        periodo=df[(df[fecha_col].dt.date>=fi)&(df[fecha_col].dt.date<=ff)].copy()

        modo=st.radio("Gráfica",["Índice base 100","Precio con escala ajustada"],horizontal=True)
        if modo=="Índice base 100":
            periodo["Valor"]=periodo[fondo]/periodo[fondo].iloc[0]*100
            ytitle="Índice base 100"
        else:
            periodo["Valor"]=periodo[fondo]
            ytitle="Precio"

        fig=px.line(periodo,x=fecha_col,y="Valor",title=fondo)
        mn=periodo["Valor"].min();mx=periodo["Valor"].max()
        r=mx-mn
        m=r*0.1 if r>0 else max(abs(mn)*0.001,0.001)
        fig.update_yaxes(range=[mn-m,mx+m])
        fig.update_layout(hovermode="x unified",yaxis_title=ytitle)
        st.plotly_chart(fig,use_container_width=True)
