import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from datetime import datetime, timezone, timedelta
import requests
import json
from dotenv import load_dotenv
import os

# Cargar variables del archivo .env
load_dotenv()

# Obtener la API KEY
API_KEY = os.getenv("OPENWEATHER_API_KEY")

if API_KEY:
    print("✅ Clave cargada correctamente:", API_KEY[:5] + "..." + API_KEY[-5:])
else:
    print("❌ No se pudo cargar la clave")

def cargar_datos_s3(url_dataset):
    """
    Carga datos desde S3 usando URL pública
    
    Args:
        url_dataset (str): URL del dataset en S3
    
    Returns:
        pandas.DataFrame: Dataset cargado
    """
    try:
        # Para CSV
        if url_dataset.endswith('.csv'):
            df = pd.read_csv(url_dataset)
        # Para JSON
        elif url_dataset.endswith('.json'):
            response = requests.get(url_dataset)
            data = response.json()
            df = pd.DataFrame(data)
        # Para Excel
        elif url_dataset.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(url_dataset)
        else:
            raise ValueError("Formato de archivo no soportado")
        
        print(f"Dataset cargado exitosamente: {df.shape[0]} filas, {df.shape[1]} columnas")
        return df
    
    except Exception as e:
        print(f"Error cargando datos desde S3: {e}")
        return None

def adaptar_dataset_real(df):
    """
    Adapta el dataset meteorológico real al formato esperado por el modelo
    
    Args:
        df (pandas.DataFrame): Dataset con columnas: date,tavg,tmin,tmax,prcp,snow,wdir,wspd,wpgt,pres,tsun
    
    Returns:
        pandas.DataFrame: Dataset adaptado
    """
    df_adaptado = df.copy()

    # Renombrar columnas para que coincidan con el pipeline
    renombres = {
        'date': 'fecha',
        'tavg': 'temperatura',        # Temperatura promedio
        'prcp': 'precipitacion',      # Precipitación
        'wspd': 'viento_velocidad',   # Velocidad del viento
        'pres': 'presion',            # Presión atmosférica
        'tmin': 'temperatura_min',    # Temperatura mínima (adicional)
        'tmax': 'temperatura_max',    # Temperatura máxima (adicional)
        'wdir': 'direccion_viento',   # Dirección del viento
        'wpgt': 'rafaga_viento',      # Ráfaga de viento
        'tsun': 'horas_sol'           # Horas de sol
    }
    
    # Renombrar solo las columnas que existen
    columnas_existentes = {k: v for k, v in renombres.items() if k in df_adaptado.columns}
    df_adaptado = df_adaptado.rename(columns=columnas_existentes)

    # Convertir fecha a datetime
    if 'fecha' in df_adaptado.columns:
        df_adaptado['fecha'] = pd.to_datetime(df_adaptado['fecha'])

    # Rellenar valores faltantes con estrategias específicas
    if 'temperatura' in df_adaptado.columns:
        df_adaptado['temperatura'] = df_adaptado['temperatura'].fillna(df_adaptado['temperatura'].mean())
    
    if 'precipitacion' in df_adaptado.columns:
        df_adaptado['precipitacion'] = df_adaptado['precipitacion'].fillna(0)
    
    if 'viento_velocidad' in df_adaptado.columns:
        df_adaptado['viento_velocidad'] = df_adaptado['viento_velocidad'].fillna(0)
    
    if 'presion' in df_adaptado.columns:
        df_adaptado['presion'] = df_adaptado['presion'].fillna(df_adaptado['presion'].mean())

    # Crear columnas derivadas que faltan en el dataset original
    # Humedad estimada (basada en temperatura y precipitación)
    if 'temperatura' in df_adaptado.columns and 'precipitacion' in df_adaptado.columns:
        # Fórmula empírica para estimar humedad
        df_adaptado['humedad'] = np.clip(
            70 + (df_adaptado['precipitacion'] * 5) - (df_adaptado['temperatura'] - 20) * 2 + np.random.normal(0, 5, len(df_adaptado)),
            30, 95
        )
    else:
        df_adaptado['humedad'] = 65  # Valor por defecto

    # Visibilidad estimada (inversamente relacionada con precipitación)
    if 'precipitacion' in df_adaptado.columns:
        df_adaptado['visibilidad'] = np.clip(
            15 - (df_adaptado['precipitacion'] * 0.8) + np.random.normal(0, 1, len(df_adaptado)),
            1, 15
        )
    else:
        df_adaptado['visibilidad'] = 12  # Valor por defecto

    # Nubosidad estimada (relacionada con precipitación y horas de sol)
    if 'precipitacion' in df_adaptado.columns:
        if 'horas_sol' in df_adaptado.columns:
            # Si tenemos horas de sol, usarlas
            df_adaptado['nubosidad'] = np.clip(
                100 - (df_adaptado['horas_sol'].fillna(6) * 8) + (df_adaptado['precipitacion'] * 15),
                0, 100
            )
        else:
            # Solo basada en precipitación
            df_adaptado['nubosidad'] = np.clip(
                30 + (df_adaptado['precipitacion'] * 20) + np.random.normal(0, 15, len(df_adaptado)),
                0, 100
            )
    else:
        df_adaptado['nubosidad'] = 40  # Valor por defecto

    # Simular retrasos con lógica basada en condiciones climáticas REALES
    retrasos = []
    for _, fila in df_adaptado.iterrows():
        prob = 0.03  # Probabilidad base baja (3%)
        
        # Factores de riesgo basados en datos reales
        if pd.notna(fila.get('precipitacion', 0)) and fila.get('precipitacion', 0) > 1:
            prob += 0.15  # Lluvia ligera
        if pd.notna(fila.get('precipitacion', 0)) and fila.get('precipitacion', 0) > 5:
            prob += 0.25  # Lluvia fuerte
        if pd.notna(fila.get('precipitacion', 0)) and fila.get('precipitacion', 0) > 10:
            prob += 0.3   # Lluvia muy fuerte
            
        if pd.notna(fila.get('viento_velocidad', 0)) and fila.get('viento_velocidad', 0) > 15:
            prob += 0.1   # Viento moderado
        if pd.notna(fila.get('viento_velocidad', 0)) and fila.get('viento_velocidad', 0) > 25:
            prob += 0.2   # Viento fuerte
        if pd.notna(fila.get('viento_velocidad', 0)) and fila.get('viento_velocidad', 0) > 35:
            prob += 0.3   # Viento muy fuerte
            
        # Temperaturas extremas
        if pd.notna(fila.get('temperatura', 20)):
            temp = fila.get('temperatura', 20)
            if temp < 5 or temp > 35:
                prob += 0.15
            if temp < 0 or temp > 40:
                prob += 0.25
        
        # Presión atmosférica baja (tormentas)
        if pd.notna(fila.get('presion', 1013.25)) and fila.get('presion', 1013.25) < 1005:
            prob += 0.1
        if pd.notna(fila.get('presion', 1013.25)) and fila.get('presion', 1013.25) < 995:
            prob += 0.2
            
        # Baja visibilidad estimada
        if fila.get('visibilidad', 12) < 8:
            prob += 0.2
        if fila.get('visibilidad', 12) < 5:
            prob += 0.3
            
        # Limitar probabilidad máxima
        prob = min(prob, 0.8)
        
        retrasos.append(int(np.random.rand() < prob))

    df_adaptado['retraso_vuelo'] = retrasos
    
    print(f"Dataset adaptado: {len(df_adaptado)} registros")
    print(f"Tasa de retrasos simulada: {np.mean(retrasos)*100:.1f}%")
    print(f"Columnas disponibles: {list(df_adaptado.columns)}")

    return df_adaptado

