"""
Lógica de negocio de la prueba de concepto de multas.

Aquí viven DOS cosas, y las usan las tres pantallas:
  1. Las validaciones de datos (que una fila sea correcta o no).
  2. El cálculo de la mora (recargo por pagar con retraso).

Las mismas reglas se aplican al formulario de registro y a los archivos que
se cargan, para que la información entre siempre con la misma calidad.

La plataforma maneja 34 campos por multa:
  - 9 obligatorios (los mínimos para identificar y cobrar la multa),
  - 1 opcional de pago (fecha_pago),
  - 24 adicionales (vehículo, lugar, detección, pago, contacto).
"""
import pandas as pd

# ----------------------------------------------------------------------
# Campos
# ----------------------------------------------------------------------
COLUMNAS_OBLIGATORIAS = [
    "id_multa", "dni", "nombre", "placa", "infraccion",
    "monto", "fecha_infraccion", "fecha_vencimiento", "estado",
]
COLUMNAS_OPCIONALES = ["fecha_pago"]
ESTADOS = ["PENDIENTE", "PAGADA"]

# Campos adicionales: nombre -> (tipo, parámetro).
# Son opcionales; si vienen con dato, se valida según su tipo.
CAMPOS_EXTRA = {
    "hora_infraccion": ("hora", None),
    "codigo_infraccion": ("texto", None),
    "gravedad": ("lista", ["LEVE", "GRAVE", "MUY GRAVE"]),
    "puntos_licencia": ("entero", (0, 100)),
    "tipo_vehiculo": ("lista", ["AUTO", "CAMIONETA", "MOTO", "CAMION", "BUS"]),
    "marca": ("texto", None),
    "modelo": ("texto", None),
    "anio_vehiculo": ("entero", (1980, 2027)),
    "color": ("texto", None),
    "numero_licencia": ("texto", None),
    "departamento": ("texto", None),
    "provincia": ("texto", None),
    "distrito": ("texto", None),
    "direccion_infraccion": ("texto", None),
    "latitud": ("decimal", (-90, 90)),
    "longitud": ("decimal", (-180, 180)),
    "unidad_fiscalizadora": ("texto", None),
    "tipo_deteccion": ("lista", ["AGENTE", "FOTOPAPELETA", "CAMARA"]),
    "numero_papeleta": ("texto", None),
    "descuento_pct": ("decimal", (0, 100)),
    "medio_pago": ("lista", ["EFECTIVO", "TARJETA", "TRANSFERENCIA", "APP"]),
    "numero_operacion": ("texto", None),
    "telefono": ("telefono", None),
    "email": ("email", None),
}

# Todos los campos de datos, en el orden en que se guardan
COLUMNAS_DATOS = COLUMNAS_OBLIGATORIAS + COLUMNAS_OPCIONALES + list(CAMPOS_EXTRA)

COLUMNAS_FECHA = ["fecha_infraccion", "fecha_vencimiento", "fecha_pago"]


def tipo_db(columna):
    """Tipo de la columna en la base de datos (nombres de BigQuery)."""
    if columna == "monto":
        return "FLOAT"
    if columna in COLUMNAS_FECHA:
        return "DATE"
    if columna in CAMPOS_EXTRA:
        return {"entero": "INTEGER", "decimal": "FLOAT"}.get(CAMPOS_EXTRA[columna][0], "STRING")
    return "STRING"


# ----------------------------------------------------------------------
# Reglas del negocio (SUPUESTOS de la prueba de concepto: ajustar si el
# docente o el caso piden otra cosa)
# ----------------------------------------------------------------------
# Mora = monto x tasa diaria x días de retraso (solo para multas pendientes).
TASA_MORA_DIARIA = 0.001  # 0.1 % por día (supuesto)

RE_DNI = r"^\d{8}$"
RE_PLACA = r"^[A-Z0-9]{3}-?\d{3}$"
RE_HORA = r"^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$"
RE_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
RE_TELEFONO = r"^\d{9}$"


