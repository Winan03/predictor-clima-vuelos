# Importaciones existentes + nuevas
from flask import Flask, render_template, request, jsonify, session
import joblib
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import os
from procesamiento import procesar_datos_clima, preparar_features, obtener_datos_clima_reales
from entrenamiento.entrenamiento import ModeloClimaVuelos
from service.firebase_service import FirebaseService 
from service.explicacion_service import ExplicadorPredicciones, generar_explicacion_simple
from firebase_admin import db 

app = Flask(__name__)

# Habilita CORS para todos los dominios
from flask_cors import CORS
CORS(app)

contador_predicciones = 0
retrasos_evitados = 0
ahorro_estimado = 0

# Inicializar Firebase Service
firebase_service = FirebaseService()  

explicador = ExplicadorPredicciones()

# Agregamos el servicio de envio de emails por prediccion realizada
from service.email_service import EmailService

# Inicializar el servicio de email después de FirebaseService
email_service = EmailService()

# Cargar modelo entrenado desde S3 o local
def cargar_modelo():
    """
    CORREGIDA: Carga modelo y valida que las columnas sean consistentes
    """
    try:
        ruta = os.getenv('MODELO_URL', 'modelo_vuelos_clima.pkl')

        if ruta.startswith('http'):
            response = requests.get(ruta)
            with open('modelo_temp.pkl', 'wb') as f:
                f.write(response.content)
            data = joblib.load('modelo_temp.pkl')
            os.remove('modelo_temp.pkl')
        else:
            data = joblib.load(ruta)

        modelo = ModeloClimaVuelos()
        modelo.modelo = data['modelo']
        modelo.scaler = data['scaler']
        modelo.label_encoders = data.get('label_encoders', {})
        modelo.metricas = data.get('metricas', {})
        
        # Obtener las columnas que espera el modelo
        if hasattr(modelo.scaler, 'feature_names_in_'):
            modelo.columnas_esperadas = list(modelo.scaler.feature_names_in_)
            print(f"Modelo cargado. Columnas esperadas: {modelo.columnas_esperadas}")
        else:
            print("Advertencia: No se pudieron obtener las columnas esperadas del modelo")
            modelo.columnas_esperadas = None
        
        return modelo

    except Exception as e:
        print(f"Error cargando modelo: {e}")
        return None

# Cargar modelo al iniciar la aplicación
modelo = cargar_modelo()

@app.route('/')
def index():
    return render_template('index.html')

# ============= NUEVA RUTA PARA EL HISTORIAL =============
@app.route('/historial')
def historial_predicciones():
    return render_template('historial.html')

