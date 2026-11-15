"""
Prueba de concepto - Plataforma de multas vehiculares.

Tres pantallas:
  1. Registro de multas       -> reemplaza al Excel (ingreso de datos con validación)
  2. Carga de archivo         -> procesa un CSV/Excel en vivo (valida y separa errores)
  3. Consulta por DNI         -> muestra multas, mora y deuda de una persona

Para ejecutarla:   streamlit run app.py
"""
import io
import time
import uuid
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import logic
from db import crear_base

st.set_page_config(page_title="Multas - Prueba de concepto", page_icon="🚗", layout="wide")

INFRACCIONES = [
    "Exceso de velocidad",
    "Cruzar la luz roja",
    "Estacionar en zona prohibida",
    "No portar licencia de conducir",
    "Conducir sin SOAT vigente",
    "Uso de celular al conducir",
    "No respetar el paso peatonal",
]


@st.cache_resource
def obtener_base():
    return crear_base()


@st.cache_data(ttl=10, show_spinner=False)
def resumen_cacheado(_base):
    return _base.resumen()


def soles(x):
    return f"S/ {x:,.2f}"


def hora_lima(valor):
    """Convierte la fecha de carga a hora de Lima para mostrarla."""
    t = pd.to_datetime(valor, utc=True)
    return t.tz_convert("America/Lima").strftime("%d/%m/%Y %H:%M")


# ======================================================================
# Pantalla 1: registro de multas (data entry)
# ======================================================================
def pantalla_registro(base):
    st.header("Registro de multas")
    st.caption("Reemplaza al Excel: los datos se validan al escribirlos y van directo a la plataforma.")

    with st.form("form_registro"):
        c1, c2, c3 = st.columns(3)
        dni = c1.text_input("DNI del infractor", max_chars=8, placeholder="12345678")
        nombre = c2.text_input("Nombre completo")
        placa = c3.text_input("Placa del vehículo", max_chars=7, placeholder="ABC-123")

        c4, c5 = st.columns(2)
        infraccion = c4.selectbox("Infracción", INFRACCIONES)
        monto = c5.number_input("Monto de la multa (S/)", min_value=0.0, value=215.0, step=5.0)

        c6, c7, c8 = st.columns(3)
        f_infraccion = c6.date_input("Fecha de la infracción", value=date.today())
        f_vencimiento = c7.date_input("Fecha de vencimiento", value=date.today() + timedelta(days=30))
        estado = c8.selectbox("Estado", logic.ESTADOS)

        enviar = st.form_submit_button("Guardar multa", type="primary")

    if enviar:
        id_multa = "W-" + uuid.uuid4().hex[:8].upper()
        fila = pd.DataFrame([{
            "id_multa": id_multa, "dni": dni, "nombre": nombre, "placa": placa,
            "infraccion": infraccion, "monto": str(monto),
            "fecha_infraccion": str(f_infraccion), "fecha_vencimiento": str(f_vencimiento),
            "estado": estado,
        }])
        validas, rechazadas = logic.validar_filas(fila)
        if not rechazadas.empty:
            st.error("No se pudo guardar. Corrige lo siguiente:")
            for motivo in rechazadas.loc[0, "motivo"].split("; "):
                st.write(f"- {motivo}")
        else:
            base.insertar(validas, fuente="FORMULARIO")
            resumen_cacheado.clear()
            st.success(f"Multa guardada correctamente. Código: {id_multa}")

    st.subheader("Últimos registros en la plataforma")
    ultimos = base.ultimos(8)
    if ultimos.empty:
        st.info("Todavía no hay multas registradas.")
    else:
        st.dataframe(
            ultimos[["id_multa", "dni", "nombre", "placa", "infraccion", "monto",
                     "fecha_vencimiento", "estado", "fuente"]],
            hide_index=True, width="stretch",
            column_config={"monto": st.column_config.NumberColumn("monto", format="S/ %.2f"),
                           "fecha_vencimiento": st.column_config.DateColumn("vencimiento")})


