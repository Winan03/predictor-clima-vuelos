import os
import json
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import joblib
import firebase_admin
from firebase_admin import credentials, db
from procesamiento import preparar_features
from entrenamiento import ModeloClimaVuelos

# Cargar variables .env
load_dotenv()

# Inicializar Firebase
cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
db_url = os.getenv('FIREBASE_DATABASE_URL')

cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred, {'databaseURL': db_url})

# Cargar modelo
data = joblib.load("modelo_vuelos_clima.pkl")
modelo = ModeloClimaVuelos()
modelo.modelo = data["modelo"]
modelo.scaler = data["scaler"]
modelo.label_encoders = data.get("label_encoders", {})
modelo.columnas_esperadas = list(modelo.scaler.feature_names_in_)

# Contadores para estadísticas
retrasos_evitados = 0
ahorro_total = 0
vuelos_actualizados = 0

# Leer usuarios y vuelos
ref = db.reference("users")
usuarios = ref.get()

for uid, udata in usuarios.items():
    flights = udata.get("flights", {})
    for flight_id, fdata in flights.items():
        # Solo procesar si fue modificado manualmente
        if not fdata.get("modificado_manualmente", False):
            continue

        factores = fdata.get("factores")
        if not factores:
            continue  # Si no hay factores, se salta

        try:
            dt = datetime.strptime(fdata["date"], "%Y-%m-%d")
            hora = int(fdata["time"].split(":")[0])
        except Exception as e:
            print(f"❌ Error de formato en vuelo {flight_id}: {e}")
            continue

        datos = {
            'temperatura': factores.get('temperatura', 22),
            'precipitacion': factores.get('precipitacion', 0),
            'viento_velocidad': factores.get('viento_velocidad', 10),
            'presion': factores.get('presion', 1013),
            'visibilidad': factores.get('visibilidad', 10),
            'nubosidad': factores.get('nubosidad', 0),
            'hora': hora,
            'dia_semana': dt.weekday(),
            'mes': dt.month,
            'es_fin_semana': int(dt.weekday() >= 5),
            'lluvia_fuerte': int(factores.get('precipitacion', 0) > 2.0),
            'viento_fuerte': int(factores.get('viento_velocidad', 0) > 15)
        }

        df = pd.DataFrame([datos])
        X, _, _, _, _ = preparar_features(df, scaler=modelo.scaler)

        try:
            probas = modelo.modelo.predict_proba(X)[0]
            nueva_prob = float(probas[1]) * 100

            if nueva_prob > 60:
                nuevo_riesgo = "alto"
                nuevo_status = "highRisk"
            elif nueva_prob > 30:
                nuevo_riesgo = "medio"
                nuevo_status = "mediumRisk"
            else:
                nuevo_riesgo = "bajo"
                nuevo_status = "lowRisk"

            # Comparar con valores anteriores
            anterior_riesgo = fdata.get("riesgo", "bajo")
            anterior_prob = fdata.get("probabilidad", 0)
            if nuevo_riesgo != anterior_riesgo or abs(anterior_prob - nueva_prob) >= 1.0:
                print(f"🔄 Actualizando {flight_id} ({uid}): {anterior_riesgo} → {nuevo_riesgo}")

                # Actualizar en Firebase
                ref.child(uid).child("flights").child(flight_id).update({
                    "probabilidad": nueva_prob,
                    "riesgo": nuevo_riesgo,
                    "status": nuevo_status
                })

                vuelos_actualizados += 1

                if nuevo_riesgo in ["medio", "alto"]:
                    retrasos_evitados += 1
                    costo = fdata.get("costo", 100)
                    pasajeros = fdata.get("pasajeros", 120)
                    ahorro_total += int(costo * pasajeros)

        except Exception as e:
            print(f"❌ Error procesando {flight_id}: {e}")

# Actualizar estadísticas generales
try:
    estadisticas_ref = db.reference("estadisticas")
    actuales = estadisticas_ref.get() or {}
    actuales["retrasos_ev"] = actuales.get("retrasos_ev", 0) + retrasos_evitados
    actuales["ahorro_estimado_usd"] = actuales.get("ahorro_estimado_usd", 0) + ahorro_total
    estadisticas_ref.set(actuales)
    print(f"\n✅ Estadísticas actualizadas: +{retrasos_evitados} retrasos evitados, +${ahorro_total} USD")
except Exception as e:
    print(f"❌ Error al actualizar estadísticas: {e}")

print(f"🔎 Total vuelos actualizados: {vuelos_actualizados}")