def procesar_datos_clima(df):
    """
    Procesa y limpia los datos climáticos reales
    
    Args:
        df (pandas.DataFrame): Dataset crudo con datos meteorológicos
    
    Returns:
        pandas.DataFrame: Dataset procesado
    """
    try:
        # Primero adaptar el dataset real al formato esperado
        df_procesado = adaptar_dataset_real(df)
        
        # Crear features adicionales de tiempo si hay columna fecha
        if 'fecha' in df_procesado.columns:
            df_procesado['hora'] = df_procesado['fecha'].dt.hour
            df_procesado['dia_semana'] = df_procesado['fecha'].dt.weekday
            df_procesado['mes'] = df_procesado['fecha'].dt.month
            df_procesado['es_fin_semana'] = (df_procesado['dia_semana'] >= 5).astype(int)
        
        # Crear features de condiciones extremas basadas en datos reales
        if 'precipitacion' in df_procesado.columns:
            df_procesado['lluvia_fuerte'] = (df_procesado['precipitacion'] > 5).astype(int)
        
        if 'viento_velocidad' in df_procesado.columns:
            df_procesado['viento_fuerte'] = (df_procesado['viento_velocidad'] > 20).astype(int)
        
        if 'visibilidad' in df_procesado.columns:
            df_procesado['baja_visibilidad'] = (df_procesado['visibilidad'] < 8).astype(int)
        
        # Manejo más robusto de valores faltantes
        columnas_numericas = df_procesado.select_dtypes(include=[np.number]).columns
        
        for col in columnas_numericas:
            if col != 'retraso_vuelo':  # No imputar la variable objetivo
                # Usar mediana para valores más robustos
                df_procesado[col] = df_procesado[col].fillna(df_procesado[col].median())
        
        # Eliminar outliers extremos (no todos, solo los más extremos)
        df_procesado = eliminar_outliers_extremos(df_procesado, columnas_numericas)
        
        print(f"Datos procesados: {df_procesado.shape[0]} filas después del procesamiento")
        print(f"Columnas finales: {list(df_procesado.columns)}")
        
        return df_procesado
    
    except Exception as e:
        print(f"Error procesando datos: {e}")
        import traceback
        traceback.print_exc()
        return df