def normalizar_columnas(df):
    """Pone los nombres de columnas en minúscula y sin espacios."""
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def verificar_estructura(df):
    """Devuelve la lista de columnas obligatorias que faltan en el archivo."""
    columnas = {str(c).strip().lower() for c in df.columns}
    return [c for c in COLUMNAS_OBLIGATORIAS if c not in columnas]


def _texto(serie):
    """Convierte una columna a texto limpio (sin espacios, vacío si no hay dato)."""
    return serie.astype("object").where(serie.notna(), "").astype(str).str.strip()


def _validar_extra(campo, tipo, param, s):
    """
    Valida un campo adicional (opcional). Devuelve (falla, valor, mensaje):
    qué filas fallan, el valor ya convertido y el mensaje de error.
    """
    vacio = s.eq("")
    ninguna = pd.Series(False, index=s.index)
    como_texto = s.astype("object").where(~vacio, None)

    if tipo == "texto":
        return ninguna, como_texto, ""
    if tipo == "lista":
        mayus = s.str.upper()
        falla = ~vacio & ~mayus.isin(param)
        return falla, mayus.astype("object").where(~vacio, None), \
            f"{campo} inválido (valores permitidos: {', '.join(param)})"
    if tipo in ("entero", "decimal"):
        n = pd.to_numeric(s, errors="coerce")
        lo, hi = param
        falla = ~vacio & (n.isna() | (n < lo) | (n > hi))
        if tipo == "entero":
            falla = falla | (~vacio & n.notna() & (n % 1 != 0))
            valor = n.round().astype("Int64")
            return falla, valor, f"{campo} inválido (entero entre {lo} y {hi})"
        return falla, n.astype(float), f"{campo} inválido (número entre {lo} y {hi})"
    if tipo == "hora":
        return ~vacio & ~s.str.match(RE_HORA), como_texto, f"{campo} inválida (formato HH:MM)"
    if tipo == "email":
        return ~vacio & ~s.str.match(RE_EMAIL), como_texto, f"{campo} inválido"
    if tipo == "telefono":
        return ~vacio & ~s.str.match(RE_TELEFONO), como_texto, f"{campo} inválido (9 dígitos)"
    return ninguna, como_texto, ""


