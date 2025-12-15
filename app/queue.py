"""
Módulo para manejar la cola de trabajos con Redis.

Este módulo encapsula toda la lógica de comunicación con Redis.
Redis actúa como nuestro "broker de mensajes" - un intermediario
que permite que el API y el worker se comuniquen sin estar
directamente conectados.
"""

import json
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import redis
from rq import Queue
from app.config import settings


# Conexión a Redis
# redis.Redis crea un cliente que se conecta al servidor Redis
# decode_responses=True hace que Redis devuelva strings en lugar de bytes
redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
    decode_responses=True  # Convierte bytes a strings automáticamente
)

# Cola de trabajos usando RQ (Redis Queue)
# RQ es una biblioteca que usa Redis para crear colas de trabajos
# 'clinical_jobs' es el nombre de la cola
job_queue = Queue('clinical_jobs', connection=redis_client)


def enqueue_job(job_data: Dict[str, Any]) -> str:
    """
    Encola un nuevo trabajo en Redis.
    
    Args:
        job_data: Diccionario con los datos del trabajo (texto o audio_url)
    
    Returns:
        job_id: ID único del trabajo que se puede usar para consultar resultados
    
    Explicación:
        1. Generamos un UUID único para el trabajo
        2. Guardamos los datos del trabajo en Redis con una clave única
        3. Encolamos el trabajo en la cola RQ
        4. El worker (que está escuchando la cola) tomará este trabajo y lo procesará
    """
    # Generar ID único para el trabajo
    # uuid4() genera un UUID aleatorio (muy poco probable de colisiones)
    job_id = str(uuid.uuid4())
    
    # Guardar datos del trabajo en Redis
    # Usamos un hash de Redis para almacenar metadatos del trabajo
    job_key = f"job:{job_id}"
    job_metadata = {
        "job_id": job_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "text": job_data.get("text") or "",
        "audio_filename": job_data.get("audio_filename") or "",
        "audio_url": job_data.get("audio_url") or ""
    }
    
    # Guardar en Redis con expiración de 24 horas
    # Esto previene que Redis se llene de trabajos antiguos
    redis_client.hset(job_key, mapping=job_metadata)
    redis_client.expire(job_key, timedelta(hours=24))
    
    # Encolar el trabajo en RQ
    # job_queue.enqueue() añade el trabajo a la cola
    # 'process_clinical_job' es la función que el worker ejecutará
    # job_id se pasa como argumento a esa función
    job_queue.enqueue(
        'app.worker.process_clinical_job',  # Función a ejecutar
        job_id,  # Argumento para la función
        job_timeout=300  # Timeout de 5 minutos para el trabajo
    )
    
    return job_id


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene el estado y resultado de un trabajo.
    
    Args:
        job_id: ID del trabajo a consultar
    
    Returns:
        Diccionario con el estado y resultado, o None si no existe
    
    Explicación:
        El worker guarda el resultado en Redis cuando termina.
        Esta función lee ese resultado.
    """
    job_key = f"job:{job_id}"
    
    # Verificar si el trabajo existe
    if not redis_client.exists(job_key):
        return None
    
    # Obtener todos los campos del hash
    job_data = redis_client.hgetall(job_key)
    
    # Si el trabajo está completado, también obtener el resultado
    if job_data.get("status") == "completed":
        result_key = f"result:{job_id}"
        result_data = redis_client.get(result_key)
        if result_data:
            # json.loads convierte el string JSON a un diccionario Python
            job_data["clinical_summary"] = json.loads(result_data)
    
    return job_data


def update_job_status(job_id: str, status: str, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
    """
    Actualiza el estado de un trabajo.
    
    Esta función es llamada por el worker para actualizar el progreso.
    
    Args:
        job_id: ID del trabajo
        status: Nuevo estado (processing, completed, failed)
        result: Resultado del procesamiento (si está completo)
        error: Mensaje de error (si falló)
    """
    job_key = f"job:{job_id}"
    
    # Actualizar estado
    redis_client.hset(job_key, "status", status)
    
    # Si hay un resultado, guardarlo en una clave separada
    if result:
        result_key = f"result:{job_id}"
        redis_client.setex(
            result_key,
            timedelta(hours=24),  # Expira en 24 horas
            json.dumps(result)  # Convertir dict a JSON string
        )
        redis_client.hset(job_key, "completed_at", datetime.now().isoformat())
    
    # Si hay un error, guardarlo
    if error:
        redis_client.hset(job_key, "error", error)
        redis_client.hset(job_key, "completed_at", datetime.now().isoformat())