def eliminar_outliers_extremos(df, columnas_numericas, max_eliminar=0.3):
    """
    Elimina solo outliers extremos usando un rango más amplio del IQR,
    y evita eliminar más del `max_eliminar`% del dataset.

    Args:
        df (pandas.DataFrame): DataFrame a procesar
        columnas_numericas (list): Lista de columnas numéricas
        max_eliminar (float): Proporción máxima de filas que se pueden eliminar (ej. 0.3 = 30%)

    Returns:
        pandas.DataFrame: DataFrame filtrado
    """
    df_limpio = df.copy()
    filas_originales = len(df_limpio)
    mask_total = pd.Series(True, index=df_limpio.index)

    for col in columnas_numericas:
        if col != 'retraso_vuelo':
            Q1 = df_limpio[col].quantile(0.25)
            Q3 = df_limpio[col].quantile(0.75)
            IQR = Q3 - Q1
            lim_inf = Q1 - 3.0 * IQR
            lim_sup = Q3 + 3.0 * IQR
            mask_col = (df_limpio[col] >= lim_inf) & (df_limpio[col] <= lim_sup)
            mask_total &= mask_col

    # Aplicar máscara si no elimina más del % permitido
    filas_filtradas = mask_total.sum()
    if filas_filtradas < (1 - max_eliminar) * filas_originales:
        print("⚠️ Demasiadas filas serían eliminadas como outliers. Se omite el filtrado.")
        return df  # devolver sin eliminar
    else:
        df_limpio = df_limpio[mask_total]
        print(f"Outliers eliminados: {filas_originales - len(df_limpio)} filas ({(1 - len(df_limpio)/filas_originales)*100:.1f}%)")
        return df_limpio

