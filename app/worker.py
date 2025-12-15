"""
Worker que procesa trabajos de la cola Redis.

Este es el proceso que REALMENTE ejecuta la inference.
Se ejecuta como un proceso separado del API, escuchando
la cola de Redis y procesando trabajos cuando están disponibles.

IMPORTANTE: Este proceso puede tardar minutos en procesar un trabajo,
pero el API responde en milisegundos porque no espera este proceso.
"""

import logging
import traceback
from typing import Dict, Any

from app.queue import redis_client, update_job_status, get_job_status
from app.agent import ClinicalAgent
from app.config import settings

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar el agente clínico (se carga una vez al iniciar el worker)
# Esto es costoso, por eso lo hacemos una sola vez, no por cada trabajo
clinical_agent = None


def initialize_agent():
    """
    Inicializa el agente clínico.
    
    Esta función carga los modelos necesarios (Whisper, LLM, etc.)
    Se llama una vez al iniciar el worker.
    """
    global clinical_agent
    if clinical_agent is None:
        logger.info("Inicializando agente clínico...")
        clinical_agent = ClinicalAgent()
        logger.info("Agente clínico inicializado")
    return clinical_agent


def process_clinical_job(job_id: str):
    """
    Función principal que procesa un trabajo clínico.
    
    Esta función es llamada por RQ cuando hay un trabajo en la cola.
    
    Args:
        job_id: ID del trabajo a procesar
    
    Flujo:
        1. Obtener datos del trabajo desde Redis
        2. Actualizar estado a "processing"
        3. Si hay audio, transcribirlo con Whisper
        4. Procesar texto con el agente clínico
        5. Guardar resultado en Redis
        6. Actualizar estado a "completed" o "failed"
    
    IMPORTANTE: Esta función puede tardar varios minutos.
    Por eso NO la ejecutamos en el API directamente.
    """
    try:
        logger.info(f"Iniciando procesamiento del trabajo {job_id}")
        
        # Obtener datos del trabajo
        job_data = get_job_status(job_id)
        if not job_data:
            raise ValueError(f"Trabajo {job_id} no encontrado")
        
        # Actualizar estado a "processing"
        update_job_status(job_id, "processing")
        
        # Inicializar agente si no está inicializado
        agent = initialize_agent()
        
        # Obtener texto del trabajo
        text = job_data.get("text")
        audio_filename = job_data.get("audio_filename")
        
        # Si hay audio pero no texto, transcribirlo
        if audio_filename and not text:
            logger.info(f"Transcribiendo audio: {audio_filename}")
            # TODO: Cargar archivo de audio desde almacenamiento
            # Por ahora, asumimos que el texto ya está disponible
            # En producción, aquí cargaríamos el archivo y lo transcribiríamos
            text = agent.transcribe_audio(audio_filename)
            logger.info(f"Transcripción completada: {len(text)} caracteres")
        
        if not text:
            raise ValueError("No se proporcionó texto ni audio válido")
        
        # Procesar texto con el agente clínico
        # ESTA ES LA PARTE DE INFERENCE - puede tardar varios segundos o minutos
        logger.info(f"Procesando texto con agente clínico...")
        clinical_summary = agent.process_clinical_text(text)
        logger.info(f"Procesamiento completado")
        
        # Convertir resultado a dict para guardarlo en Redis
        result_dict = clinical_summary.model_dump() if hasattr(clinical_summary, 'model_dump') else clinical_summary.dict()
        
        # Guardar resultado y actualizar estado
        update_job_status(job_id, "completed", result=result_dict)
        logger.info(f"Trabajo {job_id} completado exitosamente")
        
        return result_dict
        
    except Exception as e:
        # Si hay un error, guardarlo y actualizar estado
        error_message = f"Error procesando trabajo: {str(e)}\n{traceback.format_exc()}"
        logger.error(f"Error en trabajo {job_id}: {error_message}")
        update_job_status(job_id, "failed", error=error_message)
        raise  # Re-lanzar para que RQ sepa que falló


# Este bloque solo se ejecuta si ejecutamos este archivo directamente
# Normalmente, RQ ejecutará este worker con: rq worker clinical_jobs
if __name__ == "__main__":
    from rq import Worker, Queue, Connection
    
    # Conectar a Redis y escuchar la cola 'clinical_jobs'
    with Connection(redis_client):
        worker = Worker(Queue('clinical_jobs'))
        logger.info("Worker iniciado. Escuchando cola 'clinical_jobs'...")
        worker.work()  # Esto bloquea y procesa trabajos indefinidamente

