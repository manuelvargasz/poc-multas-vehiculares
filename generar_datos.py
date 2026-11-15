"""
Genera datos de ejemplo (ficticios) para la prueba de concepto.
Todos los archivos tienen 34 campos por multa.

Uso:
    python generar_datos.py                  -> archivos pequeños de demostración
    python generar_datos.py --excel 500000   -> además, un Excel de 500.000 filas
    python generar_datos.py --csv 1000000    -> además, un CSV de 1.000.000 de filas

Crea la carpeta "datos_ejemplo" con:
    multas_base.csv          2,000 multas correctas (para la primera carga)
    archivo_demo.csv         500 filas con errores a propósito (para la demo en vivo)
    archivo_demo.xlsx        lo mismo, en Excel
    multas_excel_N.xlsx      (solo con --excel) Excel grande, con ~1,5 % de filas con errores
    multas_grande_N.csv      (solo con --csv) CSV grande, con ~1,5 % de filas con errores
"""
import argparse
import os
import random
import time
import unicodedata
from datetime import date, timedelta

import numpy as np
import pandas as pd

from logic import COLUMNAS_DATOS

random.seed(7)
np.random.seed(7)

HOY = date(2026, 11, 9)

# infracción: (monto, código, gravedad, puntos de licencia)
INFRACCIONES = {
    "Exceso de velocidad": (430.0, "M-27", "MUY GRAVE", 30),
    "Cruzar la luz roja": (645.0, "M-26", "MUY GRAVE", 50),
    "Estacionar en zona prohibida": (215.0, "L-04", "LEVE", 0),
    "No portar licencia de conducir": (215.0, "L-01", "LEVE", 0),
    "Conducir sin SOAT vigente": (430.0, "G-11", "GRAVE", 10),
    "Uso de celular al conducir": (215.0, "G-14", "GRAVE", 10),
    "No respetar el paso peatonal": (645.0, "M-32", "MUY GRAVE", 40),
}
NOMBRES = ["Carlos", "María", "José", "Lucía", "Miguel", "Rosa", "Luis", "Ana", "Jorge", "Carmen",
           "Pedro", "Elena", "Diego", "Sofía", "Raúl", "Patricia", "Andrés", "Valeria", "Hugo", "Julia"]
APELLIDOS = ["Quispe", "Flores", "Rojas", "Mendoza", "Torres", "Vargas", "Castillo", "Ramos",
             "Huamán", "Chávez", "Salazar", "Paredes", "Campos", "Ríos", "Soto", "Peña"]
GEOGRAFIA = [
    ("LIMA", "LIMA", "MIRAFLORES"), ("LIMA", "LIMA", "SAN ISIDRO"), ("LIMA", "LIMA", "SURCO"),
    ("LIMA", "LIMA", "LA MOLINA"), ("AREQUIPA", "AREQUIPA", "CERCADO"), ("CUSCO", "CUSCO", "WANCHAQ"),
    ("LA LIBERTAD", "TRUJILLO", "TRUJILLO"), ("PIURA", "PIURA", "CASTILLA"),
    ("LAMBAYEQUE", "CHICLAYO", "CHICLAYO"), ("JUNIN", "HUANCAYO", "HUANCAYO"),
]
CALLES = ["Arequipa", "Javier Prado", "Brasil", "Universitaria", "Benavides", "Angamos",
          "Larco", "Salaverry", "Grau", "Bolognesi", "San Martín", "Colonial"]
MARCAS = {"Toyota": ["Yaris", "Corolla", "Hilux"], "Hyundai": ["Accent", "Elantra", "Tucson"],
          "Kia": ["Rio", "Picanto", "Sportage"], "Nissan": ["Versa", "Sentra", "Frontier"],
          "Chevrolet": ["Sail", "Spark", "Onix"]}
