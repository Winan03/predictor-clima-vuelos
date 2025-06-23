let datosPrediccionActual = null;
let datosClimaticosActuales = null;
let resultadoCompleto = null;

function procesarResultadoPrediccion(resultado) {
    resultadoCompleto = resultado;
    
    datosPrediccionActual = {
        probabilidad: Math.round(resultado.probabilidad_retraso),
        probabilidad_puntual: Math.round(resultado.probabilidad_puntual),
        riesgo: resultado.riesgo,
        confianza: Math.round(resultado.confianza),
        prediccion: resultado.prediccion,
        timestamp: new Date(resultado.timestamp)
    };
    
    datosClimaticosActuales = {
        temperature: resultado.datos_clima.temperatura,
        humidity: resultado.datos_clima.humedad || 65,
        wind_speed: resultado.datos_clima.viento_velocidad,
        precipitation: resultado.datos_clima.precipitacion,
        visibility: resultado.datos_clima.visibilidad,
        cloud_cover: resultado.datos_clima.nubosidad,
        pressure: resultado.datos_clima.presion,
        origen: resultado.datos_clima_origen,
        destino: resultado.datos_clima_destino
    };
    
    mostrarResumenAutomatico();
}

function mostrarResumenAutomatico() {
    const summarySection = document.getElementById('prediction-summary');
    const summaryText = document.getElementById('summary-text');
    
    if (!summarySection || !summaryText) return;
    
    const { probabilidad, riesgo } = datosPrediccionActual;
    let mensaje = '';
    let emoji = '';
    
    switch(riesgo) {
        case 'bajo':
            emoji = '✅';
            mensaje = `Condiciones favorables. ${probabilidad}% probabilidad de retraso.`;
            break;
        case 'medio':
            emoji = '⚠️';
            mensaje = `Condiciones moderadas. ${probabilidad}% probabilidad de retraso.`;
            break;
        case 'alto':
            emoji = '🚨';
            mensaje = `Alto riesgo. ${probabilidad}% probabilidad de retraso.`;
            break;
        default:
            emoji = '📊';
            mensaje = `${probabilidad}% probabilidad de retraso detectada.`;
    }
    
    summaryText.innerHTML = `${emoji} ${mensaje}`;
    summarySection.style.display = 'block';
}

function llenarResumenRiesgo() {
    const container = document.getElementById('modal-risk-summary');
    if (!datosPrediccionActual || !container) return;
    
    const { probabilidad, probabilidad_puntual, riesgo, confianza, prediccion } = datosPrediccionActual;
    let mensaje = '';
    let colorClass = '';
    
    switch(riesgo) {
        case 'bajo':
            mensaje = `🟢 RIESGO BAJO: ${probabilidad}% retraso vs ${probabilidad_puntual}% puntual. Confianza: ${confianza}%`;
            colorClass = 'low-risk';
            break;
        case 'medio':
            mensaje = `🟡 RIESGO MODERADO: ${probabilidad}% retraso vs ${probabilidad_puntual}% puntual. Confianza: ${confianza}%`;
            colorClass = 'medium-risk';
            break;
        case 'alto':
            mensaje = `🔴 RIESGO ALTO: ${probabilidad}% retraso vs ${probabilidad_puntual}% puntual. Confianza: ${confianza}%`;
            colorClass = 'high-risk';
            break;
    }
    
    mensaje += `<br><small>🤖 Predicción: ${prediccion ? 'RETRASO ESPERADO' : 'VUELO PUNTUAL'}</small>`;
    container.innerHTML = `<div class="risk-summary-content ${colorClass}">${mensaje}</div>`;
}

