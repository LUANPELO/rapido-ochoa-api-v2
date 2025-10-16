"""
Script de prueba para la API de Rápido Ochoa
Ejecutar con: python test_api.py
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def print_separator():
    print("\n" + "="*60 + "\n")

def test_health():
    """Prueba el endpoint de salud"""
    print("🔍 Probando endpoint de salud...")
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ API funcionando correctamente")
            print(json.dumps(response.json(), indent=2))
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error al conectar con la API: {e}")
        print("\n💡 Asegúrate de que la API esté ejecutándose:")
        print("   uvicorn main:app --reload")
        return False

def test_root():
    """Prueba el endpoint raíz"""
    print("🔍 Probando endpoint raíz...")
    try:
        response = requests.get(BASE_URL, timeout=5)
        if response.status_code == 200:
            print("✅ Información de la API:")
            print(json.dumps(response.json(), indent=2))
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_consultar_guia_get(numero_guia):
    """Prueba consultar una guía con método GET"""
    print(f"🔍 Consultando guía {numero_guia} con GET...")
    print("⏳ Esto puede tomar 20-40 segundos (Selenium está trabajando)...")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/rastreo/{numero_guia}",
            timeout=60
        )
        
        if response.status_code == 200:
            print("✅ Guía encontrada:")
            datos = response.json()
            print(f"\n📦 Número de guía: {datos.get('numero_guia')}")
            print(f"👤 Remitente: {datos.get('remitente', 'N/A')}")
            print(f"👥 Destinatario: {datos.get('destinatario', 'N/A')}")
            print(f"📍 Origen: {datos.get('origen', 'N/A')}")
            print(f"📍 Destino: {datos.get('destino', 'N/A')}")
            print(f"⚖️  Peso: {datos.get('peso', 'N/A')}")
            print(f"📅 Fecha admisión: {datos.get('fecha_admision', 'N/A')}")
            print(f"📊 Estado: {datos.get('estado_actual', 'N/A')}")
            
            # Productos
            productos = datos.get('productos', [])
            if productos:
                print(f"\n📦 Productos ({len(productos)}):")
                for i, prod in enumerate(productos, 1):
                    print(f"  {i}. {prod.get('dice_contener', 'N/A')}")
                    print(f"     Empaque: {prod.get('empaque', 'N/A')}")
                    print(f"     Unidades: {prod.get('unidades', 'N/A')}")
                    print(f"     Peso: {prod.get('peso_cobrar', 'N/A')}")
            
            if datos.get('total_unidades'):
                print(f"\n   Total unidades: {datos.get('total_unidades')}")
            
            print(f"\n🔄 Trazabilidad ({len(datos.get('trazabilidad', []))} eventos):")
            for i, evento in enumerate(datos.get('trazabilidad', []), 1):
                print(f"  {i}. {evento.get('fecha', 'N/A')} - {evento.get('detalle', 'N/A')}")
                print(f"     📍 {evento.get('sede', 'N/A')}")
            
            print(f"\n🕐 Fecha consulta: {datos.get('fecha_consulta')}")
            
            print("\n📄 JSON completo:")
            print(json.dumps(datos, indent=2, ensure_ascii=False))
            return True
            
        elif response.status_code == 404:
            print(f"❌ Guía no encontrada: {numero_guia}")
            print(response.json())
            return False
        elif response.status_code == 408:
            print("❌ Timeout: La página tardó demasiado en responder")
            print(response.json())
            return False
        else:
            print(f"❌ Error {response.status_code}:")
            try:
                print(json.dumps(response.json(), indent=2))
            except:
                print(response.text)
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Timeout: La consulta tardó más de 60 segundos")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_consultar_guia_post(numero_guia):
    """Prueba consultar una guía con método POST"""
    print(f"🔍 Consultando guía {numero_guia} con POST...")
    print("⏳ Esto puede tomar 15-30 segundos...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/rastreo",
            json={"numero_guia": numero_guia},
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        if response.status_code == 200:
            print("✅ Guía encontrada (método POST)")
            datos = response.json()
            print(f"📦 Número: {datos.get('numero_guia')}")
            print(f"👤 Remitente: {datos.get('remitente', 'N/A')}")
            print(f"👥 Destinatario: {datos.get('destinatario', 'N/A')}")
            print(f"📊 Estado: {datos.get('estado_actual', 'N/A')}")
            return True
        else:
            print(f"❌ Error {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def menu():
    """Menú interactivo"""
    print("="*60)
    print("   🚀 TEST API RÁPIDO OCHOA - RASTREO DE ENCOMIENDAS")
    print("="*60)
    print("\nOpciones:")
    print("1. Probar Health Check")
    print("2. Probar endpoint raíz (información)")
    print("3. Consultar guía con GET")
    print("4. Consultar guía con POST")
    print("5. Ejecutar todas las pruebas")
    print("0. Salir")
    print("\n" + "-"*60)
    
    return input("Selecciona una opción: ").strip()

def main():
    """Función principal"""
    
    # Si se pasa un número de guía como argumento
    if len(sys.argv) > 1:
        numero_guia = sys.argv[1]
        print(f"\n🚀 Consultando guía desde argumentos: {numero_guia}")
        print_separator()
        test_consultar_guia_get(numero_guia)
        return
    
    # Modo interactivo
    while True:
        opcion = menu()
        print_separator()
        
        if opcion == "1":
            test_health()
            
        elif opcion == "2":
            test_root()
            
        elif opcion == "3":
            numero_guia = input("\nIngresa el número de guía: ").strip()
            if numero_guia:
                test_consultar_guia_get(numero_guia)
            else:
                print("❌ Debes ingresar un número de guía")
                
        elif opcion == "4":
            numero_guia = input("\nIngresa el número de guía: ").strip()
            if numero_guia:
                test_consultar_guia_post(numero_guia)
            else:
                print("❌ Debes ingresar un número de guía")
                
        elif opcion == "5":
            print("🧪 Ejecutando todas las pruebas...\n")
            
            # Test 1: Health
            test_health()
            print_separator()
            
            # Test 2: Root
            test_root()
            print_separator()
            
            # Test 3: Consultar guía
            numero_guia = input("\n¿Tienes un número de guía para probar? (Enter para saltar): ").strip()
            if numero_guia:
                test_consultar_guia_get(numero_guia)
            else:
                print("⏭️  Saltando prueba de consulta de guía")
                
        elif opcion == "0":
            print("👋 ¡Hasta luego!")
            break
            
        else:
            print("❌ Opción inválida")
        
        print_separator()
        input("Presiona Enter para continuar...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Pruebas canceladas por el usuario")
        sys.exit(0)