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
        self.db = db 
    
    def init_firebase(self):
        """
        Inicializa Firebase Admin SDK para Render y entorno local
        """
        try:
            if not firebase_admin._apps:
                cred = None

                # 🔒 1. Render: si tienes FIREBASE_PROJECT_ID y JSON
                if os.getenv('FIREBASE_PROJECT_ID') and os.getenv('FIREBASE_PRIVATE_KEY'):
                    cred_data = {
                        "type": "service_account",
                        "project_id": os.getenv("FIREBASE_PROJECT_ID"),
                        "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
                        "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
                        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                        "client_id": os.getenv("FIREBASE_CLIENT_ID"),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL")
                    }
                    cred = credentials.Certificate(cred_data)
                    print("🌐 Usando credenciales desde variables de entorno (Render)")

                # 💻 2. Local: si existe un path a JSON
                elif os.getenv('FIREBASE_CREDENTIALS_PATH'):
                    cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
                    if os.path.exists(cred_path):
                        cred = credentials.Certificate(cred_path)
                        print("💻 Usando credenciales desde archivo local")

                if not cred:
                    print("❌ No se encontraron credenciales de Firebase")
                    return

                firebase_admin.initialize_app(cred, {
                    'databaseURL': os.getenv('FIREBASE_DATABASE_URL')
                })

            self.initialized = True
            print("✅ Firebase inicializado correctamente")

        except Exception as e:
            print(f"❌ Error inicializando Firebase: {e}")
            self.initialized = False

    
    def guardar_prediccion_vuelo(self, ciudad, fecha, hora, resultado_prediccion, user_id=None):
        """
        Guarda una predicción de vuelo en Firebase
        """
        if not self.initialized:
            print("❌ Firebase no está inicializado")
            return False

        try:
            ref = db.reference()
            timestamp = int(datetime.now().timestamp() * 1000)

            clima_destino = resultado_prediccion.get('datos_clima_destino', {})
            clima_origen = resultado_prediccion.get('datos_clima_origen', {})

            # Guardar predicción general
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

            # Guardar historial por usuario si aplica
            if user_id:
                flight_id = self._generate_flight_id(ciudad, fecha, hora, user_id)
                
                # IMPORTANTE: Usar la misma sanitización que en app.py
                sanitized_user_id = user_id.replace('.', '_').replace('@', '_')
                user_ref = ref.child('users').child(sanitized_user_id).child('flights').child(flight_id)

                user_flight_data = {
                    "destination": ciudad,
                    "origin": resultado_prediccion.get('origen', 'Lima'),  # Valor por defecto
                    "date": fecha,
                    "time": hora,
                    "pasajeros": resultado_prediccion.get('pasajeros', 120),
                    "costo": resultado_prediccion.get('costo', 100.0),
                    "probabilidad": resultado_prediccion.get('probabilidad_retraso', 0),
                    "riesgo": resultado_prediccion.get('riesgo', 'bajo'),
                    "status": self._get_status_from_riesgo(resultado_prediccion.get('riesgo', 'bajo')),
                    "saved_at": datetime.now().isoformat(),
                    "timestamp": timestamp,
                    "modificado_manualmente": False,
                    "clima_origen": clima_origen,
                    "clima_destino": clima_destino,
                    "recomendaciones": resultado_prediccion.get('recomendaciones', []),
                    "confianza": resultado_prediccion.get('confianza', 85.0),
                    "numero_vuelo": resultado_prediccion.get('numero_vuelo', f'FLY-{flight_id[:6].upper()}'),
                    "fecha_hora": f"{fecha} {hora}"
                }

                user_ref.set(user_flight_data)
                print(f"✅ Datos guardados para usuario: {sanitized_user_id}")

            print(f"✅ Predicción guardada: {ciudad} - {fecha} {hora}")
            return True

        except Exception as e:
            print(f"❌ Error guardando predicción: {e}")
            import traceback
            traceback.print_exc()
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
        
    def obtener_ciudades_activas(self):
        """
        Extrae ciudades de origen y destino de los vuelos en los tickets confirmados.
        Retorna una lista única y ordenada de ciudades activas.
        """
        if not self.initialized:
            return []

        try:
            ref = db.reference('tickets')
            tickets = ref.get()

            ciudades = set()

            if tickets:
                for ticket_id, ticket_data in tickets.items():
                    if ticket_data.get('estado', '').lower() == 'confirmado':
                        vuelo = ticket_data.get('vuelo', {})
                        origen = vuelo.get('origen', '').strip().lower()
                        destino = vuelo.get('destino', '').strip().lower()

                        if origen:
                            ciudades.add(origen)
                        if destino:
                            ciudades.add(destino)

            return sorted(ciudades)

        except Exception as e:
            print(f"❌ Error al obtener ciudades activas: {e}")
            return []

    