COLORES = ["BLANCO", "NEGRO", "GRIS", "ROJO", "AZUL", "PLATA"]
UNIDADES = ["UF-LIMA-01", "UF-LIMA-02", "UF-AREQUIPA-01", "UF-CUSCO-01", "UF-NORTE-01"]


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def generar(n, desde_id, n_personas):
    """Genera n multas correctas (34 campos) repartidas entre n_personas."""
    # ---- Datos por persona (se repiten en sus multas)
    dnis = np.random.randint(10_000_000, 99_999_999, size=n_personas).astype(str)
    nombres = [f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"
               for _ in range(n_personas)]
    placas = [f"{''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ', k=3))}-{random.randint(100, 999)}"
              for _ in range(n_personas)]
    marcas = [random.choice(list(MARCAS)) for _ in range(n_personas)]
    modelos = [random.choice(MARCAS[m]) for m in marcas]
    anios = np.random.randint(2005, 2026, size=n_personas)
    colores = np.random.choice(COLORES, size=n_personas)
    tipos = np.random.choice(["AUTO", "CAMIONETA", "MOTO", "CAMION", "BUS"], size=n_personas,
                             p=[0.6, 0.2, 0.15, 0.03, 0.02])
    licencias = np.array([f"Q{d}" for d in dnis])
    telefonos = np.array(["9" + str(x) for x in np.random.randint(10_000_000, 99_999_999, n_personas)])
    emails = np.array([f"{_sin_tildes(nom.split()[0]).lower()}{random.randint(1, 999)}@correo.pe"
                       for nom in nombres])

    idx = np.random.randint(0, n_personas, size=n)  # a qué persona pertenece cada multa

    # ---- Datos de cada multa
    inf = np.random.choice(list(INFRACCIONES), size=n)
    monto = np.array([INFRACCIONES[i][0] for i in inf])
    codigo = np.array([INFRACCIONES[i][1] for i in inf])
    gravedad = np.array([INFRACCIONES[i][2] for i in inf])
    puntos = np.array([INFRACCIONES[i][3] for i in inf])
    dias_atras = np.random.randint(5, 400, size=n)
    f_inf = np.array([str(HOY - timedelta(days=int(x))) for x in dias_atras])
    f_ven = np.array([str(HOY - timedelta(days=int(x)) + timedelta(days=30)) for x in dias_atras])
    pagada = np.random.rand(n) < 0.35
    dias_pago = np.random.randint(0, 26, size=n)
    f_pago = np.array([str(HOY - timedelta(days=int(a)) + timedelta(days=30 - int(p))) if y else ""
                       for a, p, y in zip(dias_atras, dias_pago, pagada)])

    geo = np.random.randint(0, len(GEOGRAFIA), size=n)
    horas = pd.Series(np.random.randint(0, 24, n)).astype(str).str.zfill(2) + ":" + \
        pd.Series(np.random.randint(0, 60, n)).astype(str).str.zfill(2)
    calle = np.random.choice(CALLES, size=n)
    numero = np.random.randint(100, 4000, size=n).astype(str)
    ids = np.arange(desde_id, desde_id + n)

    df = pd.DataFrame({
        "id_multa": [f"M-{i:07d}" for i in ids],
        "dni": dnis[idx],
        "nombre": np.array(nombres)[idx],
        "placa": np.array(placas)[idx],
        "infraccion": inf,
        "monto": monto,
        "fecha_infraccion": f_inf,
        "fecha_vencimiento": f_ven,
        "estado": np.where(pagada, "PAGADA", "PENDIENTE"),
        "fecha_pago": f_pago,
        "hora_infraccion": horas.values,
        "codigo_infraccion": codigo,
        "gravedad": gravedad,
        "puntos_licencia": puntos,
        "tipo_vehiculo": tipos[idx],
        "marca": np.array(marcas)[idx],
        "modelo": np.array(modelos)[idx],
        "anio_vehiculo": anios[idx],
        "color": colores[idx],
        "numero_licencia": licencias[idx],
        "departamento": np.array([GEOGRAFIA[g][0] for g in geo]),
        "provincia": np.array([GEOGRAFIA[g][1] for g in geo]),
        "distrito": np.array([GEOGRAFIA[g][2] for g in geo]),
        "direccion_infraccion": ["Av. " + c + " " + x for c, x in zip(calle, numero)],
        "latitud": np.round(np.random.uniform(-18.0, -3.5, n), 6),
        "longitud": np.round(np.random.uniform(-80.5, -70.0, n), 6),
        "unidad_fiscalizadora": np.random.choice(UNIDADES, size=n),
        "tipo_deteccion": np.random.choice(["AGENTE", "FOTOPAPELETA", "CAMARA"], size=n,
                                           p=[0.5, 0.3, 0.2]),
        "numero_papeleta": [f"P-{i:08d}" for i in ids],
        "descuento_pct": np.where(pagada, np.random.choice([0.0, 25.0, 50.0], size=n), 0.0),
        "medio_pago": np.where(pagada, np.random.choice(["EFECTIVO", "TARJETA", "TRANSFERENCIA", "APP"],
                                                        size=n), ""),
        "numero_operacion": np.where(pagada, "OP" + pd.Series(np.random.randint(
            10_000_000, 99_999_999, n)).astype(str).values, ""),
        "telefono": telefonos[idx],
        "email": emails[idx],
    })
    return df[COLUMNAS_DATOS]


