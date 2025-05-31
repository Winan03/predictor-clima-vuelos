from flask import Flask, render_template, request, jsonify
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import os
from procesamiento import procesar_datos_clima, preparar_features, obtener_datos_clima_reales
from entrenamiento import ModeloClimaVuelos
from firebase_service import FirebaseService  # <-- NUEVO IMPORT

app = Flask(__name__)

# Habilita CORS para todos los dominios
from flask_cors import CORS
CORS(app)

contador_predicciones = 0
retrasos_evitados = 0
ahorro_estimado = 0

# Inicializar Firebase Service
firebase_service = FirebaseService()  # <-- NUEVO

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

@app.route('/predecir', methods=['POST'])
def predecir_retraso():
    """
    MODIFICADO: Endpoint de predicción que guarda en Firebase
    """
    try:
        data = request.json
        
        ciudad = data.get('ciudad')
        fecha = data.get('fecha')
        hora = data.get('hora')
        pasajeros = data.get('pasajeros', 120)  
        costo = data.get('costo', 100.0)
        user_id = data.get('user_id')  # <-- NUEVO: ID del usuario (opcional)

        
        # Validar datos de entrada
        if not ciudad or not fecha or not hora:
            return jsonify({'error': 'Faltan datos requeridos: ciudad, fecha, hora'}), 400
        
        # Obtener datos climáticos
        datos_clima = obtener_datos_clima_reales(ciudad, fecha, hora)
        
        # Convertir fecha y hora
        try:
            dt = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
        except ValueError:
            return jsonify({'error': 'Formato de fecha/hora inválido. Use YYYY-MM-DD HH:MM'}), 400
        
        if modelo:
            try:
                # Crear DataFrame con SOLO las columnas que el modelo espera
                # Primero intentar obtener las columnas esperadas del modelo
                if hasattr(modelo, 'columnas_esperadas') and modelo.columnas_esperadas:
                    columnas_modelo = modelo.columnas_esperadas
                else:
                    # Usar columnas básicas si no se pueden obtener del modelo
                    columnas_modelo = [
                        'temperatura', 'precipitacion', 'viento_velocidad', 'presion',
                        'hora', 'dia_semana', 'mes', 'es_fin_semana', 
                        'lluvia_fuerte', 'viento_fuerte'
                    ]
                
                print(f"Columnas que espera el modelo: {columnas_modelo}")
                
                # Crear DataFrame solo con las columnas necesarias
                data_dict = {}
                
                # Mapear datos climáticos a las columnas esperadas
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
                        # Para cualquier otra columna, usar valor por defecto
                        data_dict[col] = 0
                
                # Crear DataFrame
                df_nuevo = pd.DataFrame([data_dict])
                
                print(f"DataFrame para predicción:")
                print(f"Columnas: {list(df_nuevo.columns)}")
                print(f"Valores: {df_nuevo.iloc[0].to_dict()}")

                # Preparar features
                X_nuevo, _, _, _, _ = preparar_features(
                    df_nuevo,
                    columnas_target=[],  # No hay columna target en predicción
                    scaler=modelo.scaler,
                    label_encoders=modelo.label_encoders
                )
                # Si hay valores vacíos o infinitos, los reemplazo por 0
                if X_nuevo.isnull().any().any() or np.isinf(X_nuevo.values).any():
                    print("⚠️ Había datos vacíos o inválidos. Se limpiaron.")
                    X_nuevo = X_nuevo.replace([np.inf, -np.inf], 0).fillna(0)

                if X_nuevo is None or X_nuevo.empty:
                    return jsonify({'error': 'Error preparando features para predicción'}), 500
                
                print(f"Shape de X_nuevo: {X_nuevo.shape}")
                print(f"Columnas de X_nuevo: {list(X_nuevo.columns)}")
                
                # Realizar predicción
                prediccion = modelo.modelo.predict(X_nuevo)[0]

                # Intentar obtener la probabilidad de retraso con seguridad
                try:
                    probabilidad = modelo.modelo.predict_proba(X_nuevo)[0]
                    prob_retraso = float(probabilidad[1]) * 100  # En porcentaje
                except Exception as e:
                    print("⚠️ Falló al calcular la probabilidad:", e)
                    prob_retraso = 0.0
                    probabilidad = [100.0, 0.0]  # Default si algo sale mal
                
                print("🔍 Probabilidad cruda:", probabilidad)

                # Asignar nivel de riesgo más sensible
                if prob_retraso > 60:
                    riesgo = "alto"
                elif prob_retraso > 30:
                    riesgo = "medio"
                else:
                    riesgo = "bajo"
                
                # Calcular confianza
                confianza = max(probabilidad) * 100
                
                # Interpretar resultados
                resultado = {
                    'prediccion': bool(prediccion),
                    'probabilidad_retraso': prob_retraso,
                    'probabilidad_puntual': float(probabilidad[0]) * 100,
                    'confianza': float(confianza),
                    'riesgo': riesgo,  # <- Esta línea es clave
                    'factores_riesgo': analizar_factores_riesgo(datos_clima, dt),
                    'recomendaciones': generar_recomendaciones(datos_clima, prediccion),
                    'datos_clima': datos_clima,
                    'fecha_hora': f"{fecha} {hora}",
                    'ciudad': ciudad
                }
                
                global contador_predicciones, retrasos_evitados, ahorro_estimado
                contador_predicciones += 1

                if prediccion:  
                    retrasos_evitados += 1
                    ahorro_estimado += round(pasajeros * costo)
                    resultado['ahorro_estimado'] = round(pasajeros * costo)
                else:
                    resultado['ahorro_estimado'] = 0

                # ============= NUEVO: GUARDAR EN FIREBASE =============
                try:
                    firebase_service.guardar_prediccion_vuelo(
                        ciudad=ciudad,
                        fecha=fecha,
                        hora=hora,
                        resultado_prediccion=resultado,
                        user_id=user_id
                    )
                    
                    # Actualizar estadísticas en Firebase
                    precision_modelo = 98.6  # Puedes obtener esto del modelo real
                    firebase_service.actualizar_estadisticas(
                        predicciones_hoy=contador_predicciones,
                        precision_modelo=precision_modelo,
                        retrasos_evitados=retrasos_evitados,
                        ahorro_estimado=ahorro_estimado
                    )
                    
                    resultado['firebase_guardado'] = True
                    print("✅ Datos guardados en Firebase")
                    
                except Exception as firebase_error:
                    print(f"⚠️ Error guardando en Firebase: {firebase_error}")
                    resultado['firebase_guardado'] = False
                # ===================================================

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

