"""
Módulo de Explicabilidad para Predicciones de Vuelos
Genera explicaciones detalladas de por qué el modelo predice retrasos
"""

import pandas as pd
import numpy as np
from datetime import datetime

class ExplicadorPredicciones:
    """
    Clase que analiza y explica las razones detrás de las predicciones del modelo
    """
    
    def __init__(self):
        # Pesos de importancia para cada factor (ajustables)
        self.pesos_factores = {
            'clima_origen': 0.35,
            'clima_destino': 0.35,
            'temporal': 0.15,
            'operacional': 0.15
        }
        
        # Umbrales para clasificar factores
        self.umbrales = {
            'precipitacion_alta': 3.0,
            'viento_fuerte': 18.0,
            'temperatura_extrema_baja': 8.0,
            'temperatura_extrema_alta': 32.0,
            'presion_baja': 1005.0,
            'visibilidad_reducida': 8.0,
            'nubosidad_alta': 70.0,
            'ocupacion_alta': 85.0,
            'hora_pico_inicio': [6, 7, 8],
            'hora_pico_fin': [18, 19, 20, 21]
        }
    
    def explicar_prediccion(self, datos_prediccion, probabilidad_retraso, datos_vuelo):
        """
        Genera una explicación completa de la predicción
        
        Args:
            datos_prediccion (dict): Datos climáticos y de contexto
            probabilidad_retraso (float): Probabilidad de retraso (0-100)
            datos_vuelo (dict): Información del vuelo (origen, destino, fecha, etc.)
        
        Returns:
            dict: Explicación estructurada de la predicción
        """
        explicacion = {
            'resumen': self._generar_resumen(probabilidad_retraso),
            'factores_principales': [],
            'factores_secundarios': [],
            'factores_favorables': [],
            'puntuacion_total': probabilidad_retraso,
            'nivel_confianza': self._calcular_confianza(datos_prediccion),
            'recomendaciones_especificas': []
        }
        
        # Analizar cada categoría de factores
        factores_clima_origen = self._analizar_clima(
            datos_prediccion.get('datos_clima_origen', {}), 
            'origen', 
            datos_vuelo.get('origen', '')
        )
        
        factores_clima_destino = self._analizar_clima(
            datos_prediccion.get('datos_clima_destino', {}), 
            'destino', 
            datos_vuelo.get('ciudad', '')
        )
        
        factores_temporales = self._analizar_factores_temporales(datos_vuelo)
        factores_operacionales = self._analizar_factores_operacionales(datos_vuelo)
        
        # Combinar todos los factores
        todos_factores = (factores_clima_origen + factores_clima_destino + 
                         factores_temporales + factores_operacionales)
        
        # Clasificar factores por impacto
        for factor in todos_factores:
            if factor['impacto'] >= 30:
                explicacion['factores_principales'].append(factor)
            elif factor['impacto'] >= 15:
                explicacion['factores_secundarios'].append(factor)
            else:
                explicacion['factores_favorables'].append(factor)
        
        # Ordenar por impacto
        explicacion['factores_principales'].sort(key=lambda x: x['impacto'], reverse=True)
        explicacion['factores_secundarios'].sort(key=lambda x: x['impacto'], reverse=True)
        
        # Generar recomendaciones específicas
        explicacion['recomendaciones_especificas'] = self._generar_recomendaciones_especificas(
            explicacion['factores_principales'] + explicacion['factores_secundarios']
        )
        
        return explicacion
    
    def _generar_resumen(self, probabilidad):
        """Genera un resumen ejecutivo de la predicción"""
        if probabilidad >= 70:
            return {
                'nivel': 'ALTO',
                'mensaje': 'Riesgo muy alto de retraso. Se recomienda precaución extrema.',
                'color': '#dc3545',  # Rojo
                'icono': '⚠️'
            }
        elif probabilidad >= 40:
            return {
                'nivel': 'MEDIO',
                'mensaje': 'Riesgo moderado de retraso. Monitorear condiciones.',
                'color': '#ffc107',  # Amarillo
                'icono': '⚡'
            }
        else:
            return {
                'nivel': 'BAJO',
                'mensaje': 'Condiciones favorables para vuelo puntual.',
                'color': '#28a745',  # Verde
                'icono': '✅'
            }
    
    def _analizar_clima(self, datos_clima, tipo_ubicacion, nombre_ciudad):
        """Analiza factores climáticos"""
        factores = []
        
        if not datos_clima:
            return factores
        
        # Precipitación
        precipitacion = datos_clima.get('precipitacion', 0)
        if precipitacion > self.umbrales['precipitacion_alta']:
            intensidad = 'muy fuerte' if precipitacion > 10 else 'fuerte'
            factores.append({
                'categoria': f'Clima en {tipo_ubicacion}',
                'factor': f'Lluvia {intensidad} en {nombre_ciudad}',
                'valor': f'{precipitacion} mm',
                'impacto': min(precipitacion * 8, 50),
                'descripcion': f'La precipitación intensa puede causar demoras en las operaciones de pista.',
                'tipo': 'negativo'
            })
        
        # Viento
        viento = datos_clima.get('viento_velocidad', 0)
        if viento > self.umbrales['viento_fuerte']:
            intensidad = 'muy fuertes' if viento > 30 else 'fuertes'
            factores.append({
                'categoria': f'Clima en {tipo_ubicacion}',
                'factor': f'Vientos {intensidad} en {nombre_ciudad}',
                'valor': f'{viento} km/h',
                'impacto': min((viento - 15) * 2, 40),
                'descripcion': f'Vientos intensos pueden afectar maniobras de despegue y aterrizaje.',
                'tipo': 'negativo'
            })
        
        # Temperatura extrema
        temperatura = datos_clima.get('temperatura', 20)
        if temperatura < self.umbrales['temperatura_extrema_baja']:
            factores.append({
                'categoria': f'Clima en {tipo_ubicacion}',
                'factor': f'Temperatura muy baja en {nombre_ciudad}',
                'valor': f'{temperatura}°C',
                'impacto': (8 - temperatura) * 3,
                'descripcion': 'Temperaturas bajas pueden afectar equipos de tierra y formación de hielo.',
                'tipo': 'negativo'
            })
        elif temperatura > self.umbrales['temperatura_extrema_alta']:
            factores.append({
                'categoria': f'Clima en {tipo_ubicacion}',
                'factor': f'Temperatura muy alta en {nombre_ciudad}',
                'valor': f'{temperatura}°C',
                'impacto': (temperatura - 32) * 2,
                'descripcion': 'Temperaturas altas reducen la densidad del aire y afectan el rendimiento.',
                'tipo': 'negativo'
            })
        
        # Visibilidad
        visibilidad = datos_clima.get('visibilidad', 10)
        if visibilidad < self.umbrales['visibilidad_reducida']:
            factores.append({
                'categoria': f'Clima en {tipo_ubicacion}',
                'factor': f'Visibilidad reducida en {nombre_ciudad}',
                'valor': f'{visibilidad} km',
                'impacto': (8 - visibilidad) * 5,
                'descripcion': 'Baja visibilidad puede requerir procedimientos de aproximación especiales.',
                'tipo': 'negativo'
            })
        
        # Presión atmosférica
        presion = datos_clima.get('presion', 1013)
        if presion < self.umbrales['presion_baja']:
            factores.append({
                'categoria': f'Clima en {tipo_ubicacion}',
                'factor': f'Presión atmosférica baja en {nombre_ciudad}',
                'valor': f'{presion} hPa',
                'impacto': (1005 - presion) * 2,
                'descripcion': 'Baja presión suele asociarse con mal tiempo en desarrollo.',
                'tipo': 'negativo'
            })
        
        return factores
    
    def _analizar_factores_temporales(self, datos_vuelo):
        """Analiza factores relacionados con el tiempo"""
        factores = []
        
        try:
            fecha_str = datos_vuelo.get('fecha', '')
            hora_str = datos_vuelo.get('hora', '')
            
            if fecha_str and hora_str:
                dt = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
                
                # Hora pico
                if dt.hour in self.umbrales['hora_pico_inicio']:
                    factores.append({
                        'categoria': 'Operacional',
                        'factor': 'Hora pico matutina',
                        'valor': f'{dt.hour}:00',
                        'impacto': 25,
                        'descripcion': 'Mayor congestión en aeropuertos durante horas pico.',
                        'tipo': 'negativo'
                    })
                elif dt.hour in self.umbrales['hora_pico_fin']:
                    factores.append({
                        'categoria': 'Operacional',
                        'factor': 'Hora pico vespertina',
                        'valor': f'{dt.hour}:00',
                        'impacto': 20,
                        'descripcion': 'Tráfico intenso en horario de fin de jornada.',
                        'tipo': 'negativo'
                    })
                
                # Fin de semana
                if dt.weekday() >= 5:
                    factores.append({
                        'categoria': 'Operacional',
                        'factor': 'Vuelo de fin de semana',
                        'valor': 'Sábado/Domingo',
                        'impacto': 15,
                        'descripcion': 'Mayor flujo de pasajeros recreacionales los fines de semana.',
                        'tipo': 'negativo'
                    })
                
                # Temporada alta (ejemplo: diciembre, enero)
                if dt.month in [12, 1, 7, 8]:
                    factores.append({
                        'categoria': 'Operacional',
                        'factor': 'Temporada alta de viajes',
                        'valor': f'Mes {dt.month}',
                        'impacto': 18,
                        'descripcion': 'Mayor demanda de vuelos durante temporadas vacacionales.',
                        'tipo': 'negativo'
                    })
        
        except Exception as e:
            print(f"Error analizando factores temporales: {e}")
        
        return factores
    
    def _analizar_factores_operacionales(self, datos_vuelo):
        """Analiza factores operacionales del vuelo"""
        factores = []
        
        # Ocupación del vuelo
        pasajeros = datos_vuelo.get('pasajeros', 0)
        if pasajeros > 0:
            # Asumiendo capacidad promedio de 150 pasajeros
            ocupacion_pct = (pasajeros / 150) * 100
            
            if ocupacion_pct > self.umbrales['ocupacion_alta']:
                factores.append({
                    'categoria': 'Operacional',
                    'factor': 'Alta ocupación del vuelo',
                    'valor': f'{int(ocupacion_pct)}% ocupado',
                    'impacto': (ocupacion_pct - 85) * 1.5,
                    'descripcion': 'Vuelos con alta ocupación requieren más tiempo de abordaje.',
                    'tipo': 'negativo'
                })
        
        # Ruta compleja (distancia entre ciudades)
        origen = datos_vuelo.get('origen', '').lower()
        destino = datos_vuelo.get('ciudad', '').lower()
        
        # Rutas que suelen tener más complejidad operacional
        rutas_complejas = {
            ('lima', 'cusco'): 'Ruta de alta demanda turística',
            ('lima', 'iquitos'): 'Vuelo a región selvática con condiciones variables',
            ('arequipa', 'lima'): 'Ruta con condiciones montañosas'
        }
        
        ruta_key = (origen, destino)
        if ruta_key in rutas_complejas:
            factores.append({
                'categoria': 'Operacional',
                'factor': 'Ruta operacionalmente compleja',
                'valor': f'{origen.title()} → {destino.title()}',
                'impacto': 12,
                'descripcion': rutas_complejas[ruta_key],
                'tipo': 'negativo'
            })
        
        return factores
    
    def _calcular_confianza(self, datos_prediccion):
        """Calcula el nivel de confianza de la predicción"""
        # Factores que aumentan la confianza
        confianza_base = 85
        
        # Si tenemos datos climáticos completos
        if datos_prediccion.get('datos_clima_origen') and datos_prediccion.get('datos_clima_destino'):
            confianza_base += 10
        
        # Si hay condiciones extremas claras (más fácil de predecir)
        clima_origen = datos_prediccion.get('datos_clima_origen', {})
        clima_destino = datos_prediccion.get('datos_clima_destino', {})
        
        if (clima_origen.get('precipitacion', 0) > 5 or 
            clima_destino.get('precipitacion', 0) > 5 or
            clima_origen.get('viento_velocidad', 0) > 25 or
            clima_destino.get('viento_velocidad', 0) > 25):
            confianza_base += 5
        
        return min(confianza_base, 98)
    
    def _generar_recomendaciones_especificas(self, factores_significativos):
        """Genera recomendaciones específicas basadas en los factores identificados"""
        recomendaciones = []
        
        factores_clima = [f for f in factores_significativos if 'Clima' in f['categoria']]
        factores_operacionales = [f for f in factores_significativos if 'Operacional' in f['categoria']]
        
        # Recomendaciones por clima
        if any('Lluvia' in f['factor'] for f in factores_clima):
            recomendaciones.append({
                'tipo': 'clima',
                'recomendacion': 'Permita tiempo extra para llegar al aeropuerto debido a condiciones lluviosas',
                'prioridad': 'alta'
            })
        
        if any('Viento' in f['factor'] for f in factores_clima):
            recomendaciones.append({
                'tipo': 'clima',
                'recomendacion': 'Prepárese para posibles turbulencias durante el vuelo',
                'prioridad': 'media'
            })
        
        if any('Temperatura' in f['factor'] for f in factores_clima):
            recomendaciones.append({
                'tipo': 'clima',
                'recomendacion': 'Vístase apropiadamente para las condiciones climáticas extremas',
                'prioridad': 'baja'
            })
        
        # Recomendaciones operacionales
        if any('pico' in f['factor'] for f in factores_operacionales):
            recomendaciones.append({
                'tipo': 'operacional',
                'recomendacion': 'Llegue al aeropuerto con tiempo adicional debido a la hora pico',
                'prioridad': 'alta'
            })
        
        if any('ocupación' in f['factor'] for f in factores_operacionales):
            recomendaciones.append({
                'tipo': 'operacional',
                'recomendacion': 'El vuelo tiene alta ocupación, considere hacer check-in online',
                'prioridad': 'media'
            })
        
        return recomendaciones

def generar_explicacion_simple(explicacion_completa):
    """
    Convierte la explicación completa en un formato más simple para mostrar en UI
    """
    factores_principales = explicacion_completa.get('factores_principales', [])
    resumen = explicacion_completa.get('resumen', {})
    
    if not factores_principales:
        return {
            'mensaje_principal': f"Riesgo {resumen.get('nivel', 'BAJO')} - Condiciones generalmente favorables",
            'factores_clave': ['Condiciones meteorológicas normales', 'Horario operacional estándar'],
            'recomendacion_principal': 'Manténgase informado sobre el estado de su vuelo'
        }
    
    # Tomar los 3 factores más importantes
    factores_top = factores_principales[:3]
    
    return {
        'mensaje_principal': f"Riesgo {resumen.get('nivel', 'MEDIO')} debido principalmente a:",
        'factores_clave': [f['factor'] for f in factores_top],
        'recomendacion_principal': explicacion_completa.get('recomendaciones_especificas', [{}])[0].get('recomendacion', 'Monitoree las condiciones antes del vuelo')
    }