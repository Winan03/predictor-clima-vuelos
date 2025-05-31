#!/usr/bin/env python3
"""
Script de configuración inicial para el proyecto de predicción de vuelos
"""

import os
import json
from firebase_service import FirebaseService

def verificar_configuracion():
    """Verifica que toda la configuración esté en orden"""
    print("🔍 Verificando configuración...")
    
    # Verificar .env
    if not os.path.exists('.env'):
        print("❌ Archivo .env no encontrado")
        return False
    
    # Verificar variables de entorno esenciales
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = [
        'OPENWEATHER_API_KEY',
        'FIREBASE_DATABASE_URL'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Variables de entorno faltantes: {missing_vars}")
        return False
    
    # Verificar credenciales de Firebase
    firebase_cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
    firebase_cred_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
    
    if not firebase_cred_path and not firebase_cred_json:
        print("❌ Credenciales de Firebase no configuradas")
        print("   Configura FIREBASE_CREDENTIALS_PATH o FIREBASE_CREDENTIALS_JSON")
        return False
    
    if firebase_cred_path and not os.path.exists(firebase_cred_path):
        print(f"❌ Archivo de credenciales Firebase no encontrado: {firebase_cred_path}")
        return False
    
    print("✅ Configuración verificada")
    return True

def test_firebase_connection():
    """Prueba la conexión con Firebase"""
    print("🔥 Probando conexión con Firebase...")
    
    try:
        firebase_service = FirebaseService()
        if firebase_service.test_connection():
            print("✅ Conexión con Firebase exitosa")
            return True
        else:
            print("❌ Error conectando con Firebase")
            return False
    except Exception as e:
        print(f"❌ Error probando Firebase: {e}")
        return False

def crear_estructura_firebase():
    """Crea la estructura inicial en Firebase"""
    print("📊 Creando estructura inicial en Firebase...")
    
    try:
        firebase_service = FirebaseService()
        
        # Crear estadísticas iniciales
        firebase_service.actualizar_estadisticas(
            predicciones_hoy=0,
            precision_modelo=98.6,
            retrasos_evitados=0,
            ahorro_estimado=0
        )
        
        print("✅ Estructura inicial creada en Firebase")
        return True
        
    except Exception as e:
        print(f"❌ Error creando estructura: {e}")
        return False

def main():
    """Función principal de configuración"""
    print("🚀 Configuración inicial del proyecto de predicción de vuelos")
    print("=" * 60)
    
    # Verificar configuración
    if not verificar_configuracion():
        print("\n❌ Configuración incompleta. Por favor revisa los pasos anteriores.")
        return
    
    # Probar Firebase
    if not test_firebase_connection():
        print("\n❌ No se pudo conectar con Firebase. Revisa tus credenciales.")
        return
    
    # Crear estructura
    if not crear_estructura_firebase():
        print("\n❌ No se pudo crear la estructura inicial.")
        return
    
    print("\n✅ ¡Configuración completada exitosamente!")
    print("\nPuedes ejecutar la aplicación con:")
    print("  python app.py")
    print("\nO en modo producción con:")
    print("  gunicorn app:app")

if __name__ == "__main__":
    main()