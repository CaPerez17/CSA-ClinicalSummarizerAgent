# Clinical Summarizer Agent

Microservicio completo para resumir conversaciones clínicas usando LLM y arquitectura de cola.

## 🎯 Objetivo del Proyecto

Microservicio de producción para procesamiento de conversaciones clínicas usando LLM, implementando arquitectura de cola asíncrona para desacoplar la latencia de inference de la respuesta del API. Este proyecto sirve como referencia para construir sistemas escalables que procesan datos con modelos de IA pesados.

## 🏗️ Arquitectura

```
┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐
│ Cliente │─────▶│   API   │─────▶│  Redis  │◀─────│ Worker  │
│         │      │ FastAPI │      │  Queue  │      │(Inference)
└─────────┘      └─────────┘      └─────────┘      └─────────┘
                      │                  │                │
                      │                  │                │
                      ▼                  ▼                ▼
                 /submit          Encola trabajo    Procesa trabajo
                 /result/{id}     Almacena resultado
```

### Componentes Principales

1. **API (FastAPI)**: Recibe peticiones HTTP, encola trabajos, devuelve resultados
2. **Redis**: Cola de trabajos y almacenamiento temporal de resultados
3. **Worker**: Proceso separado que ejecuta inference (Whisper + LLM)

## 📚 Arquitectura y Decisiones de Diseño

Esta sección explica las decisiones arquitectónicas clave y los patrones implementados, útiles para desarrolladores que buscan entender o replicar este tipo de sistemas.

### 1. ¿Qué es Inference?

**Inference** es el proceso de ejecutar un modelo de IA entrenado con datos nuevos para obtener una predicción o salida.

En este proyecto:
- **Whisper**: Toma audio → genera texto (inference de transcripción)
- **LLM (GPT-4)**: Toma texto → genera resumen estructurado (inference de lenguaje)

**¿Por qué es lento?**
- Los modelos tienen millones/billones de parámetros
- Cada predicción requiere cálculos matemáticos complejos
- Puede tardar segundos o minutos dependiendo del tamaño del input

### 2. ¿Por qué NO ejecutar Inference en la API?

**Problema si ejecutamos inference en la ruta de la API:**

```python
# ❌ MAL - Bloquea el servidor
@app.post("/submit")
async def submit():
    result = model.predict(data)  # Tarda 30 segundos
    return result  # Cliente espera 30 segundos
```

**Problemas:**
- Cliente espera bloqueado (mala UX)
- Servidor no puede atender otras peticiones eficientemente
- Si hay muchos clientes, el servidor se satura
- No escala horizontalmente

**Solución con cola:**

```python
# ✅ BIEN - Responde inmediatamente
@app.post("/submit")
async def submit():
    job_id = enqueue_job(data)  # Tarda 10ms
    return {"job_id": job_id}  # Cliente recibe respuesta inmediata
```

**Ventajas:**
- API responde en milisegundos
- Worker procesa en background
- Puedes tener múltiples workers procesando en paralelo
- Escala horizontalmente añadiendo más workers

### 3. Arquitectura con Cola (Queue Architecture)

**Flujo completo:**

1. **Cliente → API (`/submit`)**:
   - Cliente envía texto o audio
   - API valida datos
   - API encola trabajo en Redis
   - API devuelve `job_id` inmediatamente

2. **Worker escucha cola**:
   - Worker está ejecutándose en un proceso separado
   - Escucha la cola de Redis constantemente
   - Cuando encuentra un trabajo, lo toma

3. **Worker procesa trabajo**:
   - Si hay audio, transcribe con Whisper
   - Procesa texto con LLM
   - Guarda resultado en Redis

4. **Cliente → API (`/result/{job_id}`)**:
   - Cliente hace polling al endpoint
   - API consulta Redis
   - Devuelve resultado cuando está listo

**Desacoplamiento:**
- API y Worker están completamente desacoplados
- Pueden ejecutarse en servidores diferentes
- Puedes escalar cada uno independientemente

### 4. FastAPI y Concurrencia

**FastAPI usa ASGI (Asynchronous Server Gateway Interface):**

```python
async def endpoint():
    # async permite que FastAPI maneje múltiples peticiones
    # sin bloquear el servidor
    result = await some_async_operation()
    return result
```

