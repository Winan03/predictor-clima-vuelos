import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, accuracy_score
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from procesamiento import cargar_datos_s3, procesar_datos_clima, preparar_features, validar_calidad_datos, adaptar_dataset_real, diagnostico_features_antes_del_escalado, analizar_aporte_nuevas_features
import warnings
warnings.filterwarnings('ignore')

class ModeloClimaVuelos:
    def __init__(self):
        self.modelo = None
        self.scaler = None
        self.label_encoders = None
        self.metricas = {}

    def cargar_y_procesar_datos(self, usar_simulados=False):
        """
        Carga y procesa los datos para entrenamiento desde S3 (datos reales)

        Args:
            usar_simulados (bool): Parámetro mantenido por compatibilidad, pero siempre usará datos reales

        Returns:
            pandas.DataFrame: Datos procesados
        """
        print("Iniciando carga y procesamiento de datos desde S3...")

        # URLs de los datasets reales en S3
        urls = {
            'lima': 'https://transporteaereopredictivo.s3.amazonaws.com/Datos_Climaticos_Lima.csv',
            'arequipa': 'https://transporteaereopredictivo.s3.amazonaws.com/Datos_Climaticos_Arequipa.csv',
            'cajamarca': 'https://transporteaereopredictivo.s3.amazonaws.com/Datos_Climaticos_Cajamarca.csv',
            'piura': 'https://transporteaereopredictivo.s3.amazonaws.com/Datos_Climaticos_Piura.csv',
            'puno': 'https://transporteaereopredictivo.s3.amazonaws.com/Datos_Climaticos_Puno.csv',
            'trujillo': 'https://transporteaereopredictivo.s3.amazonaws.com/Datos_Climaticos_Trujillo.csv'
        }

        dataframes = []

        for ciudad, url in urls.items():
            print(f"📦 Cargando datos de {ciudad}...")
            df = cargar_datos_s3(url)
            if df is not None:
                df['ciudad'] = ciudad
                print(f"✅ {ciudad} cargado: {df.shape[0]} filas.")
                # Adaptar y procesar los datos reales
                df_adaptado = adaptar_dataset_real(df)
                df_procesado = procesar_datos_clima(df_adaptado)
                dataframes.append(df_procesado)
            else:
                print(f"❌ Error al cargar datos de {ciudad}")

        if dataframes:
            df_total = pd.concat(dataframes, ignore_index=True)

            print("\nDistribución de clases en 'retraso_vuelo':")
            print(df_total['retraso_vuelo'].value_counts())

            clase_counts = df_total['retraso_vuelo'].value_counts()

            # Solo advertir si hay muy pocos positivos
            if 1 not in clase_counts or clase_counts[1] < 10:
                print("⚠️ Advertencia: Muy pocos ejemplos positivos de retrasos. Esto puede afectar el recall del modelo.")

            # Verificar nuevamente que haya al menos 2 muestras por clase
            clase_counts_final = df_total['retraso_vuelo'].value_counts()
            if clase_counts_final.nunique() < 2 or clase_counts_final.min() < 2:
                print("❌ Error: La distribución de clases sigue siendo insuficiente para estratificar.")
                return None

            print(f"\n✅ Datos combinados: {df_total.shape[0]} filas en total.")
            print("✅ Distribución final de clases:")
            print(clase_counts_final)

            return df_total
        else:
            print("⚠️ No se pudo cargar ningún dataset.")
            return None
    
    def entrenar_modelos(self, df, test_size=0.2, random_state=42):
        """
        Entrena múltiples modelos y selecciona el mejor
        
        Args:
            df (pandas.DataFrame): Datos procesados
            test_size (float): Proporción de datos para prueba
            random_state (int): Semilla aleatoria
        """
        print("Iniciando entrenamiento de modelos...")
        
        # Diagnóstico visual previo al escalado
        diagnostico_features_antes_del_escalado(df)

        # Preparar features
        X, y, self.scaler, self.label_encoders, columnas_features = preparar_features(df)
        
        if X is None or y is None:
            print("Error preparando features")
            return
        
        # Verificar que tenemos suficientes datos para dividir
        if len(X) < 10:
            print("Error: No hay suficientes datos para entrenar el modelo")
            return
        
        # Dividir datos
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state, stratify=y
            )
        except ValueError as e:
            print(f"Error dividiendo datos: {e}")
            # Intentar sin estratificación si hay problemas
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state
            )
        
        print(f"Datos de entrenamiento: {X_train.shape}")
        print(f"Datos de prueba: {X_test.shape}")
        
        # Definir modelos a probar
        modelos = {
            'RandomForest': RandomForestClassifier(random_state=random_state),
            'GradientBoosting': GradientBoostingClassifier(random_state=random_state),
            'LogisticRegression': LogisticRegression(random_state=random_state, max_iter=1000),
            'SVM': SVC(probability=True, random_state=random_state)
        }
        
        # Parámetros para GridSearch (simplificados para datasets pequeños)
        parametros = {
            'RandomForest': {
                'n_estimators': [50, 100],
                'max_depth': [5, 10, None],
                'min_samples_split': [2, 5]
            },
            'GradientBoosting': {
                'n_estimators': [50, 100],
                'learning_rate': [0.1, 0.15],
                'max_depth': [3, 5]
            },
            'LogisticRegression': {
                'C': [0.1, 1, 10],
                'penalty': ['l1', 'l2'],
                'solver': ['liblinear']
            },
            'SVM': {
                'C': [0.1, 1, 10],
                'kernel': ['rbf', 'linear']
            }
        }
        
        mejores_modelos = {}
        resultados = {}
        
        # Entrenar cada modelo
        for nombre, modelo in modelos.items():
            print(f"\nEntrenando {nombre}...")
            
            try:
                # GridSearch para encontrar mejores parámetros
                # Usar cv=3 para datasets pequeños
                cv_folds = min(3, len(X_train) // 5) if len(X_train) >= 10 else 2
                
                grid_search = GridSearchCV(
                    modelo, 
                    parametros[nombre], 
                    cv=cv_folds, 
                    scoring='roc_auc',
                    n_jobs=-1
                )
                
                grid_search.fit(X_train, y_train)
                mejor_modelo = grid_search.best_estimator_
                
                # Predicciones
                y_pred = mejor_modelo.predict(X_test)
                y_pred_proba = mejor_modelo.predict_proba(X_test)[:, 1]
                
                # Métricas
                accuracy = accuracy_score(y_test, y_pred)
                auc = roc_auc_score(y_test, y_pred_proba)
                
                # Cross-validation
                cv_scores = cross_val_score(mejor_modelo, X_train, y_train, cv=cv_folds, scoring='roc_auc')
                
                resultados[nombre] = {
                    'modelo': mejor_modelo,
                    'accuracy': accuracy,
                    'auc': auc,
                    'cv_mean': cv_scores.mean(),
                    'cv_std': cv_scores.std(),
                    'mejores_parametros': grid_search.best_params_
                }
                
                print(f"Accuracy: {accuracy:.4f}")
                print(f"AUC: {auc:.4f}")
                print(f"CV Score: {cv_scores.mean():.4f} (+/- {cv_scores.std()*2:.4f})")
                
            except Exception as e:
                print(f"Error entrenando {nombre}: {e}")
                continue
        
        if not resultados:
            print("Error: No se pudo entrenar ningún modelo")
            return
        
        # Seleccionar mejor modelo
        mejor_nombre = max(resultados, key=lambda k: resultados[k]['auc'])
        self.modelo = resultados[mejor_nombre]['modelo']
        self.metricas = resultados
        
        print(f"\nMejor modelo seleccionado: {mejor_nombre}")
        print(f"AUC: {resultados[mejor_nombre]['auc']:.4f}")
        
        # Evaluación detallada del mejor modelo
        self._evaluar_modelo_detallado(X_test, y_test, mejor_nombre)
        
        # Importancia de features (si el modelo lo soporta)
        self._analizar_importancia_features(columnas_features)

        # Análisis de importancia de nuevas variables climáticas
        analizar_aporte_nuevas_features(self)
    
    def _evaluar_modelo_detallado(self, X_test, y_test, nombre_modelo):
        """Evaluación detallada del mejor modelo"""
        y_pred = self.modelo.predict(X_test)
        y_pred_proba = self.modelo.predict_proba(X_test)[:, 1]
        
        print(f"\n=== Evaluación detallada - {nombre_modelo} ===")
        print("\nReporte de clasificación:")
        print(classification_report(y_test, y_pred))
        
        print("\nMatriz de confusión:")
        cm = confusion_matrix(y_test, y_pred)
        print(cm)
        
        # Métricas adicionales
        if cm.shape == (2, 2):
            tn, fp, fn, tp = cm.ravel()
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
            sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        else:
            print("⚠️ Matriz de confusión no tiene ambas clases. No se pueden calcular métricas adicionales.")
            specificity = sensitivity = precision = 0

        print(f"\nMétricas adicionales:")
        print(f"Especificidad: {specificity:.4f}")
        print(f"Sensibilidad (Recall): {sensitivity:.4f}")
        print(f"Precisión: {precision:.4f}")
    
    def _analizar_importancia_features(self, columnas):
        """Analiza la importancia de las features"""
        if hasattr(self.modelo, 'feature_importances_'):
            importancias = self.modelo.feature_importances_
            feature_importance = pd.DataFrame({
                'feature': columnas,
                'importance': importancias
            }).sort_values('importance', ascending=False)
            
            print("\nTop 10 features más importantes:")
            print(feature_importance.head(10))
            
            return feature_importance
        else:
            print("El modelo seleccionado no proporciona importancia de features")
            return None
    
    def guardar_modelo(self, ruta='modelo_vuelos_clima.pkl'):
        """Guarda el modelo entrenado"""
        if self.modelo is not None:
            print("✅ Guardando modelo...")
            modelo_completo = {
                'modelo': self.modelo,
                'scaler': self.scaler,
                'label_encoders': self.label_encoders,
                'metricas': self.metricas
            }
            joblib.dump(modelo_completo, ruta)
            print(f"✅ Modelo guardado en: {ruta}")
        else:
            print("❌ No hay modelo entrenado para guardar")

    def cargar_modelo(self, ruta='modelo_vuelos_clima.pkl'):
        """
        Carga un modelo previamente entrenado
        
        Args:
            ruta (str): Ruta del modelo guardado
        """
        try:
            modelo_completo = joblib.load(ruta)
            self.modelo = modelo_completo['modelo']
            self.scaler = modelo_completo['scaler']
            self.label_encoders = modelo_completo['label_encoders']
            self.metricas = modelo_completo['metricas']
            print(f"Modelo cargado desde: {ruta}")
        except FileNotFoundError:
            print(f"No se encontró el archivo: {ruta}")
        except Exception as e:
            print(f"Error cargando modelo: {str(e)}")
    
    def predecir(self, datos_nuevos):
        """
        Realiza predicciones con el modelo entrenado

        Args:
            datos_nuevos (pandas.DataFrame): Datos para predecir

        Returns:
            dict: Diccionario con predicciones y probabilidades
        """
        if self.modelo is None:
            print("No hay modelo entrenado. Entrena o carga un modelo primero.")
            return None

        try:
            # Usar preparar_features y tomar solo el primer valor (X_nuevos)
            resultado = preparar_features(
                datos_nuevos,
                columnas_target=[],  # No hay columna target en predicción
                scaler=self.scaler,
                label_encoders=self.label_encoders
            )

            if not resultado or len(resultado) < 1:
                print("❌ No se pudo preparar los datos para predicción.")
                return None

            # Solo nos interesa X_nuevos para predecir
            X_nuevos = resultado[0]

            predicciones = self.modelo.predict(X_nuevos)
            probabilidades = self.modelo.predict_proba(X_nuevos)[:, 1]

            return {
                'predicciones': predicciones,
                'probabilidades': probabilidades
            }

        except Exception as e:
            print(f"Error en predicción: {str(e)}")
            return None

    
    def predecir_probabilidad(self, datos_nuevos):
        """
        Obtiene las probabilidades de cancelación
        
        Args:
            datos_nuevos (pandas.DataFrame): Datos para predecir
            
        Returns:
            numpy.array: Probabilidades de cancelación
        """
        resultado = self.predecir(datos_nuevos)
        if resultado:
            return resultado['probabilidades']
        return None
    
    def mostrar_metricas(self):
        """Muestra las métricas de todos los modelos evaluados"""
        if not self.metricas:
            print("No hay métricas disponibles")
            return
        
        print("\n=== RESUMEN DE MÉTRICAS DE TODOS LOS MODELOS ===")
        for nombre, metricas in self.metricas.items():
            print(f"\n{nombre}:")
            print(f"  Accuracy: {metricas['accuracy']:.4f}")
            print(f"  AUC: {metricas['auc']:.4f}")
            print(f"  CV Score: {metricas['cv_mean']:.4f} (+/- {metricas['cv_std']*2:.4f})")
            print(f"  Mejores parámetros: {metricas['mejores_parametros']}")
    
    def generar_reporte_completo(self, ruta_reporte='reporte_modelo.txt'):
        """
        Genera un reporte completo del modelo
        
        Args:
            ruta_reporte (str): Ruta donde guardar el reporte
        """
        if not self.metricas:
            print("No hay métricas para generar reporte")
            return
        
        with open(ruta_reporte, 'w', encoding='utf-8') as f:
            f.write("REPORTE COMPLETO - MODELO CLIMA VUELOS\n")
            f.write("=" * 50 + "\n\n")
            
            # Mejor modelo
            mejor_nombre = max(self.metricas, key=lambda k: self.metricas[k]['auc'])
            f.write(f"MEJOR MODELO SELECCIONADO: {mejor_nombre}\n")
            f.write(f"AUC Score: {self.metricas[mejor_nombre]['auc']:.4f}\n")
            f.write(f"Accuracy: {self.metricas[mejor_nombre]['accuracy']:.4f}\n\n")
            
            # Todas las métricas
            f.write("COMPARACIÓN DE TODOS LOS MODELOS:\n")
            f.write("-" * 40 + "\n")
            
            for nombre, metricas in self.metricas.items():
                f.write(f"\n{nombre}:\n")
                f.write(f"  Accuracy: {metricas['accuracy']:.4f}\n")
                f.write(f"  AUC: {metricas['auc']:.4f}\n")
                f.write(f"  CV Score: {metricas['cv_mean']:.4f} (+/- {metricas['cv_std']*2:.4f})\n")
                f.write(f"  Parámetros: {metricas['mejores_parametros']}\n")
        
        print(f"Reporte guardado en: {ruta_reporte}")

# Función principal para usar la clase
def main():
    """Función principal para entrenar el modelo"""
    
    # Crear instancia del modelo
    modelo_vuelos = ModeloClimaVuelos()
    
    # Cargar y procesar datos (solo datos reales desde S3)
    datos = modelo_vuelos.cargar_y_procesar_datos(usar_simulados=False)
    
    if datos is not None:
        # Entrenar modelos
        modelo_vuelos.entrenar_modelos(datos)
        
        # Mostrar métricas
        modelo_vuelos.mostrar_metricas()
        
        # Guardar modelo
        modelo_vuelos.guardar_modelo()
        
        # Generar reporte
        modelo_vuelos.generar_reporte_completo()
        
        print("\n¡Entrenamiento completado exitosamente!")
    else:
        print("Error: No se pudieron cargar los datos")

if __name__ == "__main__":
    main()