@app.route('/historial-predicciones/<user_id>', methods=['GET'])
def obtener_historial_predicciones(user_id):
    try:
        print(f"🔥 UID recibido en ruta: {user_id}")
        
        # CORREGIDO: Usar _ en lugar de *
        sanitized_user_id = user_id.replace('.', '_').replace('@', '_')
        print(f"🔐 UID sanitizado: {sanitized_user_id}")
        
        predicciones_ref = db.reference(f'users/{sanitized_user_id}/flights')
        todas_predicciones = predicciones_ref.get()
        
        print(f"📦 Predicciones crudas:", todas_predicciones)
        
        predicciones_usuario = []
        
        if todas_predicciones:
            for flight_id, pred in todas_predicciones.items():
                # Verificar que pred no sea None
                if pred is None:
                    continue
                    
                # Obtener timestamp correcto
                timestamp = pred.get('timestamp')
                if timestamp:
                    try:
                        # Si es timestamp en milliseconds
                        if timestamp > 1e12:  # Mayor que 1 billion = milliseconds
                            fecha_obj = datetime.fromtimestamp(timestamp/1000)
                        else:  # Seconds
                            fecha_obj = datetime.fromtimestamp(timestamp)
                        timestamp_str = fecha_obj.isoformat()
                    except:
                        timestamp_str = pred.get('saved_at', datetime.now().isoformat())
                else:
                    timestamp_str = pred.get('saved_at', datetime.now().isoformat())
                
                predicciones_usuario.append({
                    'id': flight_id,
                    'origen': pred.get('origin', pred.get('origen', 'N/A')),
                    'ciudad': pred.get('destination', pred.get('destino', 'N/A')),
                    'fecha_hora': f"{pred.get('date', '')} {pred.get('time', '')}".strip(),
                    'pasajeros': pred.get('pasajeros', 0),
                    'costo': pred.get('costo', 0),
                    'probabilidad_retraso': pred.get('probabilidad', 0),
                    'probabilidad_puntual': 100 - pred.get('probabilidad', 0),
                    'confianza': pred.get('confianza', 100),
                    'riesgo': pred.get('riesgo', 'bajo'),
                    'status': pred.get('status', 'lowRisk'),
                    'numero_vuelo': pred.get('numero_vuelo', f"FLY-{flight_id[:6]}"),
                    
                    # Datos del clima - ajustados a tu estructura
                    'datos_clima_origen': pred.get('clima_origen', {}),
                    'datos_clima_destino': pred.get('clima_destino', {}),
                    # También incluir para compatibilidad con el modal
                    'datos_clima': pred.get('clima_destino', {}),
                    
                    'recomendaciones': pred.get('recomendaciones', [
                        "Verificar condiciones meteorológicas antes del vuelo",
                        "Llegar al aeropuerto con tiempo suficiente"
                    ]),
                    'timestamp': timestamp_str,
                    'factores_riesgo': pred.get('factores_riesgo', [])
                })
        
        # Ordenar por timestamp descendente
        predicciones_usuario.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        print(f"✅ Enviando {len(predicciones_usuario)} predicciones al frontend")
        
        return jsonify({
            'success': True,
            'predicciones': predicciones_usuario,
            'total': len(predicciones_usuario)
        })
        
    except Exception as e:
        print(f"❌ Error obteniendo historial: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e),
            'predicciones': []
        }), 500

# ========================================================

