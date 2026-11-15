# Prueba de concepto - Plataforma de multas vehiculares

## Inicio rápido (para probarla, sin nube ni credenciales)

Requisitos: Python 3.10 o superior.

    git clone <URL-DEL-REPOSITORIO>
    cd <carpeta-del-repositorio>
    pip install -r requirements.txt
    streamlit run app.py

Se abre en http://localhost:8501 en modo local (base SQLite, no necesita internet).

Para probarla: pantalla "2. Carga de archivo" > subir `datos_ejemplo/multas_base.csv`;
luego `datos_ejemplo/archivo_demo.xlsx` (trae errores a propósito); luego pantalla
"3. Consulta por DNI" con el DNI `12345678`.

Prueba de volumen (Excel de 500.000 filas x 34 campos, ~100 MB, no incluido en el repositorio):

    python generar_datos.py --excel 500000

El modo nube (Google BigQuery) es opcional y requiere una cuenta de Google Cloud:
ver la Parte B más abajo. Los datos del repositorio son ficticios.

---

# Prueba de concepto - Plataforma de multas vehiculares

Aplicación web con tres pantallas que demuestra la idea de la solución: datos de
distintas fuentes (formulario y archivos) que se validan, se centralizan y se
consultan en un solo lugar.

| Pantalla | Qué hace |
|---|---|
| 1. Registro de multas | Formulario que reemplaza al Excel. Valida cada dato antes de guardar. |
| 2. Carga de archivo | Sube un CSV o Excel y lo procesa en vivo: revisa la estructura, valida fila por fila, separa las filas con error (con su motivo) y carga solo las correctas. |
| 3. Consulta por DNI | Se ingresa solo el DNI. Muestra las multas de la persona, los días de retraso, la mora y la deuda total (calculada a la fecha de hoy), con la hora de la última actualización. |

Cada multa tiene **34 campos**: 9 obligatorios (código, DNI, nombre, placa, infracción,
monto, fechas y estado), la fecha de pago y 24 adicionales (vehículo, lugar, detección,
pago y contacto). La lista completa está en `logic.py`.

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `app.py` | Las tres pantallas. |
| `logic.py` | Las reglas: los 34 campos, la validación de filas y el cálculo de la mora. |
| `db.py` | Dónde se guardan los datos: base local (para probar) o BigQuery (nube). |
| `generar_datos.py` | Crea datos ficticios de ejemplo, incluidos archivos grandes. |
| `datos_ejemplo/` | Archivos de ejemplo ya generados. |
| `.streamlit/config.toml` | Configuración: permite subir archivos de hasta 1 GB. |
| `requirements.txt` | Librerías que necesita. |

## Parte A: ejecutarla en tu computadora (sin nube)

1. Instala Python 3.10 o superior desde python.org (en Windows, marca "Add Python to PATH").
2. Abre la carpeta en VS Code y abre una terminal (menú Terminal > Nueva terminal).
3. Instala las librerías (solo la primera vez, o cuando cambie `requirements.txt`):

       pip install -r requirements.txt

