"""
Aplicación principal FastAPI.

Este es el punto de entrada de nuestro microservicio.
FastAPI es un framework web moderno que usa async/await para
manejar muchas conexiones concurrentes eficientemente.

IMPORTANTE: Este archivo NO ejecuta inference directamente.
Solo encola trabajos en Redis y consulta resultados.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from app.models import (
    SubmitRequest,
    JobResponse,
    ResultResponse,
    JobStatus
)
from app.queue import enqueue_job, get_job_status
from app.config import settings

# Configurar logging
# logging es el módulo estándar de Python para registrar eventos
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear instancia de FastAPI
# FastAPI() crea la aplicación web
# title, description, version son metadatos para la documentación automática
app = FastAPI(
    title="Clinical Summarizer Agent",
    description="Microservicio para resumir conversaciones clínicas usando LLM",
    version="1.0.0"
)


@app.get("/")
async def root():
    """
    Endpoint raíz para verificar que el servicio está funcionando.
    
    async def indica que esta función es asíncrona.
    FastAPI puede manejar muchas de estas funciones concurrentemente
    sin bloquear el servidor.
    """
    return {
        "message": "Clinical Summarizer Agent API",
        "status": "running",
        "version": "1.0.0"
    }


@app.post("/submit", response_model=JobResponse)
async def submit_job(
    text: Optional[str] = Form(None),
    audio_file: Optional[UploadFile] = File(None)
):
    """
    Endpoint para enviar un trabajo de procesamiento.
    
    Este endpoint acepta:
    - text: Texto de la conversación clínica (opcional)
    - audio_file: Archivo de audio para transcribir (opcional)
    
    IMPORTANTE: Este endpoint NO ejecuta inference.
    Solo valida los datos, encola el trabajo en Redis, y devuelve un job_id.
    
    Args:
        text: Texto opcional de la conversación
        audio_file: Archivo de audio opcional
    
    Returns:
        JobResponse con job_id y status
    
    Explicación del flujo:
        1. Cliente envía petición POST con texto o audio
        2. Validamos que al menos uno esté presente
        3. Si hay audio, lo guardamos temporalmente (el worker lo procesará)
        4. Encolamos el trabajo en Redis
        5. Devolvemos job_id inmediatamente (sin esperar el procesamiento)
        6. El worker (proceso separado) tomará el trabajo y lo procesará
    """
    # Validar que al menos texto o audio estén presentes
    if not text and not audio_file:
        raise HTTPException(
            status_code=400,
            detail="Debe proporcionar texto o archivo de audio"
        )
    
    # Preparar datos del trabajo
    job_data = {}
    
    if text:
        job_data["text"] = text
        logger.info(f"Trabajo recibido con texto: {len(text)} caracteres")
    
    if audio_file:
        # En producción, guardaríamos el archivo en almacenamiento (S3, etc.)
        # Por ahora, guardamos el nombre del archivo
        # El worker leerá el archivo desde donde lo guardemos
        job_data["audio_filename"] = audio_file.filename
        # Leer contenido del archivo (en producción usaríamos almacenamiento externo)
        audio_content = await audio_file.read()
        job_data["audio_size"] = len(audio_content)
        logger.info(f"Trabajo recibido con audio: {audio_file.filename}, {len(audio_content)} bytes")
        
        # TODO: Guardar archivo en almacenamiento temporal o permanente
        # Por ahora, solo guardamos metadata
    
    # Encolar trabajo en Redis
    # Esta función devuelve inmediatamente, no espera el procesamiento
    try:
        job_id = enqueue_job(job_data)
        logger.info(f"Trabajo encolado: {job_id}")
        
        return JobResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            message="Trabajo encolado exitosamente. Use /result/{job_id} para consultar el resultado."
        )
    except Exception as e:
        logger.error(f"Error al encolar trabajo: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al encolar trabajo: {str(e)}"
        )


@app.get("/result/{job_id}", response_model=ResultResponse)
async def get_result(job_id: str):
    """
    Endpoint para consultar el resultado de un trabajo.
    
    El cliente puede hacer polling a este endpoint hasta que
    el trabajo esté completado.
    
    Args:
        job_id: ID del trabajo a consultar
    
    Returns:
        ResultResponse con el estado y resultado (si está disponible)
    
    Explicación:
        1. Cliente hace GET a /result/{job_id}
        2. Consultamos Redis para obtener el estado del trabajo
        3. Si está completado, también obtenemos el resultado
        4. Devolvemos el estado y resultado al cliente
    """
    try:
        job_data = get_job_status(job_id)
        
        if not job_data:
            raise HTTPException(
                status_code=404,
                detail=f"Trabajo {job_id} no encontrado"
            )
        
        # Convertir status string a enum
        status = JobStatus(job_data.get("status", "pending"))
        
        # Construir respuesta
        response = ResultResponse(
            job_id=job_id,
            status=status,
            created_at=job_data.get("created_at"),
            completed_at=job_data.get("completed_at"),
            error=job_data.get("error")
        )
        
        # Si está completado, incluir el resumen clínico
        if status == JobStatus.COMPLETED and "clinical_summary" in job_data:
            from app.models import ClinicalSummary
            response.clinical_summary = ClinicalSummary(**job_data["clinical_summary"])
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al consultar trabajo {job_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar trabajo: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """
    Endpoint de health check para monitoreo.
    
    Los sistemas de monitoreo (Kubernetes, Docker, etc.) pueden
    hacer ping a este endpoint para verificar que el servicio está vivo.
    """
    try:
        # Verificar conexión a Redis
        from app.queue import redis_client
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


# Punto de entrada cuando se ejecuta con uvicorn
# uvicorn app.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True  # Auto-reload en desarrollo
    )

