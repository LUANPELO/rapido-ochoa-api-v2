# API Rápido Ochoa - Rastreo de Encomiendas

API REST para consultar información de encomiendas de Rápido Ochoa.

## 🚀 Características

- Consulta por número de guía
- Extrae remitente y destinatario
- Obtiene trazabilidad completa
- Tiempo de respuesta: ~12-15 segundos

## 📦 Instalación
```bash
pip install -r requirements.txt
```

## 🔧 Uso
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 📡 Endpoints

- `GET /api/rastreo/{numero_guia}` - Consultar guía
- `GET /api/health` - Estado de la API
- `GET /docs` - Documentación Swagger

## 🌐 Ejemplo
```bash
curl http://localhost:8000/api/rastreo/E121101188
```

## 📱 Integración con Flutter

Ver archivo `flutter_service.dart` para integración completa.
```

**Guardar como:** `README.md`

---

### 1.3 - Verificar archivos necesarios

Tu carpeta debe tener:
```
rapido-ochoa-api/
├── main.py ✅
├── requirements.txt ✅
├── test_api.py ✅
├── .gitignore ✅
├── README.md ✅
└── venv/ (no se sube a GitHub)