def persona_demo():
    """Tres multas conocidas para el DNI 12345678 (para mostrar en la consulta)."""
    comunes = {"dni": "12345678", "nombre": "Carlos Quispe Rojas", "placa": "ABC-123",
               "tipo_vehiculo": "AUTO", "marca": "Toyota", "modelo": "Corolla", "anio_vehiculo": 2018,
               "color": "GRIS", "numero_licencia": "Q12345678", "telefono": "987654321",
               "email": "carlos.quispe@correo.pe", "departamento": "LIMA", "provincia": "LIMA",
               "distrito": "MIRAFLORES", "unidad_fiscalizadora": "UF-LIMA-01"}
    filas = [
        {"id_multa": "M-9000001", "infraccion": "Exceso de velocidad", "monto": 430.0,
         "fecha_infraccion": "2026-08-01", "fecha_vencimiento": "2026-08-31", "estado": "PENDIENTE",
         "hora_infraccion": "14:35", "codigo_infraccion": "M-27", "gravedad": "MUY GRAVE",
         "puntos_licencia": 30, "direccion_infraccion": "Av. Arequipa 1520",
         "tipo_deteccion": "CAMARA", "numero_papeleta": "P-09000001"},
        {"id_multa": "M-9000002", "infraccion": "Cruzar la luz roja", "monto": 645.0,
         "fecha_infraccion": "2026-09-10", "fecha_vencimiento": "2026-10-10", "estado": "PENDIENTE",
         "hora_infraccion": "08:10", "codigo_infraccion": "M-26", "gravedad": "MUY GRAVE",
         "puntos_licencia": 50, "direccion_infraccion": "Av. Javier Prado 2300",
         "tipo_deteccion": "FOTOPAPELETA", "numero_papeleta": "P-09000002"},
        {"id_multa": "M-9000003", "infraccion": "Estacionar en zona prohibida", "monto": 215.0,
         "fecha_infraccion": "2026-03-05", "fecha_vencimiento": "2026-04-04", "estado": "PAGADA",
         "fecha_pago": "2026-04-01", "hora_infraccion": "19:45", "codigo_infraccion": "L-04",
         "gravedad": "LEVE", "puntos_licencia": 0, "direccion_infraccion": "Av. Larco 640",
         "tipo_deteccion": "AGENTE", "numero_papeleta": "P-09000003", "descuento_pct": 0.0,
         "medio_pago": "TARJETA", "numero_operacion": "OP55667788"},
    ]
    return pd.DataFrame([{**comunes, **f} for f in filas]).reindex(columns=COLUMNAS_DATOS)