def validar_filas(df, ids_existentes=frozenset()):
    """
    Revisa cada fila del DataFrame.

    Devuelve (validas, rechazadas):
      - validas: filas correctas, con los tipos ya convertidos (listas para cargar).
      - rechazadas: filas con error, con el número de fila y el motivo.
    """
    d = normalizar_columnas(df).reset_index(drop=True)
    for c in COLUMNAS_DATOS:
        if c not in d.columns:
            d[c] = ""

    d["fila"] = d.index + 2  # +2: la fila 1 del archivo es el encabezado
    motivos = pd.Series([""] * len(d), index=d.index, dtype="object")

    def marcar(falla, mensaje):
        nonlocal motivos
        falla = falla.fillna(True).astype(bool)
        if falla.any():
            motivos = motivos.where(~falla, motivos + mensaje + "; ")

    # Texto limpio
    id_multa = _texto(d["id_multa"])
    # Excel suele guardar el DNI como número y agrega ".0": se limpia
    dni = _texto(d["dni"]).str.replace(r"\.0$", "", regex=True)
    nombre = _texto(d["nombre"])
    infraccion = _texto(d["infraccion"])
    placa = _texto(d["placa"]).str.upper()
    estado = _texto(d["estado"]).str.upper()

    # Tipos numéricos y de fecha (si no se pueden convertir quedan vacíos)
    monto = pd.to_numeric(_texto(d["monto"]), errors="coerce")
    f_infraccion = pd.to_datetime(_texto(d["fecha_infraccion"]),
                                  errors="coerce", format="mixed")
    f_vencimiento = pd.to_datetime(_texto(d["fecha_vencimiento"]),
                                   errors="coerce", format="mixed")
    f_pago = pd.to_datetime(_texto(d["fecha_pago"]),
                            errors="coerce", format="mixed")

    # ---- Reglas de los campos obligatorios ----
    marcar(id_multa.eq(""), "id_multa vacío")
    marcar(~dni.str.match(RE_DNI), "DNI inválido (deben ser 8 dígitos)")
    marcar(nombre.eq(""), "nombre vacío")
    marcar(~placa.str.match(RE_PLACA), "placa inválida (formato ABC-123)")
    marcar(infraccion.eq(""), "infracción vacía")
    marcar(monto.isna() | (monto <= 0), "monto inválido (debe ser un número mayor a 0)")
    marcar(f_infraccion.isna(), "fecha de infracción inválida")
    marcar(f_vencimiento.isna(), "fecha de vencimiento inválida")
    marcar(f_vencimiento.notna() & f_infraccion.notna() & (f_vencimiento < f_infraccion),
           "el vencimiento es anterior a la infracción")
    marcar(~estado.isin(ESTADOS), "estado inválido (PENDIENTE o PAGADA)")
    marcar(id_multa.ne("") & id_multa.duplicated(keep="first"),
           "id_multa repetido dentro del archivo")
    marcar(id_multa.isin(set(ids_existentes)), "id_multa ya existe en la plataforma")
    # fecha_pago: si viene con dato, debe ser una fecha
    marcar(_texto(d["fecha_pago"]).ne("") & f_pago.isna(), "fecha de pago inválida")

    salida = {
        "id_multa": id_multa,
        "dni": dni,
        "nombre": nombre,
        "placa": placa.str.replace(r"^([A-Z0-9]{3})(\d{3})$", r"\1-\2", regex=True),
        "infraccion": infraccion,
        "monto": monto.astype(float),
        "fecha_infraccion": f_infraccion.dt.date,
        "fecha_vencimiento": f_vencimiento.dt.date,
        "estado": estado,
        "fecha_pago": f_pago.dt.date,
    }

    # ---- Reglas de los campos adicionales ----
    for campo, (tipo, param) in CAMPOS_EXTRA.items():
        falla, valor, mensaje = _validar_extra(campo, tipo, param, _texto(d[campo]))
        marcar(falla, mensaje)
        salida[campo] = valor

    ok = motivos.eq("")

    validas = pd.DataFrame(salida)[COLUMNAS_DATOS][ok].reset_index(drop=True)
    validas["fecha_pago"] = validas["fecha_pago"].astype("object").where(
        validas["fecha_pago"].notna(), None)

    rechazadas = d.loc[~ok, ["fila"] + COLUMNAS_DATOS].copy()
    rechazadas["motivo"] = motivos[~ok].str.rstrip("; ").str.strip()
    rechazadas = rechazadas.reset_index(drop=True)
    return validas, rechazadas


def resumen_motivos(rechazadas):
    """Cuenta cuántas filas fallaron por cada motivo."""
    if rechazadas.empty:
        return pd.DataFrame(columns=["motivo", "filas"])
    conteo = (rechazadas["motivo"].str.split("; ").explode().value_counts()
              .rename_axis("motivo").reset_index(name="filas"))
    return conteo


def calcular_mora(df, fecha_calculo, tasa_diaria=TASA_MORA_DIARIA):
    """
    Agrega a las multas: días de retraso, mora, deuda total y situación.
    Solo las multas PENDIENTES generan mora y deuda.
    """
    d = df.copy()
    vencimiento = pd.to_datetime(d["fecha_vencimiento"])
    pendiente = d["estado"].eq("PENDIENTE")
    dias = (pd.Timestamp(fecha_calculo) - vencimiento).dt.days.clip(lower=0)
    d["dias_retraso"] = dias.where(pendiente, 0).astype(int)
    d["mora"] = (d["monto"] * tasa_diaria * d["dias_retraso"]).round(2)
    d["deuda_total"] = (d["monto"] + d["mora"]).where(pendiente, 0.0).round(2)
    d["situacion"] = "Pagada"
    d.loc[pendiente & (d["dias_retraso"] == 0), "situacion"] = "Vigente"
    d.loc[pendiente & (d["dias_retraso"] > 0), "situacion"] = "En mora"
    return d