# ======================================================================
# Pantalla 2: carga y procesamiento de archivo
# ======================================================================
def leer_archivo(archivo):
    """Lee un CSV o Excel como texto, para validar todo con las mismas reglas."""
    if archivo.name.lower().endswith(".xlsx"):
        try:
            # "calamine" lee Excel mucho más rápido (importante con cientos de miles de filas)
            return pd.read_excel(archivo, dtype=str, engine="calamine").fillna("")
        except (ImportError, ValueError):  # si "calamine" no está instalado, usa el lector normal
            return pd.read_excel(archivo, dtype=str).fillna("")
    crudo = archivo.getvalue()
    try:
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = crudo.decode("latin-1")
    primera = texto.split("\n", 1)[0]
    sep = ";" if primera.count(";") > primera.count(",") else ","
    return pd.read_csv(io.StringIO(texto), sep=sep, dtype=str, keep_default_na=False)


def pantalla_carga(base):
    st.header("Carga de archivo")
    st.caption("Sube un archivo CSV o Excel. Se valida fila por fila: las correctas se cargan "
               "y las incorrectas se separan en un reporte para corregirlas.")

    archivo = st.file_uploader("Archivo de multas (CSV o Excel)", type=["csv", "xlsx"])
    if archivo is None:
        st.info("Columnas obligatorias: " + ", ".join(logic.COLUMNAS_OBLIGATORIAS) +
                ". Opcional: fecha_pago. Fechas en formato AAAA-MM-DD.")
        return

    clave = f"{archivo.name}-{archivo.size}"
    if st.session_state.get("clave_archivo") != clave:
        st.session_state.pop("resultado", None)
        st.session_state["clave_archivo"] = clave
        st.session_state["cargado"] = False

        with st.status("Procesando archivo...", expanded=True) as estado:
            t0 = time.time()
            st.write("Paso 1: leyendo el archivo")
            df = leer_archivo(archivo)
            st.write(f"- {len(df):,} filas leídas ({time.time() - t0:.1f} s)")

            st.write("Paso 2: verificando la estructura")
            faltantes = logic.verificar_estructura(df)
            if faltantes:
                estado.update(label="Archivo rechazado", state="error")
                st.error("Faltan columnas obligatorias: " + ", ".join(faltantes))
                st.stop()
            st.write("- Estructura correcta")

            st.write("Paso 3: validando cada fila")
            t1 = time.time()
            validas, rechazadas = logic.validar_filas(df, base.ids_existentes())
            st.write(f"- {len(validas):,} correctas y {len(rechazadas):,} con error "
                     f"({time.time() - t1:.1f} s)")
            estado.update(label="Validación terminada", state="complete", expanded=False)

        st.session_state["resultado"] = {
            "leidas": len(df), "validas": validas, "rechazadas": rechazadas}

    r = st.session_state.get("resultado")
    if r is None:
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("Filas leídas", f"{r['leidas']:,}")
    m2.metric("Correctas (se pueden cargar)", f"{len(r['validas']):,}")
    m3.metric("Con error (rechazadas)", f"{len(r['rechazadas']):,}")

    tab1, tab2, tab3 = st.tabs(["Filas correctas", "Filas rechazadas", "Motivos de rechazo"])
    with tab1:
        st.dataframe(r["validas"].head(200), hide_index=True, width="stretch")
        if len(r["validas"]) > 200:
            st.caption("Se muestran las primeras 200 filas.")
    with tab2:
        if r["rechazadas"].empty:
            st.success("No hay filas rechazadas.")
        else:
            st.dataframe(r["rechazadas"].head(500), hide_index=True, width="stretch")
            st.download_button(
                "Descargar reporte de rechazadas (CSV)",
                r["rechazadas"].to_csv(index=False).encode("utf-8-sig"),
                file_name="filas_rechazadas.csv", mime="text/csv")
    with tab3:
        st.dataframe(logic.resumen_motivos(r["rechazadas"]), hide_index=True,
                     width="stretch")

    st.divider()
    cargado = st.session_state.get("cargado", False)
    if st.button(f"Cargar {len(r['validas']):,} filas correctas a la plataforma",
                 type="primary", disabled=cargado or r["validas"].empty):
        with st.spinner("Cargando a la plataforma..."):
            t0 = time.time()
            n = base.insertar(r["validas"], fuente="ARCHIVO")
        resumen_cacheado.clear()
        st.session_state["cargado"] = True
        st.success(f"Se cargaron {n:,} filas en {time.time() - t0:.1f} s. "
                   "Ya se pueden consultar en la pantalla 3.")
    elif cargado:
        st.success("Este archivo ya fue cargado.")