4. Inicia la aplicación:

       streamlit run app.py

   Se abre sola en el navegador (http://localhost:8501). Para cerrarla: Ctrl + C en la terminal.

Si ya habías usado una versión anterior, no pierdes nada: la base local `multas_local.db`
se actualiza sola con los campos nuevos. Si prefieres empezar de cero, cierra la app y
borra ese archivo.

### Recorrido sugerido para la demostración

1. **Pantalla 2:** sube `datos_ejemplo/multas_base.csv` y pulsa "Cargar". Son 2.000 multas correctas.
2. **Pantalla 2:** sube `datos_ejemplo/archivo_demo.xlsx` (es un Excel). Verás cuántas filas son
   correctas y cuántas se rechazan, con el motivo de cada una. Descarga el reporte de
   rechazadas y carga las correctas.
3. **Pantalla 3:** escribe el DNI `12345678` y pulsa Enter. Tiene 3 multas: 2 pendientes en mora
   y 1 pagada. Abre "Ver todos los campos de las multas" para ver los 34 campos.
4. **Pantalla 1:** registra una multa nueva con un DNI nuevo y consúltala en la pantalla 3.
   Prueba también dejar campos vacíos para ver las validaciones.

## Prueba de volumen: Excel de 500.000 filas y 34 campos

1. Genera el archivo (tarda cerca de 1 minuto y pesa unos 100 MB):

       python generar_datos.py --excel 500000

   Se crea `datos_ejemplo/multas_excel_500000.xlsx`. Tiene 500.000 filas, 34 columnas y
   aproximadamente 1,5 % de filas con errores puestos a propósito (7.500).
2. Carga primero `multas_base.csv` (paso 1 del recorrido), para que también se detecten
   los códigos de multa que ya existen en la plataforma.
3. En la pantalla 2, sube `multas_excel_500000.xlsx`. La validación tarda alrededor de
   30 segundos. Verás las 500.000 filas leídas, unas 492.500 correctas y unas 7.500
   rechazadas, con el detalle por motivo.
4. Pulsa "Cargar": la carga tarda unos segundos.
5. En la pantalla 3, consulta cualquier DNI: la respuesta es casi inmediata.

Tiempos medidos en una máquina de pruebas (pueden variar en tu computadora):
lectura y validación del Excel ≈ 30 s, carga ≈ 7 s, consulta por DNI con ~495.000 filas < 1 s.

Importante: leer un Excel de este tamaño usa bastante memoria (cerca de 3 GB). Se
recomienda una computadora con 8 GB de RAM o más y cerrar otros programas. Si la tuya
tiene menos, prueba con menos filas (por ejemplo `--excel 100000`).

También puedes generar un CSV grande: `python generar_datos.py --csv 1000000`.

## Parte B: conectarla a Google Cloud (BigQuery)

La aplicación es la misma; solo cambia dónde se guardan los datos.

1. Entra a console.cloud.google.com y crea un proyecto. Anota su **ID** (por ejemplo `mi-proyecto-123`).
2. Instala la Google Cloud CLI (gcloud) y, en la terminal, inicia sesión:

       gcloud auth application-default login
       gcloud config set project mi-proyecto-123

3. Indica que quieres usar BigQuery y vuelve a iniciar la app.

   En Windows (PowerShell):

       $env:BACKEND="bigquery"
       streamlit run app.py

   En Mac o Linux:

       export BACKEND=bigquery
       streamlit run app.py

4. La app crea sola el dataset `multas_poc` y la tabla `multas`. En el menú lateral
   debe aparecer "Almacenamiento: BigQuery (nube)". Repite el recorrido de la parte A:
   ahora los datos quedan en BigQuery.
5. Para el dashboard: en Looker Studio, crea un informe nuevo, elige el conector
   BigQuery y selecciona la tabla `multas_poc.multas`.

Notas:
- Con el modo gratuito (sandbox) de BigQuery las tablas se borran solas a los 60 días.
- Con 500.000 filas, la carga a BigQuery tarda más que en la base local, porque los datos
  viajan por internet.
- Si no puedes instalar gcloud en tu computadora, otra opción es ejecutar todo desde
  Cloud Shell (la terminal que ofrece Google Cloud dentro del navegador).

## Reglas de negocio (supuestos de la prueba)

Estos valores son supuestos y se pueden cambiar en `logic.py`:

- **Mora** = monto de la multa x 0,1 % por día x días de retraso, calculada a la fecha de hoy.
  Solo se aplica a multas PENDIENTES vencidas (la tasa está en `TASA_MORA_DIARIA`).
- **Deuda total** = monto + mora (solo multas pendientes). Las pagadas no generan deuda.
- **DNI:** 8 dígitos. **Placa:** formato ABC-123.
- **Monto:** número mayor a 0. **Estado:** PENDIENTE o PAGADA.
- **Fechas:** AAAA-MM-DD; el vencimiento no puede ser anterior a la infracción.
- **id_multa:** debe ser único; si ya existe en la plataforma o se repite en el archivo, se rechaza.
- **Campos adicionales:** son opcionales; si traen dato, se valida su formato (por ejemplo
  hora HH:MM, teléfono de 9 dígitos, correo, rangos de latitud y longitud, listas de valores).

## Limitaciones de la prueba

- La consulta es solo por DNI, sin inicio de sesión. En un sistema real, el ciudadano
  debería autenticarse para ver únicamente sus datos.
- Los datos son ficticios.
- Los pagos no se procesan: solo se muestra el estado de cada multa.
