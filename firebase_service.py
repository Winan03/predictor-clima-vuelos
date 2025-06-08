import firebase_admin
from firebase_admin import credentials, db
import json
import os
from datetime import datetime
import hashlib

class FirebaseService:
    def __init__(self):
        """
        Inicializa el servicio de Firebase
        """
        self.initialized = False
        self.init_firebase()
    
    def init_firebase(self):
        """
        Inicializa Firebase Admin SDK
        """
        try:
            # Verificar si ya está inicializado
            if not firebase_admin._apps:
                # Opción 1: Usar archivo JSON de credenciales
                cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
                if cred_path and os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                else:
                    # Opción 2: Usar credenciales desde variable de entorno (JSON string)
                    cred_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
                    if cred_json:
                        cred_dict = json.loads(cred_json)
                        cred = credentials.Certificate(cred_dict)
                    else:
                        print("❌ No se encontraron credenciales de Firebase")
                        return
                
                # URL de tu base de datos de Firebase
                database_url = os.getenv('FIREBASE_DATABASE_URL', 'https://your-project-default-rtdb.firebaseio.com/')
                
                firebase_admin.initialize_app(cred, {
                    'databaseURL': database_url
                })
            
            self.initialized = True
            print("✅ Firebase inicializado correctamente")
            
        except Exception as e:
            print(f"❌ Error inicializando Firebase: {e}")
            self.initialized = False
    
    def guardar_prediccion_vuelo(self, ciudad, fecha, hora, resultado_prediccion, user_id=None):
        """
        Guarda una predicción de vuelo en Firebase, incluyendo clima de origen y destino por separado.
        """
        if not self.initialized:
            print("❌ Firebase no está inicializado")
            return False

        try:
            ref = db.reference()
            timestamp = int(datetime.now().timestamp() * 1000)

            clima_destino = resultado_prediccion.get('datos_clima_destino', {})
            clima_origen = resultado_prediccion.get('datos_clima_origen', {})

            vuelo_data = {
                "probabilidad": resultado_prediccion.get('probabilidad_retraso', 0),
                "riesgo": resultado_prediccion.get('riesgo', 'bajo'),
                "status": self._get_status_from_riesgo(resultado_prediccion.get('riesgo', 'bajo')),
                "clima_origen": clima_origen,
                "clima_destino": clima_destino,
                "recomendaciones": resultado_prediccion.get('recomendaciones', []),
                "generado_por": "modeloIA",
                "timestamp": timestamp
            }

            vuelos_ref = ref.child('vuelos_predichos').child(ciudad).child(fecha).child(hora)
            vuelos_ref.set(vuelo_data)

            if user_id:
                flight_id = self._generate_flight_id(ciudad, fecha, hora, user_id)
                clima_origen = resultado_prediccion.get('datos_clima_origen', {})
                clima_destino = resultado_prediccion.get('datos_clima_destino', {})
                pasajeros = resultado_prediccion.get('pasajeros', 120)
                costo = resultado_prediccion.get('costo', 100.0)

                user_flight_data = {
                    "destination": ciudad,
                    "date": fecha,
                    "time": hora,
                    "probabilidad": resultado_prediccion.get('probabilidad_retraso', 0),
                    "riesgo": resultado_prediccion.get('riesgo', 'bajo'),
                    "status": self._get_status_from_riesgo(resultado_prediccion.get('riesgo', 'bajo')),
                    "origin": resultado_prediccion.get('origen', 'Desconocido'),
                    "saved_at": datetime.now().isoformat(),
                    "pasajeros": pasajeros,
                    "costo": costo,
                    "clima_origen": {
                        "temperatura": clima_origen.get("temperatura", 0),
                        "precipitacion": clima_origen.get("precipitacion", 0),
                        "viento_velocidad": clima_origen.get("viento_velocidad", 0),
                        "presion": clima_origen.get("presion", 1013),
                        "visibilidad": clima_origen.get("visibilidad", 10),
                        "nubosidad": clima_origen.get("nubosidad", 0)
                    },
                    "clima_destino": {
                        "temperatura": clima_destino.get("temperatura", 0),
                        "precipitacion": clima_destino.get("precipitacion", 0),
                        "viento_velocidad": clima_destino.get("viento_velocidad", 0),
                        "presion": clima_destino.get("presion", 1013),
                        "visibilidad": clima_destino.get("visibilidad", 10),
                        "nubosidad": clima_destino.get("nubosidad", 0)
                    },
                    "modificado_manualmente": False
                }

                user_ref = ref.child('users').child(user_id.replace('.', '_').replace('@', '_')).child('flights').child(flight_id)
                user_ref.set(user_flight_data)


            print(f"✅ Predicción guardada: {ciudad} - {fecha} {hora}")
            return True

        except Exception as e:
            print(f"❌ Error guardando predicción: {e}")
            return False
    
    def actualizar_estadisticas(self, predicciones_hoy, precision_modelo, retrasos_evitados, ahorro_estimado):
        """
        Actualiza las estadísticas globales
        
        Args:
            predicciones_hoy (int): Número de predicciones del día
            precision_modelo (float): Precisión del modelo
            retrasos_evitados (int): Retrasos evitados
            ahorro_estimado (float): Ahorro estimado en USD
        
        Returns:
            bool: True si se actualizó correctamente
        """
        if not self.initialized:
            return False
        
        try:
            ref = db.reference('estadisticas')
            estadisticas_data = {
                "predicciones_hoy": predicciones_hoy,
                "modelo_precision": f"{precision_modelo:.1f}%",
                "retrasos_ev": retrasos_evitados,
                "ahorro_estimado_usd": int(ahorro_estimado)
            }
            
            ref.set(estadisticas_data)
            print("✅ Estadísticas actualizadas")
            return True
            
        except Exception as e:
            print(f"❌ Error actualizando estadísticas: {e}")
            return False
    
    def obtener_predicciones_ciudad(self, ciudad, fecha=None):
        """
        Obtiene predicciones de una ciudad específica
        
        Args:
            ciudad (str): Nombre de la ciudad
            fecha (str): Fecha específica (opcional)
        
        Returns:
            dict: Predicciones encontradas
        """
        if not self.initialized:
            return {}
        
        try:
            if fecha:
                ref = db.reference(f'vuelos_predichos/{ciudad}/{fecha}')
            else:
                ref = db.reference(f'vuelos_predichos/{ciudad}')
            
            return ref.get() or {}
            
        except Exception as e:
            print(f"❌ Error obteniendo predicciones: {e}")
            return {}
    
    def obtener_estadisticas(self):
        """
        Obtiene las estadísticas actuales
        
        Returns:
            dict: Estadísticas actuales
        """
        if not self.initialized:
            return {}
        
        try:
            ref = db.reference('estadisticas')
            return ref.get() or {}
            
        except Exception as e:
            print(f"❌ Error obteniendo estadísticas: {e}")
            return {}
    
    def _get_status_from_riesgo(self, riesgo):
        """
        Convierte el nivel de riesgo a status
        """
        mapping = {
            'alto': 'highRisk',
            'medio': 'mediumRisk',
            'bajo': 'lowRisk'
        }
        return mapping.get(riesgo, 'lowRisk')
    
    def _generate_flight_id(self, ciudad, fecha, hora, user_id):
        """
        Genera un ID único para el vuelo
        """
        data = f"{ciudad}-{fecha}-{hora}-{user_id}"
        return hashlib.md5(data.encode()).hexdigest()[:12]
    
    def test_connection(self):
        """
        Prueba la conexión a Firebase
        
        Returns:
            bool: True si la conexión es exitosa
        """
        if not self.initialized:
            return False
        
        try:
            ref = db.reference('test')
            ref.set({'timestamp': datetime.now().isoformat()})
            test_data = ref.get()
            ref.delete()  # Limpiar el test
            return test_data is not None
            
        except Exception as e:
            print(f"❌ Error en test de conexión: {e}")
            return False