# ======================================================================
# Pantalla 3: consulta por DNI
# ======================================================================
def pantalla_consulta(base):
    st.header("Consulta de multas y deudas")
    st.caption("Ingresa el DNI para ver las multas, la mora por retraso y la deuda total.")


    with st.form("form_consulta"):
        dni = st.text_input("DNI", max_chars=8, placeholder="12345678")
        consultar = st.form_submit_button("Consultar", type="primary")

    if not consultar:
        return
    dni = dni.strip()
    if not (dni.isdigit() and len(dni) == 8):
        st.error("El DNI debe tener 8 dígitos.")
        return

    with st.spinner("Consultando..."):
        t0 = time.time()
        df = base.consultar_dni(dni)
        segundos = time.time() - t0

    if df.empty:
        st.info(f"No se encontraron multas para el DNI {dni}.")
        return

    hoy = date.today()
    d = logic.calcular_mora(df, hoy, logic.TASA_MORA_DIARIA)
    pendientes = d[d["estado"] == "PENDIENTE"]

    st.subheader(d["nombre"].iloc[0])
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Multas pendientes", f"{len(pendientes)}")
    m2.metric("Monto de multas", soles(pendientes["monto"].sum()))
    m3.metric("Mora acumulada", soles(pendientes["mora"].sum()))
    m4.metric("Deuda total", soles(d["deuda_total"].sum()))

    d["fecha_infraccion"] = d["fecha_infraccion"].dt.date
    d["fecha_vencimiento"] = d["fecha_vencimiento"].dt.date
    st.dataframe(
        d[["id_multa", "placa", "infraccion", "fecha_infraccion", "fecha_vencimiento",
           "situacion", "monto", "dias_retraso", "mora", "deuda_total"]],
        hide_index=True, width="stretch",
        column_config={
            "monto": st.column_config.NumberColumn("monto", format="S/ %.2f"),
            "mora": st.column_config.NumberColumn("mora", format="S/ %.2f"),
            "deuda_total": st.column_config.NumberColumn("deuda total", format="S/ %.2f"),
            "dias_retraso": st.column_config.NumberColumn("días de retraso"),
            "fecha_infraccion": st.column_config.DateColumn("infracción"),
            "fecha_vencimiento": st.column_config.DateColumn("vencimiento"),
        })
    st.caption(f"Información actualizada al {hora_lima(df['fecha_carga'].max())} (hora de Lima). "
               f"Mora calculada al {hoy:%d/%m/%Y} ({logic.TASA_MORA_DIARIA * 100:.2f} % diario "
               f"sobre multas vencidas). Consulta resuelta en {segundos:.2f} s.")

    with st.expander("Ver todos los campos de las multas"):
        completo = df.drop(columns=["fecha_carga"]).copy()
        for c in ("fecha_infraccion", "fecha_vencimiento", "fecha_pago"):
            completo[c] = completo[c].dt.date
        st.dataframe(completo, hide_index=True, width="stretch")


# ======================================================================
# Estructura general
# ======================================================================
base = obtener_base()

st.sidebar.title("Plataforma de multas")
st.sidebar.caption("Prueba de concepto")
pagina = st.sidebar.radio(
    "Pantalla",
    ["1. Registro de multas", "2. Carga de archivo", "3. Consulta por DNI"])

st.sidebar.divider()
contador = st.sidebar.empty()  # se llena al final, para mostrar el total ya actualizado
st.sidebar.caption(f"Almacenamiento: {base.descripcion}")

if pagina.startswith("1"):
    pantalla_registro(base)
elif pagina.startswith("2"):
    pantalla_carga(base)
else:
    pantalla_consulta(base)

total, ultima = resumen_cacheado(base)
contador.metric("Multas en la plataforma", f"{total:,}")
