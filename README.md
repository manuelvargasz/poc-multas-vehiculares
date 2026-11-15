# Prueba de concepto: plataforma de multas vehiculares

App web con 3 pantallas (registro, carga de archivos y consulta por DNI con mora).
Datos ficticios. Requiere Python 3.10 o superior.

## Ejecutar (modo local)

    pip install -r requirements.txt
    streamlit run app.py

Se abre en http://localhost:8501

## Probar

1. Pantalla "2. Carga de archivo": subir datos_ejemplo/multas_base.csv y luego datos_ejemplo/archivo_demo.xlsx (trae errores a propósito).
2. Pantalla "3. Consulta por DNI": consultar 12345678.
3. Prueba de volumen: python generar_datos.py --excel 500000 (Excel de 500.000 filas x 34 campos).