**¿Cómo funciona?**
- `async/await` permite que Python pause una función y ejecute otra
- Cuando una función espera I/O (red, disco), Python puede ejecutar otra función
- Esto permite manejar miles de conexiones concurrentes

**Limitación importante:**
- `async/await` es excelente para I/O (red, base de datos)
- **NO** paraleliza operaciones CPU-intensivas (como inference)
- Por eso necesitamos workers separados para inference

### 5. Cómo Construir un Agente Clínico

Un agente clínico es un sistema que:
1. **Entiende** lenguaje médico natural
2. **Extrae** información estructurada
3. **Estructura** datos en formato estándar

**Nuestro agente:**

```python
class ClinicalAgent:
    def process_clinical_text(self, text: str):
        # 1. Construir prompt detallado
        prompt = self._build_clinical_prompt(text)
        
        # 2. Enviar a LLM (inference)
        response = llm.generate(prompt)
        
        # 3. Parsear respuesta
        structured_data = self._parse_response(response)
        
        # 4. Validar y estructurar
        return ClinicalSummary(**structured_data)
```

**Prompt Engineering:**
- El prompt le dice al LLM exactamente qué hacer
- Incluye ejemplos y formato esperado
- Es crítico para obtener buenos resultados

### 6. Conversión a FHIR

**FHIR (Fast Healthcare Interoperability Resources)** es un estándar para intercambio de información médica.

**¿Por qué es importante?**
- Permite que diferentes sistemas médicos se comuniquen
- Estructura datos de manera consistente
- Facilita integración con sistemas hospitalarios

**Nuestro módulo FHIR:**
- Convierte `ClinicalSummary` → formato FHIR Bundle
- Crea recursos: Patient, Condition, Observation, ClinicalImpression
- Mantiene compatibilidad con sistemas FHIR

### 7. Diseño de Microservicios Escalables

**Principios aplicados:**

1. **Separación de responsabilidades**:
   - API: Maneja HTTP, valida datos
   - Worker: Ejecuta inference
   - Redis: Cola y almacenamiento

2. **Escalabilidad horizontal**:
   - Puedes ejecutar múltiples instancias del API
   - Puedes ejecutar múltiples workers
   - Redis maneja la distribución

3. **Resiliencia**:
   - Si un worker falla, otro puede tomar el trabajo
   - Si el API se cae, los trabajos siguen en la cola
   - Redis persiste datos en disco

4. **Monitoreo**:
   - Health checks (`/health`)
   - Logging estructurado
   - Estados de trabajos rastreables

### 8. WebSockets en Workflows de Salud

**¿Por qué WebSockets?**
- Permiten comunicación bidireccional en tiempo real
- Cliente puede recibir actualizaciones sin hacer polling
- Mejor UX para procesos largos

**Ejemplo de uso:**
```python
@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    # Cliente se conecta
    await websocket.accept()
    
    # Enviar actualizaciones en tiempo real
    while True:
        status = get_job_status(job_id)
        await websocket.send_json(status)
        
        if status == "completed":
            break
```

**Ventajas:**
- Cliente recibe actualizaciones automáticamente
- Menos carga en el servidor (no hay polling constante)
- Mejor experiencia de usuario

## 🚀 Instalación y Uso

### Prerrequisitos

- Python 3.11+
- Redis (o Docker)
- OpenAI API Key (para el LLM)

### Instalación Local

1. **Clonar y entrar al directorio:**
```bash
cd CSA-ClinicalSummarizerAgent
```

2. **Crear entorno virtual:**
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. **Instalar dependencias:**
```bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno:**
```bash
cp .env.example .env
# Editar .env y agregar tu OPENAI_API_KEY
```

5. **Iniciar Redis:**
```bash
# Opción 1: Docker
docker run -d -p 6379:6379 redis:7-alpine

# Opción 2: Instalación local
redis-server
```

6. **Iniciar API (en una terminal):**
```bash
uvicorn app.main:app --reload
```

7. **Iniciar Worker (en otra terminal):**
```bash
rq worker clinical_jobs
```

### Uso con Docker Compose

```bash
# Construir e iniciar todos los servicios
docker-compose up --build

# Ver logs
docker-compose logs -f