@app.route('/predecir', methods=['POST'])
def predecir_retraso():
    """
    Endpoint de predicción que guarda en Firebase, considera clima de origen y destino por separado,
    Y AHORA TAMBIÉN ENVÍA NOTIFICACIONES POR EMAIL A LOS PASAJEROS + EXPLICACIONES
    """
    try:
        data = request.json

        ciudad = data.get('ciudad')
        origen = data.get('origen')
        fecha = data.get('fecha')
        hora = data.get('hora')
        pasajeros = data.get('pasajeros', 120)
        costo = data.get('costo', 100.0)
        user_id = data.get('user_id')
        numero_vuelo = data.get('numero_vuelo')

        if not ciudad or not origen or not fecha or not hora:
            return jsonify({'error': 'Faltan datos requeridos: ciudad, origen, fecha, hora'}), 400

        # Obtener datos climáticos
        clima_destino = obtener_datos_clima_reales(ciudad, fecha, hora)
        clima_origen = obtener_datos_clima_reales(origen, fecha, hora)

        # Guardar ambos por separado
        datos_clima_origen = clima_origen
        datos_clima_destino = clima_destino

        # Fusionar para predicción
        datos_clima = {
            "temperatura": round((clima_origen["temperatura"] + clima_destino["temperatura"]) / 2, 1),
            "precipitacion": round(clima_origen["precipitacion"] + clima_destino["precipitacion"], 1),
            "viento_velocidad": max(clima_origen["viento_velocidad"], clima_destino["viento_velocidad"]),
            "presion": round((clima_origen["presion"] + clima_destino["presion"]) / 2, 1),
            "visibilidad": min(clima_origen.get("visibilidad", 10), clima_destino.get("visibilidad", 10)),
            "nubosidad": max(clima_origen.get("nubosidad", 0), clima_destino.get("nubosidad", 0))
        }

        dt = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")

        if modelo:
            try:
                columnas_modelo = modelo.columnas_esperadas if hasattr(modelo, 'columnas_esperadas') else [
                    'temperatura', 'precipitacion', 'viento_velocidad', 'presion',
                    'hora', 'dia_semana', 'mes', 'es_fin_semana',
                    'lluvia_fuerte', 'viento_fuerte'
                ]

                data_dict = {}
                for col in columnas_modelo:
                    if col == 'temperatura':
                        data_dict[col] = datos_clima.get('temperatura', 22.0)
                    elif col == 'precipitacion':
                        data_dict[col] = datos_clima.get('precipitacion', 0.0)
                    elif col == 'viento_velocidad':
                        data_dict[col] = datos_clima.get('viento_velocidad', 10.0)
                    elif col == 'presion':
                        data_dict[col] = datos_clima.get('presion', 1013.25)
                    elif col == 'hora':
                        data_dict[col] = dt.hour
                    elif col == 'dia_semana':
                        data_dict[col] = dt.weekday()
                    elif col == 'mes':
                        data_dict[col] = dt.month
                    elif col == 'es_fin_semana':
                        data_dict[col] = int(dt.weekday() >= 5)
                    elif col == 'lluvia_fuerte':
                        data_dict[col] = int(datos_clima.get('precipitacion', 0) > 5)
                    elif col == 'viento_fuerte':
                        data_dict[col] = int(datos_clima.get('viento_velocidad', 0) > 20)
                    else:
                        data_dict[col] = 0

                df_nuevo = pd.DataFrame([data_dict])

                X_nuevo, _, _, _, _ = preparar_features(
                    df_nuevo,
                    columnas_target=[],
                    scaler=modelo.scaler,
                    label_encoders=modelo.label_encoders
                )

                if X_nuevo.isnull().any().any() or np.isinf(X_nuevo.values).any():
                    X_nuevo = X_nuevo.replace([np.inf, -np.inf], 0).fillna(0)

                if X_nuevo.empty:
                    return jsonify({'error': 'Error preparando features para predicción'}), 500

                prediccion = modelo.modelo.predict(X_nuevo)[0]

                try:
                    probabilidad = modelo.modelo.predict_proba(X_nuevo)[0]
                    prob_retraso = float(probabilidad[1]) * 100
                except Exception:
                    probabilidad = [100.0, 0.0]
                    prob_retraso = 0.0

                riesgo = "alto" if prob_retraso > 60 else "medio" if prob_retraso > 30 else "bajo"
                confianza = max(probabilidad) * 100

                # Preparar resultado base
                resultado = {
                    'prediccion': bool(prediccion),
                    'probabilidad_retraso': prob_retraso,
                    'probabilidad_puntual': float(probabilidad[0]) * 100,
                    'confianza': float(confianza),
                    'riesgo': riesgo,
                    'factores_riesgo': analizar_factores_riesgo(datos_clima, dt),
                    'recomendaciones': generar_recomendaciones(datos_clima, prediccion),
                    'datos_clima': datos_clima,
                    'datos_clima_origen': datos_clima_origen,
                    'datos_clima_destino': datos_clima_destino,
                    'fecha_hora': f"{fecha} {hora}",
                    'origen': origen,
                    'ciudad': ciudad,
                    'pasajeros': pasajeros,
                    'costo': costo,
                    'numero_vuelo': numero_vuelo,
                    'timestamp': datetime.now().isoformat()
                }

                # ⭐ GENERAR EXPLICACIÓN DE LA PREDICCIÓN
                try:
                    print("🧠 Generando explicación de la predicción...")
                    
                    datos_para_explicacion = {
                        'datos_clima_origen': datos_clima_origen,
                        'datos_clima_destino': datos_clima_destino,
                        'datos_clima': datos_clima  # clima combinado
                    }
                    
                    datos_vuelo_para_explicacion = {
                        'origen': origen,
                        'ciudad': ciudad,
                        'fecha': fecha,
                        'hora': hora,
                        'pasajeros': pasajeros,
                        'costo': costo,
                        'numero_vuelo': numero_vuelo
                    }
                    
                    explicacion_completa = explicador.explicar_prediccion(
                        datos_para_explicacion, 
                        prob_retraso, 
                        datos_vuelo_para_explicacion
                    )
                    
                    explicacion_simple = generar_explicacion_simple(explicacion_completa)
                    
                    # ✅ AGREGAR EXPLICACIONES AL RESULTADO
                    resultado['explicacion'] = explicacion_completa
                    resultado['explicacion_simple'] = explicacion_simple
                    resultado['tiene_explicacion'] = True
                    
                    print(f"✅ Explicación generada exitosamente")
                    print(f"📋 Explicación simple: {explicacion_simple.get('mensaje_principal', 'N/A')}")
                    
                except Exception as e:
                    print(f"⚠️ Error generando explicación: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    # Si falla la explicación, agregar una versión básica
                    resultado['explicacion'] = None
                    resultado['explicacion_simple'] = {
                        'mensaje_principal': f"Predicción realizada - Riesgo {riesgo.upper()}",
                        'factores_clave': ['Análisis basado en condiciones meteorológicas'],
                        'recomendacion_principal': 'Verifique el estado de su vuelo antes de partir'
                    }
                    resultado['tiene_explicacion'] = False
                    resultado['error_explicacion'] = str(e)

                # Actualizar estadísticas globales
                global contador_predicciones, retrasos_evitados, ahorro_estimado
                contador_predicciones += 1

                if prediccion:
                    retrasos_evitados += 1
                    ahorro_estimado += round(pasajeros * costo)
                    resultado['ahorro_estimado'] = round(pasajeros * costo)
                else:
                    resultado['ahorro_estimado'] = 0

                # ⭐ GUARDAR EN FIREBASE PRIMERO
                prediccion_id = None
                try:
                    prediccion_id = firebase_service.guardar_prediccion_vuelo(
                        ciudad=ciudad,
                        fecha=fecha,
                        hora=hora,
                        resultado_prediccion=resultado,
                        user_id=user_id
                    )

                    firebase_service.actualizar_estadisticas(
                        predicciones_hoy=contador_predicciones,
                        precision_modelo=98.6,
                        retrasos_evitados=retrasos_evitados,
                        ahorro_estimado=ahorro_estimado
                    )

                    resultado['firebase_guardado'] = True
                    resultado['prediccion_id'] = prediccion_id
                except Exception as firebase_error:
                    print(f"⚠️ Error guardando en Firebase: {firebase_error}")
                    resultado['firebase_guardado'] = False

                # ⭐ ENVIAR NOTIFICACIONES POR EMAIL A TODOS LOS PASAJEROS
                email_resultado = None
                if numero_vuelo:
                    try:
                        print(f"📤 Preparando envío de notificaciones para vuelo {numero_vuelo}")

                        datos_para_email = resultado.copy()
                        datos_para_email['datos_clima'] = datos_clima  # Clima combinado

                        email_resultado = email_service.enviar_notificacion_vuelo(
                            codigo_vuelo=numero_vuelo,
                            prediccion_data=datos_para_email
                        )

                        print(f"📧 Resultado del envío de emails: {email_resultado}")
                        resultado['notificacion_email'] = email_resultado

                    except Exception as email_error:
                        print(f"❌ Error enviando notificaciones por email: {email_error}")
                        resultado['notificacion_email'] = {
                            'success': False,
                            'error': str(email_error)
                        }
                else:
                    resultado['notificacion_email'] = {
                        'success': False,
                        'message': f'Número de vuelo no proporcionado. No se enviaron emails.'
                    }

                # ✅ AGREGAR CAMPOS ADICIONALES PARA EL FRONTEND
                resultado['status'] = 'success'
                resultado['mostrar_explicacion'] = True  # Señal para el frontend
                
                print("🚀 Resultado final preparado para envío:")
                print(f"   - Predicción: {resultado['prediccion']}")
                print(f"   - Probabilidad retraso: {resultado['probabilidad_retraso']:.1f}%")
                print(f"   - Riesgo: {resultado['riesgo']}")
                print(f"   - Tiene explicación: {resultado.get('tiene_explicacion', False)}")

                return jsonify(resultado)

            except Exception as e:
                print(f"Error en predicción: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': f'Error en predicción: {str(e)}'}), 500

        else:
            return jsonify({'error': 'Modelo no disponible'}), 500

    except Exception as e:
        print(f"Error general en predicción: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error procesando solicitud: {str(e)}'}), 500

# ============= ENDPOINT MANUAL PARA ENVIAR NOTIFICACIONES =============
@app.route('/enviar-notificacion-vuelo', methods=['POST'])
def enviar_notificacion_manual():
    """
    Endpoint para enviar notificaciones por email de forma manual
    """
    try:
        data = request.json
        codigo_vuelo = data.get('codigo_vuelo')
        prediccion_data = data.get('prediccion_data')
        
        if not codigo_vuelo or not prediccion_data:
            return jsonify({
                'success': False,
                'error': 'Faltan datos: codigo_vuelo y prediccion_data son requeridos'
            }), 400
        
        resultado = email_service.enviar_notificacion_vuelo(codigo_vuelo, prediccion_data)
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ Error en envío manual de notificaciones: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ================================================================

def analizar_factores_riesgo(datos_clima, fecha_hora):
    """
    Analiza los factores meteorológicos que influyen en la predicción de retraso,
    utilizando los mismos umbrales que en la función generar_etiqueta_retraso().
    """
    factores = []

    # Precipitación > 2.0 mm
    if datos_clima['precipitacion'] > 2.0:
        factores.append({
            'factor': 'Lluvia significativa',
            'nivel': 'medio',
            'valor': f"{datos_clima['precipitacion']} mm",
            'descripcion': 'Puede afectar la operación en pista y visibilidad.'
        })

    # Viento > 15 km/h
    if datos_clima['viento_velocidad'] > 15:
        factores.append({
            'factor': 'Viento moderado',
            'nivel': 'medio',
            'valor': f"{datos_clima['viento_velocidad']} km/h",
            'descripcion': 'Puede generar turbulencias o demoras en el aterrizaje.'
        })

    # Temperatura < 8 °C o > 32 °C
    if datos_clima['temperatura'] < 8:
        factores.append({
            'factor': 'Temperatura baja',
            'nivel': 'bajo',
            'valor': f"{datos_clima['temperatura']}°C",
            'descripcion': 'Temperaturas bajas pueden afectar equipos en tierra.'
        })
    elif datos_clima['temperatura'] > 32:
        factores.append({
            'factor': 'Temperatura alta',
            'nivel': 'bajo',
            'valor': f"{datos_clima['temperatura']}°C",
            'descripcion': 'Altas temperaturas pueden alterar la densidad del aire.'
        })

    # Presión < 1005 hPa
    if datos_clima['presion'] < 1005:
        factores.append({
            'factor': 'Presión atmosférica baja',
            'nivel': 'bajo',
            'valor': f"{datos_clima['presion']} hPa",
            'descripcion': 'Presión baja está asociada a mal clima general.'
        })

    # Visibilidad < 10 km
    if datos_clima['visibilidad'] < 10:
        factores.append({
            'factor': 'Visibilidad reducida',
            'nivel': 'bajo',
            'valor': f"{datos_clima['visibilidad']} km",
            'descripcion': 'Puede dificultar maniobras de aterrizaje y despegue.'
        })

    # Factores temporales
    if fecha_hora.hour in [6, 7, 8, 18, 19, 20]:
        factores.append({
            'factor': 'Hora pico de operaciones',
            'nivel': 'bajo',
            'valor': f"{fecha_hora.hour}:00",
            'descripcion': 'Mayor tráfico aéreo puede causar demoras logísticas.'
        })

    if fecha_hora.weekday() >= 5:
        factores.append({
            'factor': 'Fin de semana',
            'nivel': 'bajo',
            'valor': 'Mayor tráfico de pasajeros',
            'descripcion': 'Los fines de semana suelen tener mayor congestión en aeropuertos.'
        })

    return factores

def generar_recomendaciones(datos_clima, prediccion_retraso):
    """
    Genera recomendaciones basadas en las condiciones climáticas y predicción
    
    Args:
        datos_clima (dict): Datos climáticos actuales
        prediccion_retraso (bool): Predicción de retraso
    
    Returns:
        list: Lista de recomendaciones
    """
    recomendaciones = []
    
    if prediccion_retraso:
        recomendaciones.append("Alto riesgo de retraso - Llegue al aeropuerto con tiempo extra")
        recomendaciones.append("Manténgase informado sobre el estado de su vuelo")
        recomendaciones.append("Considere tener un plan alternativo")
    else:
        recomendaciones.append("Bajo riesgo de retraso - Condiciones favorables para el vuelo")
    
    # Recomendaciones específicas por clima
    if datos_clima['precipitacion'] > 5:
        recomendaciones.append("Lluvia fuerte prevista - Permita tiempo adicional para llegar al aeropuerto")
    
    if datos_clima['viento_velocidad'] > 25:
        recomendaciones.append("Vientos fuertes - Posibles turbulencias durante el vuelo")
    
    if 'visibilidad' in datos_clima and datos_clima['visibilidad'] < 8:
        recomendaciones.append("Visibilidad reducida - Posibles demoras en operaciones aeroportuarias")
    
    if datos_clima['temperatura'] > 35 or datos_clima['temperatura'] < 5:
        recomendaciones.append("Temperatura extrema - Vístase apropiadamente y hidrátese bien")
    
    return recomendaciones

# ============= ENDPOINTS EXISTENTES DE FIREBASE =============
@app.route('/firebase/test', methods=['GET'])
def test_firebase():
    """Endpoint para probar la conexión con Firebase"""
    if firebase_service.test_connection():
        return jsonify({'status': 'success', 'message': 'Conexión a Firebase exitosa'})
    else:
        return jsonify({'status': 'error', 'message': 'Error conectando a Firebase'}), 500

@app.route('/firebase/predicciones/<ciudad>', methods=['GET'])
def obtener_predicciones_firebase(ciudad):
    """Obtiene predicciones de una ciudad desde Firebase"""
    fecha = request.args.get('fecha')
    predicciones = firebase_service.obtener_predicciones_ciudad(ciudad, fecha)
    return jsonify({
        'ciudad': ciudad,
        'fecha': fecha,
        'predicciones': predicciones
    })

@app.route('/firebase/estadisticas', methods=['GET'])
def obtener_estadisticas_firebase():
    """Obtiene estadísticas desde Firebase"""
    estadisticas = firebase_service.obtener_estadisticas()
    return jsonify(estadisticas)
# =========================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar el estado de la aplicación"""
    return jsonify({
        'status': 'healthy',
        'modelo_cargado': modelo is not None,
        'firebase_conectado': firebase_service.initialized,
        'email_service_disponible': email_service is not None,  # ⭐ NUEVO
        'timestamp': datetime.now().isoformat()
    })

@app.route('/info', methods=['GET'])
def info_modelo():
    """Endpoint para obtener información del modelo"""
    if modelo and hasattr(modelo, 'metricas'):
        return jsonify({
            'modelo_disponible': True,
            'metricas': modelo.metricas,
            'features_esperadas': list(modelo.scaler.feature_names_in_) if hasattr(modelo.scaler, 'feature_names_in_') else 'No disponible'
        })
    else:
        return jsonify({
            'modelo_disponible': False,
            'error': 'Modelo no cargado o sin métricas disponibles'
        })

@app.route('/ciudades', methods=['GET'])
def obtener_ciudades():
    """Endpoint para obtener lista de ciudades soportadas"""
    ciudades_soportadas = [
        {'codigo': 'lima', 'nombre': 'Lima', 'pais': 'Perú'},
        {'codigo': 'arequipa', 'nombre': 'Arequipa', 'pais': 'Perú'},
        {'codigo': 'piura', 'nombre': 'Piura', 'pais': 'Perú'},
        {'codigo': 'trujillo', 'nombre': 'Trujillo', 'pais': 'Perú'},
        {'codigo': 'cajamarca', 'nombre': 'Cajamarca', 'pais': 'Perú'},
        {'codigo': 'puno', 'nombre': 'Puno', 'pais': 'Perú'}
    ]
    
    return jsonify({
        'ciudades': ciudades_soportadas,
        'total': len(ciudades_soportadas)
    })

@app.route('/clima/<ciudad>', methods=['GET'])
def obtener_clima_actual(ciudad):
    """Endpoint para obtener clima actual de una ciudad"""
    try:
        fecha_actual = datetime.now().strftime('%Y-%m-%d')
        datos_clima = obtener_datos_clima_reales(ciudad, fecha_actual)
        
        return jsonify({
            'ciudad': ciudad,
            'fecha': fecha_actual,
            'clima': datos_clima,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': f'Error obteniendo clima: {str(e)}'}), 500

@app.route('/estadisticas')
def estadisticas():
    """Endpoint para mostrar estadísticas de la aplicación"""
    try:
        # Obtener estadísticas persistentes desde Firebase
        stats_firebase = firebase_service.obtener_estadisticas()

        # Obtener valores directamente de Firebase
        predicciones_hoy = stats_firebase.get('predicciones_hoy', 0)
        retrasos_ev = stats_firebase.get('retrasos_ev', 0)
        ahorro_usd = stats_firebase.get('ahorro_estimado_usd', 0)
        modelo_precision = stats_firebase.get('modelo_precision', '0%')

        return jsonify({
            'predicciones_realizadas': predicciones_hoy,
            'retrasos_evitados': retrasos_ev,
            'ahorro_estimado_usd': int(ahorro_usd),
            'modelo_precision': modelo_precision,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        print(f"Error obteniendo estadísticas: {e}")
        return jsonify({
            'predicciones_realizadas': 0,
            'retrasos_evitados': 0,
            'ahorro_estimado_usd': 0,
            'modelo_precision': '0%',
            'error': 'Error obteniendo estadísticas',
            'timestamp': datetime.now().isoformat()
        })

@app.route('/vuelos_programados', methods=['GET'])
def vuelos_programados():
    try:
        ref = db.reference('vuelos_programados')
        vuelos_raw = ref.get()

        vuelos = []
        if vuelos_raw:
            for key, v in vuelos_raw.items():
                vuelo = v.copy()
                vuelo['id'] = key
                vuelos.append(vuelo)

        return jsonify(vuelos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tickets', methods=['GET'])
def obtener_tickets():
    try:
        ref = firebase_service.db.reference('tickets') 
        data = ref.get()
        return jsonify(data if data else {})
    except Exception as e:
        print(f"❌ Error al obtener tickets: {e}")
        return jsonify({'error': str(e)}), 500

##================== ENDPOINTS DE EXPLICACIÓN DE PREDICCIÓN =================

@app.route('/explicar-prediccion', methods=['POST'])
def explicar_prediccion_endpoint():
    """
    Endpoint dedicado para obtener explicaciones de predicciones
    """
    try:
        data = request.json
        
        # Datos requeridos
        datos_clima_origen = data.get('datos_clima_origen', {})
        datos_clima_destino = data.get('datos_clima_destino', {})
        probabilidad_retraso = data.get('probabilidad_retraso', 0)
        datos_vuelo = data.get('datos_vuelo', {})
        
        datos_para_explicacion = {
            'datos_clima_origen': datos_clima_origen,
            'datos_clima_destino': datos_clima_destino,
            'datos_clima': data.get('datos_clima', {})
        }
        
        explicacion_completa = explicador.explicar_prediccion(
            datos_para_explicacion, 
            probabilidad_retraso, 
            datos_vuelo
        )
        
        explicacion_simple = generar_explicacion_simple(explicacion_completa)
        
        return jsonify({
            'success': True,
            'explicacion_completa': explicacion_completa,
            'explicacion_simple': explicacion_simple
        })
        
    except Exception as e:
        print(f"❌ Error en endpoint de explicación: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'explicacion_simple': {
                'mensaje_principal': 'Error generando explicación',
                'factores_clave': ['No disponible'],
                'recomendacion_principal': 'Consulte el estado de su vuelo'
            }
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)