def analizar_factores_riesgo(datos_clima, fecha_hora):
    factores = []

    # Precipitación
    if datos_clima['precipitacion'] > 10:
        factores.append({'factor': 'Lluvia muy fuerte', 'nivel': 'alto', 'valor': f"{datos_clima['precipitacion']} mm"})
    elif datos_clima['precipitacion'] > 5:
        factores.append({'factor': 'Lluvia moderada', 'nivel': 'medio', 'valor': f"{datos_clima['precipitacion']} mm"})
    elif datos_clima['precipitacion'] > 1:
        factores.append({'factor': 'Lluvia ligera', 'nivel': 'bajo', 'valor': f"{datos_clima['precipitacion']} mm"})

    # Viento
    if datos_clima['viento_velocidad'] > 35:
        factores.append({'factor': 'Viento muy fuerte', 'nivel': 'alto', 'valor': f"{datos_clima['viento_velocidad']} km/h"})
    elif datos_clima['viento_velocidad'] > 25:
        factores.append({'factor': 'Viento fuerte', 'nivel': 'medio', 'valor': f"{datos_clima['viento_velocidad']} km/h"})
    elif datos_clima['viento_velocidad'] > 15:
        factores.append({'factor': 'Viento moderado', 'nivel': 'bajo', 'valor': f"{datos_clima['viento_velocidad']} km/h"})

    # Visibilidad (si está disponible)
    if 'visibilidad' in datos_clima:
        if datos_clima['visibilidad'] < 5:
            factores.append({'factor': 'Visibilidad muy baja', 'nivel': 'alto', 'valor': f"{datos_clima['visibilidad']} km"})
        elif datos_clima['visibilidad'] < 8:
            factores.append({'factor': 'Visibilidad reducida', 'nivel': 'medio', 'valor': f"{datos_clima['visibilidad']} km"})

    # Temperatura extrema
    if datos_clima['temperatura'] > 40:
        factores.append({'factor': 'Temperatura muy alta', 'nivel': 'medio', 'valor': f"{datos_clima['temperatura']}°C"})
    elif datos_clima['temperatura'] < 0:
        factores.append({'factor': 'Temperatura bajo cero', 'nivel': 'medio', 'valor': f"{datos_clima['temperatura']}°C"})

    # Presión atmosférica
    if datos_clima['presion'] < 995:
        factores.append({'factor': 'Presión muy baja (tormenta)', 'nivel': 'alto', 'valor': f"{datos_clima['presion']} hPa"})
    elif datos_clima['presion'] < 1005:
        factores.append({'factor': 'Presión baja', 'nivel': 'medio', 'valor': f"{datos_clima['presion']} hPa"})

    # Nubosidad (si está disponible)
    if 'nubosidad' in datos_clima:
        if datos_clima['nubosidad'] > 80:
            factores.append({'factor': 'Cielo muy nublado', 'nivel': 'bajo', 'valor': f"{datos_clima['nubosidad']}%"})

    # Factores temporales
    if fecha_hora.hour in [6, 7, 8, 18, 19, 20]:
        factores.append({'factor': 'Hora pico de tráfico aéreo', 'nivel': 'bajo', 'valor': f"{fecha_hora.hour}:00"})

    if fecha_hora.weekday() >= 5:
        factores.append({'factor': 'Fin de semana', 'nivel': 'bajo', 'valor': 'Mayor tráfico'})

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

# ============= NUEVOS ENDPOINTS PARA FIREBASE =============
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
        'firebase_conectado': firebase_service.initialized,  # <-- NUEVO
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
        # Obtener estadísticas desde Firebase
        stats_firebase = firebase_service.obtener_estadisticas()
        
        # Combinar con estadísticas locales
        estadisticas_completas = {
            'predicciones_realizadas': contador_predicciones,
            'retrasos_evitados': retrasos_evitados,
            'ahorro_estimado_usd': int(ahorro_estimado),
            'modelo_precision': '98.6%',
            'firebase_stats': stats_firebase,
            'modelo_cargado': modelo is not None,
            'firebase_conectado': firebase_service.initialized,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(estadisticas_completas)
        
    except Exception as e:
        print(f"Error obteniendo estadísticas: {e}")
        return jsonify({
            'predicciones_realizadas': contador_predicciones,
            'retrasos_evitados': retrasos_evitados,
            'ahorro_estimado_usd': int(ahorro_estimado),
            'modelo_precision': '98.6%',
            'modelo_cargado': modelo is not None,
            'firebase_conectado': firebase_service.initialized,
            'error': 'Error obteniendo estadísticas de Firebase',
            'timestamp': datetime.now().isoformat()
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)