# Detener servicios
docker-compose down
```

## 📖 Uso de la API

### 1. Enviar trabajo con texto

```bash
curl -X POST "http://localhost:8000/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Paciente de 45 años, masculino, presenta dolor de cabeza desde hace 3 días, severidad moderada. Tiene historial de migrañas."
  }'
```

**Respuesta:**
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "message": "Trabajo encolado exitosamente..."
}
```

### 2. Consultar resultado

```bash
curl "http://localhost:8000/result/123e4567-e89b-12d3-a456-426614174000"
```

**Respuesta (cuando está completado):**
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "clinical_summary": {
    "patient_age": 45,
    "patient_gender": "masculino",
    "symptoms": [
      {
        "name": "dolor de cabeza",
        "duration": "3 días",
        "severity": "moderado"
      }
    ],
    "risk_factors": ["historial de migrañas"],
    "relevant_conditions": ["migraña"],
    "narrative_summary": "Paciente masculino de 45 años..."
  }
}
```

### 3. Health Check

```bash
curl "http://localhost:8000/health"
```

## 🧪 Testing

```bash
# Ejecutar tests (cuando estén implementados)
pytest tests/
```

## 📁 Estructura del Proyecto

```
CSA-ClinicalSummarizerAgent/
├── app/
│   ├── __init__.py          # Paquete Python
│   ├── main.py              # FastAPI app y endpoints
│   ├── worker.py            # Worker que ejecuta inference
│   ├── agent.py             # Agente clínico (LLM)
│   ├── fhir.py              # Conversión a formato FHIR
│   ├── models.py            # Schemas Pydantic
│   ├── queue.py             # Manejo de Redis
│   └── config.py            # Configuración
├── tests/                   # Tests unitarios e integración
├── docker-compose.yml       # Orquestación de servicios
├── Dockerfile               # Imagen Docker
├── requirements.txt         # Dependencias Python
└── README.md               # Este archivo
```

## 🚀 Mejoras y Extensiones Futuras

Este proyecto implementa una arquitectura base sólida y escalable. Para entornos de producción, considera las siguientes extensiones:

### Mejoras de Infraestructura
- **WebSocket endpoints** para streaming de resultados en tiempo real
- **Retry logic con exponential backoff** para manejo robusto de fallos
- **Métricas y monitoreo** (Prometheus + Grafana) para observabilidad
- **Rate limiting** y throttling para prevenir abuso
- **Caching inteligente** para resultados similares (Redis Cache)

### Seguridad y Compliance
- **Autenticación y autorización** (JWT tokens, OAuth2)
- **Encriptación de datos en tránsito y reposo** (TLS, encryption at rest)
- **HIPAA compliance** para manejo de datos de salud sensibles
- **Audit logging** para trazabilidad completa

### Calidad y Confiabilidad
- **Tests exhaustivos** (unitarios, integración, E2E)
- **CI/CD pipeline** con validación automática
- **Health checks avanzados** y circuit breakers
- **Graceful degradation** para escenarios de fallo

### Optimizaciones
- **Batch processing** para múltiples trabajos simultáneos
- **Model quantization** para reducir latencia de inference
- **Prompt optimization** basado en métricas de precisión
- **Distributed tracing** (OpenTelemetry) para debugging

## 📝 Consideraciones de Producción

Este microservicio sigue mejores prácticas de arquitectura de software modernas. Al desplegar en producción, asegúrate de:

- **Escalabilidad horizontal**: Configurar auto-scaling basado en métricas de cola
- **Alta disponibilidad**: Múltiples instancias con load balancing
- **Persistencia**: Backup y replicación de Redis para datos críticos
- **Monitoreo proactivo**: Alertas para latencia, errores y saturación de cola
- **Documentación API**: OpenAPI/Swagger completo para integración
- **Versionado**: Estrategia de versionado de API para compatibilidad

## 🤝 Contribuciones

Este proyecto está diseñado como referencia para desarrolladores que buscan implementar sistemas de procesamiento de IA con arquitecturas escalables. Las contribuciones son bienvenidas, especialmente en:

- Optimizaciones de performance
- Mejoras en la precisión del agente clínico
- Extensiones de funcionalidad
- Mejoras en documentación y ejemplos

## 📄 Licencia

Este proyecto está disponible bajo licencia MIT. Ver archivo LICENSE para más detalles.