def preparar_features(df, columnas_target=['retraso_vuelo'], scaler=None, label_encoders=None):
    """
    Prepara features para entrenamiento o predicción del modelo con datos reales
    CORREGIDO: Maneja consistencia de columnas entre entrenamiento y predicción

    Args:
        df (pandas.DataFrame): Dataset procesado
        columnas_target (list): Columnas objetivo (solo en entrenamiento)
        scaler (StandardScaler): Escalador entrenado (opcional)
        label_encoders (dict): Diccionario de LabelEncoders entrenados (opcional)

    Returns:
        tuple: (X, y, scaler, label_encoders, feature_names)
    """
    try:
        df_features = df.copy()
        print(f"DataFrame de entrada - Shape: {df_features.shape}")
        print(f"Columnas disponibles: {list(df_features.columns)}")

        # Definir columnas esperadas por el modelo (solo las que estaban en entrenamiento)
        # Estas son las columnas básicas que debe tener el modelo
        columnas_esperadas = [
            'temperatura', 'precipitacion', 'viento_velocidad', 'presion',
            'humedad', 'visibilidad', 'nubosidad',
            'hora', 'dia_semana', 'mes', 'es_fin_semana',
            'lluvia_fuerte', 'viento_fuerte'
        ]

        # Si es modo predicción y tenemos scaler, usar sus feature names
        if scaler is not None and hasattr(scaler, 'feature_names_in_'):
            columnas_esperadas = list(scaler.feature_names_in_)
            print(f"Usando columnas del scaler entrenado: {columnas_esperadas}")

        # Asegurar que tenemos todas las columnas esperadas
        for col in columnas_esperadas:
            if col not in df_features.columns:
                print(f"Advertencia: Columna {col} no encontrada, usando valor por defecto")
                if col == 'temperatura':
                    df_features[col] = 22.0
                elif col == 'precipitacion':
                    df_features[col] = 0.0
                elif col == 'viento_velocidad':
                    df_features[col] = 10.0
                elif col == 'presion':
                    df_features[col] = 1013.25
                elif col == 'hora':
                    df_features[col] = 12
                elif col == 'dia_semana':
                    df_features[col] = 1
                elif col == 'mes':
                    df_features[col] = 6
                elif col == 'es_fin_semana':
                    df_features[col] = 0
                elif col == 'lluvia_fuerte':
                    df_features[col] = 0
                elif col == 'viento_fuerte':
                    df_features[col] = 0
                else:
                    df_features[col] = 0

        # Separar features y target
        columnas_a_eliminar = ['fecha']
        
        # Solo eliminar columnas target si existen
        for col_target in columnas_target:
            if col_target in df_features.columns:
                columnas_a_eliminar.append(col_target)
        
        # Eliminar columnas que no están en el conjunto esperado
        columnas_a_mantener = columnas_esperadas.copy()
        
        # Si hay columnas target, añadirlas temporalmente
        for col_target in columnas_target:
            if col_target in df_features.columns:
                columnas_a_mantener.append(col_target)
        
        # Filtrar solo las columnas que necesitamos
        df_filtrado = df_features[columnas_a_mantener].copy()
        
        # Separar X e y
        X = df_filtrado.drop(columnas_target, axis=1, errors='ignore')
        
        # Reordenar columnas según el orden esperado
        X = X[columnas_esperadas]
        
        # Solo extraer y si la columna target existe
        y = None
        if columnas_target and columnas_target[0] in df_filtrado.columns:
            y = df_filtrado[columnas_target[0]]

        print(f"Columnas finales de X: {list(X.columns)}")
        print(f"Shape de X después del filtrado: {X.shape}")

        # Verificar tipos de datos y convertir todo a numérico
        for col in X.columns:
            if X[col].dtype == 'object':
                print(f"Convirtiendo columna {col} a numérica")
                # Si hay un label encoder para esta columna, usarlo
                if label_encoders and col in label_encoders:
                    le = label_encoders[col]
                    try:
                        X[col] = le.transform(X[col].astype(str))
                    except ValueError:
                        # Valores no vistos, usar valor por defecto
                        X[col] = 0
                else:
                    # Convertir directamente a numérico
                    X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0)

        # Verificar que no hay valores NaN
        if X.isnull().any().any():
            print("Rellenando valores NaN con 0")
            X = X.fillna(0)
        
        # Verificar que no hay valores infinitos
        if np.isinf(X.values).any():
            print("Reemplazando valores infinitos")
            X = X.replace([np.inf, -np.inf], 0)

        # Escalar variables numéricas
        if scaler is None:
            # Modo entrenamiento - crear nuevo scaler
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            X = pd.DataFrame(X_scaled, columns=X.columns, index=X.index)
        else:
            # Modo predicción - usar scaler existente
            try:
                X_scaled = scaler.transform(X)
                X = pd.DataFrame(X_scaled, columns=X.columns, index=X.index)
            except Exception as e:
                print(f"Error en escalado: {e}")
                return None, None, None, None, None

        print(f"Shape final de X: {X.shape}")
        print(f"Columnas finales: {list(X.columns)}")
        
        return X, y, scaler, label_encoders, list(X.columns)

    except Exception as e:
        print(f"Error preparando features: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None, None

def diagnostico_features_antes_del_escalado(df):
    """
    Muestra estadísticas básicas de las features clave antes del escalado.
    """
    columnas_interes = ['humedad', 'visibilidad', 'nubosidad']
    print("\n📊 Estadísticas básicas antes del escalado:")
    for col in columnas_interes:
        if col in df.columns:
            print(f"\n🔹 {col.upper()}:")
            print(df[col].describe())
        else:
            print(f"⚠️ La columna '{col}' no está presente en el DataFrame.")

def analizar_aporte_nuevas_features(self, columnas=['humedad', 'visibilidad', 'nubosidad']):
    """
    Imprime la importancia de las nuevas variables si el modelo lo permite.
    """
    if hasattr(self.modelo, 'feature_importances_'):
        print("\n🎯 Importancia de nuevas features climáticas:")
        importancias = self.modelo.feature_importances_
        for col, imp in zip(self.scaler.feature_names_in_, importancias):
            if col in columnas:
                print(f"🔍 {col}: {imp:.4f}")
    else:
        print("⚠️ El modelo seleccionado no soporta análisis de importancia de variables.")

def validar_calidad_datos(df):
    """
    Valida la calidad de los datos meteorológicos reales
    
    Args:
        df (pandas.DataFrame): Dataset a validar
    
    Returns:
        dict: Reporte de calidad de datos
    """
    reporte = {
        'total_filas': len(df),
        'total_columnas': len(df.columns),
        'valores_faltantes': df.isnull().sum().to_dict(),
        'tipos_datos': df.dtypes.to_dict(),
        'duplicados': df.duplicated().sum(),
    }
    
    # Solo incluir estadísticas para columnas numéricas que existen
    columnas_numericas = df.select_dtypes(include=[np.number]).columns
    if len(columnas_numericas) > 0:
        reporte['estadisticas_numericas'] = df[columnas_numericas].describe().to_dict()
    
    # Calcular porcentaje de valores faltantes
    reporte['porcentaje_faltantes'] = {
        col: (count / len(df)) * 100 
        for col, count in reporte['valores_faltantes'].items()
    }
    
    # Reporte específico para datos meteorológicos
    if 'temperatura' in df.columns:
        reporte['rango_temperatura'] = {
            'min': df['temperatura'].min(),
            'max': df['temperatura'].max(),
            'promedio': df['temperatura'].mean()
        }
    
    if 'precipitacion' in df.columns:
        reporte['dias_lluvia'] = (df['precipitacion'] > 0).sum()
        reporte['precipitacion_maxima'] = df['precipitacion'].max()
    
    if 'retraso_vuelo' in df.columns:
        reporte['tasa_retrasos'] = df['retraso_vuelo'].mean() * 100
        reporte['total_retrasos'] = df['retraso_vuelo'].sum()
    
    return reporte

def obtener_datos_clima_reales(ciudad, fecha=None, hora=None):
    """
    Obtiene datos climáticos futuros (si se especifica fecha y hora) o actuales (por defecto) de OpenWeather.

    Args:
        ciudad (str): Nombre de la ciudad
        fecha (str): Fecha en formato YYYY-MM-DD (opcional)
        hora (str): Hora en formato HH:MM (opcional)

    Returns:
        dict: Diccionario con variables climáticas clave
    """
    if not API_KEY:
        print("❌ No se encontró la clave API de OpenWeather.")
        return {}

    try:
        # Si se da fecha y hora, usar API de pronóstico
        if fecha and hora:
            print("📅 Solicitando clima pronosticado...")
            url = f"http://api.openweathermap.org/data/2.5/forecast?q={ciudad}&appid={API_KEY}&units=metric"
            target_dt = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
        else:
            print("📍 Solicitando clima actual...")
            url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={API_KEY}&units=metric"
            target_dt = None

        response = requests.get(url)
        data = response.json()

        if response.status_code != 200:
            print("❌ Error en respuesta de OpenWeather:", data)
            return {}

        # Si se usa pronóstico
        if 'list' in data:
            forecast_data = data['list']
            closest_block = min(forecast_data, key=lambda x: abs(datetime.utcfromtimestamp(x['dt']) - target_dt))
            block = closest_block
        else:
            block = data  # clima actual

        # Extraer datos comunes
        temperatura = block['main']['temp']
        humedad = block['main']['humidity']
        presion = block['main']['pressure']
        visibilidad = block.get('visibility', 10000)  # en metros
        viento_velocidad = block['wind']['speed']
        nubosidad = block['clouds']['all']
        
        # Detectar precipitación real (si existe el campo rain)
        rain_data = block.get('rain', {})
        if 'list' in data:
            precipitacion = rain_data.get('3h', 0.0)  # Pronóstico
        else:
            precipitacion = rain_data.get('1h', 0.0)  # Clima actual

        # Imprimir para depurar
        if rain_data:
            print(f"🌧️ Lluvia detectada: {rain_data}")
        else:
            print("🌤️ No hay campo de lluvia (rain). Se asume 0 mm.")

        # Timestamp
        timestamp = block.get('dt')
        dt_utc = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else None
        dt_peru = dt_utc - timedelta(hours=5) if dt_utc else None

        clima = {
            'temperatura': round(temperatura, 1),
            'humedad': humedad,
            'presion': presion,
            'visibilidad': round(visibilidad / 1000, 1),  # a km
            'viento_velocidad': round(viento_velocidad * 3.6, 1),  # m/s → km/h
            'nubosidad': nubosidad,
            'precipitacion': precipitacion,
            'fecha_observacion_utc': dt_utc.strftime('%Y-%m-%d %H:%M:%S UTC') if dt_utc else 'N/A',
            'fecha_observacion_peru': dt_peru.strftime('%Y-%m-%d %H:%M:%S (UTC-5)') if dt_peru else 'N/A'
        }
        print("🔍 JSON recibido de OpenWeather:", json.dumps(block, indent=2))

        return clima

    except Exception as e:
        print(f"⚠️ Error al obtener datos climáticos: {e}")
        return {}

if __name__ == "__main__":
    ciudad = "Cajamarca"
    clima = obtener_datos_clima_reales(ciudad)
    print(f"🌦️ Clima actual en {ciudad}: {clima}")
