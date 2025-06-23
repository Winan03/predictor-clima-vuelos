# email_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from datetime import datetime
from firebase_admin import db

class EmailService:
    def __init__(self):
        # Configuración SMTP - Variables corregidas para coincidir con tu .env
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.email_user = os.getenv('SENDER_EMAIL', 'winan3715@gmail.com')  # Corregido
        self.email_password = os.getenv('SENDER_PASSWORD', 'xbmpzccihskxuzgh')  # Corregido
        self.from_name = "FlyAware - Sistema Predictivo"
        
    def obtener_pasajeros_vuelo(self, codigo_vuelo):
        """
        Obtiene todos los pasajeros con tickets confirmados para un vuelo específico
        """
        try:
            # Buscar en tickets por el código de vuelo
            tickets_ref = db.reference('tickets')
            todos_tickets = tickets_ref.get()
            
            pasajeros = []
            if todos_tickets:
                for ticket_id, ticket_data in todos_tickets.items():
                    # Verificar que el ticket esté confirmado y corresponda al vuelo
                    # Según tu estructura: estado está al nivel raíz y vuelo.numero_vuelo
                    if (ticket_data.get('estado') == 'Confirmado' and 
                        ticket_data.get('vuelo', {}).get('numero_vuelo') == codigo_vuelo):
                        
                        pasajero_info = ticket_data.get('pasajero', {})
                        if pasajero_info.get('correo'):  # Cambiado de 'email' a 'correo'
                            pasajeros.append({
                                'nombre': pasajero_info.get('nombre_completo', 'Pasajero'),  # Cambiado a 'nombre_completo'
                                'email': pasajero_info.get('correo'),  # Usando 'correo'
                                'ticket_code': ticket_data.get('codigo_ticket'),
                                'vuelo': ticket_data.get('vuelo', {}),
                                'telefono': pasajero_info.get('telefono', ''),
                                'dni': pasajero_info.get('dni', '')
                            })
            
            print(f"🔍 Encontrados {len(pasajeros)} pasajeros para el vuelo {codigo_vuelo}")
            return pasajeros
            
        except Exception as e:
            print(f"❌ Error obteniendo pasajeros del vuelo {codigo_vuelo}: {e}")
            return []
    
    def generar_template_email(self, pasajero, prediccion_data):
        """
        Genera el template HTML para el email de notificación
        """
        riesgo_color = {
            'bajo': '#28a745',
            'medio': '#ffc107', 
            'alto': '#dc3545'
        }
        
        riesgo = prediccion_data.get('riesgo', 'bajo')
        color = riesgo_color.get(riesgo, '#6c757d')
        
        # Formatear recomendaciones
        recomendaciones_html = ""
        for rec in prediccion_data.get('recomendaciones', []):
            recomendaciones_html += f"<li style='margin-bottom: 8px;'>{rec}</li>"
        
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #4a6cf7 0%, #667eea 100%); color: white; padding: 30px; text-align: center; }}
                .content {{ padding: 30px; }}
                .flight-info {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .risk-badge {{ display: inline-block; padding: 8px 16px; border-radius: 20px; color: white; font-weight: bold; background-color: {color}; }}
                .recommendations {{ background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🛩️ FlyAware - Alerta de Vuelo</h1>
                    <p>Predicción de Retraso para su Vuelo</p>
                </div>
                
                <div class="content">
                    <h2>Estimado/a {pasajero['nombre']},</h2>
                    
                    <p>Hemos generado una nueva predicción para su vuelo. Aquí están los detalles:</p>
                    
                    <div class="flight-info">
                        <h3>📋 Información del Vuelo</h3>
                        <p><strong>Número de Vuelo:</strong> {pasajero['vuelo'].get('numero_vuelo', 'N/A')}</p>
                        <p><strong>Origen:</strong> {prediccion_data.get('origen', '').title()}</p>
                        <p><strong>Destino:</strong> {prediccion_data.get('ciudad', '').title()}</p>
                        <p><strong>Fecha:</strong> {prediccion_data.get('fecha_hora', 'N/A')}</p>
                        <p><strong>Código de Ticket:</strong> {pasajero['ticket_code']}</p>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <h3>🎯 Nivel de Riesgo</h3>
                        <span class="risk-badge">{prediccion_data.get('riesgo_label', riesgo.upper())}</span>
                        <p style="margin-top: 15px; font-size: 18px;">
                            <strong>Probabilidad de Retraso: {prediccion_data.get('probabilidad_retraso', 0):.1f}%</strong>
                        </p>
                    </div>
                    
                    <div class="recommendations">
                        <h3>💡 Recomendaciones</h3>
                        <ul style="margin: 10px 0; padding-left: 20px;">
                            {recomendaciones_html}
                        </ul>
                    </div>
                    
                    <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h4>🌤️ Condiciones Climáticas</h4>
                        <p><strong>Temperatura:</strong> {prediccion_data.get('datos_clima', {}).get('temperatura', 'N/A')}°C</p>
                        <p><strong>Precipitación:</strong> {prediccion_data.get('datos_clima', {}).get('precipitacion', 'N/A')} mm</p>
                        <p><strong>Viento:</strong> {prediccion_data.get('datos_clima', {}).get('viento_velocidad', 'N/A')} km/h</p>
                    </div>
                    
                    <p style="margin-top: 30px;">
                        Manténgase informado sobre el estado de su vuelo y llegue al aeropuerto con tiempo suficiente.
                    </p>
                    
                    <p>Saludos cordiales,<br>
                    <strong>Equipo FlyAware</strong></p>
                </div>
                
                <div class="footer">
                    <p>© 2025 FlyAware - Sistema Predictivo de Vuelos</p>
                    <p>Este es un mensaje automático, por favor no responda a este correo.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_template
    
    def enviar_notificacion_vuelo(self, codigo_vuelo, prediccion_data):
        """
        Envía notificaciones por email a todos los pasajeros de un vuelo
        con asunto y etiquetas personalizadas según el nivel de riesgo
        """
        try:
            # Obtener pasajeros del vuelo
            pasajeros = self.obtener_pasajeros_vuelo(codigo_vuelo)
            
            if not pasajeros:
                print(f"⚠️ No se encontraron pasajeros para el vuelo {codigo_vuelo}")
                return {'success': False, 'message': 'No hay pasajeros registrados'}
            
            emails_enviados = 0
            emails_fallidos = []
            
            # Configurar conexión SMTP
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)

            # Obtener nivel de riesgo
            riesgo = prediccion_data.get('riesgo', 'bajo')

            # Asunto dinámico según nivel de riesgo
            if riesgo == 'bajo':
                subject = f"🟢 Vuelo {codigo_vuelo} - Sin riesgo de retraso"
            elif riesgo == 'medio':
                subject = f"🟡 Vuelo {codigo_vuelo} - Riesgo moderado de retraso"
            else:
                subject = f"🔴 Vuelo {codigo_vuelo} - Alto riesgo de retraso"

            # Etiqueta para el badge en el HTML
            riesgo_label = {
                'bajo': '🟢 BAJO',
                'medio': '🟡 MEDIO',
                'alto': '🔴 ALTO'
            }

            prediccion_data['riesgo_label'] = riesgo_label.get(riesgo, '🟤 DESCONOCIDO')

            for pasajero in pasajeros:
                try:
                    # Crear mensaje
                    msg = MIMEMultipart('alternative')
                    msg['From'] = f"{self.from_name} <{self.email_user}>"
                    msg['To'] = pasajero['email']
                    msg['Subject'] = subject

                    # Generar contenido HTML con etiqueta de riesgo
                    html_content = self.generar_template_email(pasajero, prediccion_data)

                    # Adjuntar contenido
                    html_part = MIMEText(html_content, 'html', 'utf-8')
                    msg.attach(html_part)

                    # Enviar email
                    server.send_message(msg)
                    emails_enviados += 1
                    print(f"✅ Email enviado a {pasajero['email']}")

                except Exception as e:
                    emails_fallidos.append(pasajero['email'])
                    print(f"❌ Error enviando email a {pasajero['email']}: {e}")
            
            server.quit()

            # Registrar envío en Firebase
            self.registrar_notificacion_firebase(codigo_vuelo, {
                'emails_enviados': emails_enviados,
                'emails_fallidos': emails_fallidos,
                'total_pasajeros': len(pasajeros),
                'timestamp': datetime.now().isoformat(),
                'prediccion_data': prediccion_data
            })

            return {
                'success': True,
                'emails_enviados': emails_enviados,
                'emails_fallidos': len(emails_fallidos),
                'total_pasajeros': len(pasajeros)
            }

        except Exception as e:
            print(f"❌ Error general enviando notificaciones: {e}")
            return {'success': False, 'message': str(e)}

    
    def registrar_notificacion_firebase(self, codigo_vuelo, data):
        """
        Registra el envío de notificaciones en Firebase
        """
        try:
            notificaciones_ref = db.reference('notificaciones_enviadas')
            notificaciones_ref.child(codigo_vuelo).push(data)
            
        except Exception as e:
            print(f"❌ Error registrando notificación en Firebase: {e}")

    def debug_estructura_tickets(self):
        """
        Método de debug para verificar la estructura de tickets en Firebase
        """
        try:
            tickets_ref = db.reference('tickets')
            todos_tickets = tickets_ref.get()
            
            print("🔍 DEBUG - Estructura de tickets:")
            if todos_tickets:
                for ticket_id, ticket_data in todos_tickets.items():
                    print(f"\n📋 Ticket ID: {ticket_id}")
                    print(f"  ├─ Estado: {ticket_data.get('estado')}")
                    print(f"  ├─ Código: {ticket_data.get('codigo_ticket')}")
                    
                    # Info del vuelo
                    vuelo = ticket_data.get('vuelo', {})
                    print(f"  ├─ Vuelo:")
                    print(f"  │   ├─ Número: {vuelo.get('numero_vuelo')}")
                    print(f"  │   ├─ Origen: {vuelo.get('origen')}")
                    print(f"  │   └─ Destino: {vuelo.get('destino')}")
                    
                    # Info del pasajero
                    pasajero = ticket_data.get('pasajero', {})
                    print(f"  └─ Pasajero:")
                    print(f"      ├─ Nombre: {pasajero.get('nombre_completo')}")
                    print(f"      ├─ Email: {pasajero.get('correo')}")
                    print(f"      ├─ DNI: {pasajero.get('dni')}")
                    print(f"      └─ Teléfono: {pasajero.get('telefono')}")
            else:
                print("❌ No se encontraron tickets")
                
        except Exception as e:
            print(f"❌ Error en debug: {e}")

    def test_conexion_email(self):
        """
        Método para probar la conexión con el servidor SMTP
        """
        try:
            print(f"🔄 Probando conexión SMTP...")
            print(f"📧 Servidor: {self.smtp_server}:{self.smtp_port}")
            print(f"👤 Usuario: {self.email_user}")
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            server.quit()
            
            print("✅ Conexión SMTP exitosa!")
            return True
            
        except Exception as e:
            print(f"❌ Error en conexión SMTP: {e}")
            return False