from entrenamiento import ModeloClimaVuelos
import pandas as pd
import sys
import io

# Redirige stdout a una variable temporal para silenciar mensajes internos del modelo
class Silenciador:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = io.StringIO()
    def __exit__(self, *args):
        sys.stdout = self._original_stdout

# === Simulación 1: Clima extremo ===
clima_extremo = pd.DataFrame([{
    'temperatura': 40.0,
    'humedad': 95,
    'presion': 990,
    'visibilidad': 3,
    'viento_velocidad': 35.0,
    'nubosidad': 95,
    'precipitacion': 12.0,
    'fecha_observacion_utc': '2025-05-28 01:11',
    'fecha_observacion_peru': '2025-05-27 20:11'
}])

# === Simulación 2: Clima normal ===
clima_normal = pd.DataFrame([{
    'temperatura': 22.0,
    'humedad': 60,
    'presion': 1015,
    'visibilidad': 15,
    'viento_velocidad': 5.0,
    'nubosidad': 20,
    'precipitacion': 0.0,
    'fecha_observacion_utc': '2025-05-28 14:00',
    'fecha_observacion_peru': '2025-05-28 09:00'
}])

# Inicializar modelo
modelo = ModeloClimaVuelos()
with Silenciador():
    modelo.cargar_modelo("modelo_vuelos_clima.pkl")

def simular(df, titulo):
    with Silenciador():
        resultado = modelo.predecir(df)

    if resultado:
        pred = resultado['predicciones'][0]
        prob = resultado['probabilidades'][0]
        riesgo = "ALTO" if prob > 0.7 else "MEDIO" if prob > 0.4 else "BAJO"

        print(f"\n📌 *{titulo}*")
        print(f"- Temperatura: {df['temperatura'][0]} °C")
        print(f"- Humedad: {df['humedad'][0]} %")
        print(f"- Presión: {df['presion'][0]} hPa")
        print(f"- Visibilidad: {df['visibilidad'][0]} km")
        print(f"- Viento: {df['viento_velocidad'][0]} km/h")
        print(f"- Precipitación: {df['precipitacion'][0]} mm")
        print(f"- Nubosidad: {df['nubosidad'][0]} %")
        print(f"📅 Fecha y hora: {df['fecha_observacion_peru'][0]}")
        print(f"🔍 Probabilidad de retraso: {prob:.2%}")
        print(f"🚦 Riesgo estimado: {riesgo}")
        print(f"✅ Resultado del modelo: {'RETRASO' if pred == 1 else 'SIN RETRASO'}")
    else:
        print("❌ Error al hacer predicción.")

# Ejecutar ambas pruebas
simular(clima_extremo, "Simulación con condiciones climáticas extremas")
simular(clima_normal, "Simulación con clima normal y condiciones favorables")