function llenarVariablesClave() {
    const container = document.getElementById('modal-variables');
    if (!resultadoCompleto || !container) return;
    
    const variables = [
        {
            nombre: 'Origen',
            valor: `${Math.round(datosClimaticosActuales.origen.temperatura)}°C, ${datosClimaticosActuales.origen.viento_velocidad} km/h`,
            impacto: evaluarImpactoClima(datosClimaticosActuales.origen),
            icon: '🛫'
        },
        {
            nombre: 'Destino',
            valor: `${Math.round(datosClimaticosActuales.destino.temperatura)}°C, ${datosClimaticosActuales.destino.viento_velocidad} km/h`,
            impacto: evaluarImpactoClima(datosClimaticosActuales.destino),
            icon: '🛬'
        },
        {
            nombre: 'Precipitación',
            valor: `${datosClimaticosActuales.precipitation} mm`,
            impacto: evaluarPrecipitacion(datosClimaticosActuales.precipitation),
            icon: '🌧️'
        },
        {
            nombre: 'Ruta',
            valor: `${resultadoCompleto.origen} → ${resultadoCompleto.ciudad}`,
            impacto: 'Análisis basado en datos históricos',
            icon: '✈️'
        },
        {
            nombre: 'Horario',
            valor: resultadoCompleto.fecha_hora,
            impacto: evaluarHorario(resultadoCompleto.fecha_hora),
            icon: '🕐'
        },
        {
            nombre: 'Pasajeros',
            valor: `${resultadoCompleto.pasajeros} pax`,
            impacto: evaluarPasajeros(resultadoCompleto.pasajeros),
            icon: '👥'
        }
    ];
    
    let html = '';
    variables.forEach(variable => {
        html += `
            <div class="variable-card">
                <div class="variable-header">
                    <span class="variable-icon">${variable.icon}</span>
                    <div class="variable-name">${variable.nombre}</div>
                </div>
                <div class="variable-value">${variable.valor}</div>
                <div class="variable-impact">${variable.impacto}</div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function llenarDetallesMeteorologicos() {
    const container = document.getElementById('modal-weather-details');
    if (!datosClimaticosActuales || !container) return;
    
    const html = `
        <div class="weather-section">
            <h4>🛫 ${resultadoCompleto.origen} (Origen)</h4>
            <div class="weather-grid">
                ${generarItemsClima(datosClimaticosActuales.origen)}
            </div>
        </div>
        
        <div class="weather-section">
            <h4>🛬 ${resultadoCompleto.ciudad} (Destino)</h4>
            <div class="weather-grid">
                ${generarItemsClima(datosClimaticosActuales.destino)}
            </div>
        </div>
        
        <div class="weather-section">
            <h4>🔄 Valores del Modelo</h4>
            <div class="weather-grid">
                <div class="weather-item">
                    <div class="weather-icon">🌡️</div>
                    <div class="weather-label">Temperatura</div>
                    <div class="weather-value">${Math.round(datosClimaticosActuales.temperature)}°C</div>
                </div>
                <div class="weather-item">
                    <div class="weather-icon">🌧️</div>
                    <div class="weather-label">Precipitación</div>
                    <div class="weather-value">${datosClimaticosActuales.precipitation} mm</div>
                </div>
                <div class="weather-item">
                    <div class="weather-icon">💨</div>
                    <div class="weather-label">Viento</div>
                    <div class="weather-value">${datosClimaticosActuales.wind_speed} km/h</div>
                </div>
            </div>
        </div>
    `;
    
    container.innerHTML = html;
}

function generarItemsClima(datosClima) {
    const items = [
        {
            icon: '🌡️',
            label: 'Temperatura',
            value: `${Math.round(datosClima.temperatura)}°C`,
            status: evaluarTemperatura(datosClima.temperatura)
        },
        {
            icon: '💨',
            label: 'Viento',
            value: `${datosClima.viento_velocidad} km/h`,
            status: evaluarViento(datosClima.viento_velocidad)
        },
        {
            icon: '🌧️',
            label: 'Precipitación',
            value: `${datosClima.precipitacion} mm`,
            status: evaluarPrecipitacionStatus(datosClima.precipitacion)
        },
        {
            icon: '📊',
            label: 'Presión',
            value: `${datosClima.presion} hPa`,
            status: evaluarPresion(datosClima.presion)
        }
    ];
    
    if (datosClima.visibilidad) {
        items.push({
            icon: '👁️',
            label: 'Visibilidad',
            value: `${datosClima.visibilidad} km`,
            status: evaluarVisibilidad(datosClima.visibilidad)
        });
    }
    
    if (datosClima.nubosidad !== undefined) {
        items.push({
            icon: '☁️',
            label: 'Nubosidad',
            value: `${datosClima.nubosidad}%`,
            status: evaluarNubosidad(datosClima.nubosidad)
        });
    }
    
    let html = '';
    items.forEach(item => {
        html += `
            <div class="weather-item ${item.status}">
                <div class="weather-icon">${item.icon}</div>
                <div class="weather-label">${item.label}</div>
                <div class="weather-value">${item.value}</div>
                <div class="weather-status">${obtenerTextoStatus(item.status)}</div>
            </div>
        `;
    });
    
    return html;
}

function llenarFactoresRiesgo() {
    const container = document.getElementById('modal-risk-factors');
    if (!container) return;
    
    if (!resultadoCompleto?.factores_riesgo || resultadoCompleto.factores_riesgo.length === 0) {
        container.innerHTML = '<div class="risk-factor low"><span class="risk-icon">✅</span><div class="risk-content"><strong>Sin factores de riesgo significativos</strong></div></div>';
        return;
    }
    
    let html = '';
    resultadoCompleto.factores_riesgo.forEach(factor => {
        const nivelClass = factor.nivel || 'medium';
        const icon = obtenerIconoNivel(nivelClass);
        
        html += `
            <div class="risk-factor ${nivelClass}">
                <span class="risk-icon">${icon}</span>
                <div class="risk-content">
                    <strong>${factor.factor}</strong>: ${factor.descripcion}
                    <br><small>Valor: ${factor.valor}</small>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function llenarRecomendacionesDetalladas() {
    const container = document.getElementById('modal-recommendations');
    if (!container) return;
    
    if (!resultadoCompleto?.recomendaciones || resultadoCompleto.recomendaciones.length === 0) {
        container.innerHTML = '<p>No hay recomendaciones específicas.</p>';
        return;
    }
    
    let html = '';
    resultadoCompleto.recomendaciones.forEach((rec, index) => {
        const icon = obtenerIconoRecomendacion(rec, index);
        
        html += `
            <div class="recommendation-item">
                <div class="recommendation-icon">${icon}</div>
                <div class="recommendation-content">
                    <div class="recommendation-title">Recomendación ${index + 1}</div>
                    <div class="recommendation-description">${rec}</div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function evaluarImpactoClima(datos) {
    const temp = datos.temperatura;
    const viento = datos.viento_velocidad;
    const precip = datos.precipitacion;
    
    if (temp < 5 || temp > 35 || viento > 40 || precip > 10) {
        return 'Condiciones adversas - Alto impacto';
    } else if (temp < 10 || temp > 30 || viento > 25 || precip > 5) {
        return 'Condiciones moderadas - Impacto medio';
    }
    return 'Condiciones favorables - Bajo impacto';
}

function evaluarPrecipitacion(precip) {
    if (precip > 10) return 'Lluvia intensa - Alto riesgo';
    if (precip > 5) return 'Lluvia moderada - Riesgo medio';
    if (precip > 2) return 'Lluvia ligera - Riesgo bajo';
    return 'Sin precipitación - Sin impacto';
}

function evaluarHorario(fechaHora) {
    const fecha = new Date(fechaHora);
    const hora = fecha.getHours();
    
    if (hora >= 6 && hora <= 8) return 'Hora pico matutina';
    if (hora >= 18 && hora <= 20) return 'Hora pico vespertina';
    if (hora >= 0 && hora <= 5) return 'Vuelo nocturno';
    return 'Horario regular';
}

function evaluarPasajeros(pasajeros) {
    if (pasajeros > 200) return 'Alta capacidad - Más tiempo embarque';
    if (pasajeros > 100) return 'Capacidad estándar';
    return 'Baja capacidad - Operación rápida';
}

function evaluarTemperatura(temp) {
    if (temp < 5 || temp > 35) return 'high';
    if (temp < 10 || temp > 30) return 'medium';
    return 'low';
}

function evaluarViento(wind) {
    if (wind > 40) return 'high';
    if (wind > 25) return 'medium';
    return 'low';
}

function evaluarPrecipitacionStatus(precip) {
    if (precip > 10) return 'high';
    if (precip > 2) return 'medium';
    return 'low';
}

function evaluarPresion(presion) {
    if (presion < 1000) return 'high';
    if (presion < 1010) return 'medium';
    return 'low';
}

function evaluarVisibilidad(vis) {
    if (vis < 3) return 'high';
    if (vis < 8) return 'medium';
    return 'low';
}

function evaluarNubosidad(cloud) {
    if (cloud > 80) return 'high';
    if (cloud > 50) return 'medium';
    return 'low';
}

function obtenerTextoStatus(status) {
    switch(status) {
        case 'high': return '⚠️ Alto riesgo';
        case 'medium': return '🟡 Moderado';
        case 'low': return '✅ Favorable';
        default: return '';
    }
}

function obtenerIconoNivel(nivel) {
    switch(nivel) {
        case 'alto':
        case 'high': 
            return '🚨';
        case 'medio':
        case 'medium': 
            return '⚠️';
        case 'bajo':
        case 'low': 
            return '🟡';
        default: 
            return '📊';
    }
}

function obtenerIconoRecomendacion(recomendacion, index) {
    const iconos = ['⏰', '📱', '🎒', '☔', '🧥', '🔋', '💼', '📋'];
    
    const texto = recomendacion.toLowerCase();
    if (texto.includes('tiempo')) return '⏰';
    if (texto.includes('clima')) return '🌤️';
    if (texto.includes('lluvia')) return '☔';
    if (texto.includes('aeropuerto')) return '🏢';
    if (texto.includes('vuelo')) return '✈️';
    
    return iconos[index % iconos.length];
}

function mostrarExplicacionDetallada() {
    const modal = document.getElementById('explanation-modal');
    if (!modal) return;
    
    modal.style.display = 'flex';
    llenarContenidoModal();
    document.addEventListener('keydown', cerrarModalConEsc);
}

function cerrarExplicacionDetallada() {
    const modal = document.getElementById('explanation-modal');
    if (!modal) return;
    
    modal.style.display = 'none';
    document.removeEventListener('keydown', cerrarModalConEsc);
}

function cerrarModalConEsc(event) {
    if (event.key === 'Escape') {
        cerrarExplicacionDetallada();
    }
}

function llenarContenidoModal() {
    llenarResumenRiesgo();
    llenarVariablesClave();
    llenarDetallesMeteorologicos();
    llenarFactoresRiesgo();
    llenarRecomendacionesDetalladas();
}

window.procesarResultadoPrediccion = procesarResultadoPrediccion;