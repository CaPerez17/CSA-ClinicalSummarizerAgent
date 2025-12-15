"""
Schemas Pydantic para validación de datos.

Pydantic valida automáticamente los tipos y estructura de los datos
que entran y salen de nuestra API. Esto previene errores y hace
el código más robusto.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """
    Enum para estados del trabajo.
    
    Enum es una clase especial que define valores constantes.
    Esto previene errores de tipeo y hace el código más claro.
    """
    PENDING = "pending"      # Trabajo encolado, esperando procesamiento
    PROCESSING = "processing"  # Worker está procesando
    COMPLETED = "completed"    # Procesamiento exitoso
    FAILED = "failed"          # Error durante el procesamiento


class SubmitRequest(BaseModel):
    """
    Schema para la petición POST a /submit.
    
    BaseModel es la clase base de Pydantic que permite validación automática.
    Cuando FastAPI recibe un JSON, lo convierte a este modelo y valida
    que tenga los campos correctos y tipos correctos.
    """
    # Texto opcional - si se proporciona, se usa directamente
    text: Optional[str] = Field(
        None,
        description="Texto de la conversación clínica (opcional si se envía audio)"
    )
    
    # Audio opcional - si se proporciona, se transcribe primero
    # Nota: En producción, esto vendría como archivo multipart/form-data
    audio_url: Optional[str] = Field(
        None,
        description="URL del archivo de audio (opcional si se envía texto)"
    )


class Symptom(BaseModel):
    """
    Schema para un síntoma individual.
    
    Esta estructura representa un síntoma extraído de la conversación.
    """
    name: str = Field(..., description="Nombre del síntoma")
    duration: Optional[str] = Field(None, description="Duración del síntoma (ej: '3 días')")
    severity: Optional[str] = Field(None, description="Severidad (ej: 'moderado', 'leve', 'severo')")
    description: Optional[str] = Field(None, description="Descripción adicional")


class ClinicalSummary(BaseModel):
    """
    Schema para el resumen clínico completo.
    
    Este es el resultado final que el agente clínico produce.
    """
    # Información del paciente (si está disponible)
    patient_age: Optional[int] = Field(None, description="Edad del paciente")
    patient_gender: Optional[str] = Field(None, description="Género del paciente")
    
    # Síntomas principales
    symptoms: List[Symptom] = Field(default_factory=list, description="Lista de síntomas")
    
    # Factores de riesgo
    risk_factors: List[str] = Field(default_factory=list, description="Factores de riesgo identificados")
    
    # Condiciones relevantes
    relevant_conditions: List[str] = Field(
        default_factory=list,
        description="Condiciones médicas relevantes mencionadas o sugeridas"
    )
    
    # Resumen narrativo
    narrative_summary: str = Field(..., description="Resumen narrativo de la conversación")
    
    # Timestamp
    created_at: datetime = Field(default_factory=datetime.now, description="Fecha de creación")


class JobResponse(BaseModel):
    """
    Schema para la respuesta de /submit.
    
    Cuando el cliente envía un trabajo, le devolvemos un job_id
    que puede usar para consultar el resultado más tarde.
    """
    job_id: str = Field(..., description="ID único del trabajo")
    status: JobStatus = Field(..., description="Estado actual del trabajo")
    message: str = Field(..., description="Mensaje descriptivo")


class ResultResponse(BaseModel):
    """
    Schema para la respuesta de /result/{job_id}.
    
    Cuando el cliente consulta el resultado, le devolvemos
    el estado y (si está completo) el resumen clínico.
    """
    job_id: str = Field(..., description="ID del trabajo")
    status: JobStatus = Field(..., description="Estado del trabajo")
    clinical_summary: Optional[ClinicalSummary] = Field(
        None,
        description="Resumen clínico (solo si status=completed)"
    )
    error: Optional[str] = Field(None, description="Mensaje de error (solo si status=failed)")
    created_at: Optional[datetime] = Field(None, description="Cuándo se creó el trabajo")
    completed_at: Optional[datetime] = Field(None, description="Cuándo se completó el trabajo")