def con_errores(df, ids_existentes, tasa=0.015, repetida=False):
    """Introduce errores a propósito (~tasa de las filas) para mostrar cómo se rechazan."""
    d = df.astype(object).copy()
    n = len(d)
    k = max(1, int(n * tasa))
    pos = d.index[np.random.choice(n, size=k, replace=False)]

    errores = [
        ("dni", lambda s: [str(x)[:6] for x in s]),            # DNI incompleto
        ("placa", lambda s: "12"),                              # placa inválida
        ("monto", lambda s: "-50"),                             # monto negativo
        ("estado", lambda s: "DEBE"),                           # estado inválido
        ("fecha_vencimiento", lambda s: "2020-01-01"),          # vence antes de la infracción
        ("nombre", lambda s: ""),                               # nombre vacío
        ("monto", lambda s: "abc"),                             # monto no numérico
        ("id_multa", lambda s: [random.choice(ids_existentes) for _ in s] if ids_existentes else s),
        ("email", lambda s: "correo-sin-arroba"),               # email inválido
        ("latitud", lambda s: "200"),                           # fuera de rango
        ("anio_vehiculo", lambda s: "1850"),                    # año imposible
        ("hora_infraccion", lambda s: "25:99"),                 # hora inválida
        ("telefono", lambda s: "123"),                          # teléfono incompleto
        ("gravedad", lambda s: "EXTREMA"),                      # valor fuera de la lista
    ]
    tipo = np.arange(len(pos)) % len(errores)
    for t, (columna, fn) in enumerate(errores):
        sel = pos[tipo == t]
        if len(sel):
            d.loc[sel, columna] = fn(d.loc[sel, columna])
    if repetida:  # una fila repetida dentro del mismo archivo
        d = pd.concat([d, d.iloc[[5]]], ignore_index=True)
    return d


def escribir_excel(ruta, filas, ids_existentes, bloque=50_000, inicio=1_000_001):
    """Escribe un Excel grande por bloques, sin llenar la memoria."""
    import xlsxwriter
    if filas > 1_048_575:
        raise SystemExit("Excel admite como máximo 1.048.575 filas de datos por hoja.")
    wb = xlsxwriter.Workbook(ruta, {"constant_memory": True})
    ws = wb.add_worksheet("multas")
    ws.write_row(0, 0, COLUMNAS_DATOS)
    fila, t0 = 1, time.time()
    while fila - 1 < filas:
        n = min(bloque, filas - (fila - 1))
        b = con_errores(generar(n, inicio + fila - 1, max(50, n // 3)), ids_existentes)
        for registro in b.values.tolist():
            ws.write_row(fila, 0, registro)
            fila += 1
        print(f"  {fila - 1:,} filas escritas ({time.time() - t0:.0f} s)", flush=True)
    wb.close()


def escribir_csv(ruta, filas, ids_existentes, bloque=100_000):
    hecho = 0
    while hecho < filas:
        n = min(bloque, filas - hecho)
        b = con_errores(generar(n, 5_000_001 + hecho, max(50, n // 3)), ids_existentes)
        b.to_csv(ruta, mode="w" if hecho == 0 else "a", header=hecho == 0, index=False)
        hecho += n
        print(f"  {hecho:,} filas escritas", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", type=int, default=0, help="genera además un Excel con N filas")
    ap.add_argument("--csv", type=int, default=0, help="genera además un CSV con N filas")
    ap.add_argument("--inicio", type=int, default=1_000_001,
                    help="primer código de multa del Excel grande (usa otro número para "
                         "generar un segundo archivo con códigos distintos)")
    ap.add_argument("--semilla", type=int, default=None,
                    help="semilla para que el Excel grande tenga datos distintos")
    args = ap.parse_args()
    os.makedirs("datos_ejemplo", exist_ok=True)

    base = pd.concat([persona_demo(), generar(1997, 1, 700)], ignore_index=True)
    base.to_csv("datos_ejemplo/multas_base.csv", index=False)
    ids_base = list(base["id_multa"])

    demo = con_errores(generar(500, 100_001, 200), ids_base, tasa=0.08, repetida=True)
    demo.to_csv("datos_ejemplo/archivo_demo.csv", index=False)
    demo.to_excel("datos_ejemplo/archivo_demo.xlsx", index=False)

    if args.excel:
        sufijo = "" if args.inicio == 1_000_001 else f"_desde_{args.inicio}"
        ruta = f"datos_ejemplo/multas_excel_{args.excel}{sufijo}.xlsx"
        if args.semilla is not None:
            random.seed(args.semilla)
            np.random.seed(args.semilla)
        print(f"Generando {ruta} (puede tardar unos minutos)...")
        escribir_excel(ruta, args.excel, ids_base, inicio=args.inicio)
    if args.csv:
        ruta = f"datos_ejemplo/multas_grande_{args.csv}.csv"
        print(f"Generando {ruta}...")
        escribir_csv(ruta, args.csv, ids_base)

    print("Listo. Archivos creados en la carpeta datos_ejemplo")


if __name__ == "__main__":
    main()
