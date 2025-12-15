"""
Agente Clínico - Procesa texto usando LLM.

Este módulo contiene la lógica de "inference" - el procesamiento real
del texto usando modelos de lenguaje grandes (LLM).

El agente:
1. Transcribe audio usando Whisper (si es necesario)
2. Extrae información clínica usando un LLM
3. Estructura la información en formato FHIR-like
"""

import logging
import whisper
from typing import Optional
from openai import OpenAI

from app.models import ClinicalSummary, Symptom
from app.config import settings

logger = logging.getLogger(__name__)


class ClinicalAgent:
    """
    Agente que procesa conversaciones clínicas usando LLM.
    
    Este agente encapsula toda la lógica de inference:
    - Transcripción de audio (Whisper)
    - Extracción de información clínica (LLM)
    - Estructuración de datos (FHIR-like)
    """
    
    def __init__(self):
        """
        Inicializa el agente cargando los modelos necesarios.
        
        Esta inicialización es costosa (carga modelos grandes),
        por eso se hace una sola vez cuando se crea el agente,
        no por cada trabajo.
        """
        logger.info("Inicializando modelos...")
        
        # Inicializar Whisper para transcripción
        # whisper.load_model() carga el modelo en memoria
        # Esto puede tardar varios segundos y usar varios GB de RAM
        self.whisper_model = whisper.load_model(settings.whisper_model)
        logger.info(f"Modelo Whisper '{settings.whisper_model}' cargado")
        
        # Inicializar cliente de OpenAI para el LLM
        # OpenAI() crea un cliente que se conecta a la API de OpenAI
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY no configurada")
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        logger.info("Cliente OpenAI inicializado")
    
    def transcribe_audio(self, audio_path: str) -> str:
        """
        Transcribe audio a texto usando Whisper.
        
        Args:
            audio_path: Ruta al archivo de audio
        
        Returns:
            Texto transcrito
        
        Explicación:
            Whisper es un modelo de transcripción de OpenAI.
            self.whisper_model.transcribe() ejecuta inference en el audio.
            Esta operación puede tardar varios segundos dependiendo
            de la duración del audio y el tamaño del modelo.
        """
        logger.info(f"Transcribiendo audio: {audio_path}")
        
        # Transcribir audio
        # transcribe() ejecuta inference - procesa el audio frame por frame
        # y genera texto. Esto es CPU/GPU intensivo.
        result = self.whisper_model.transcribe(audio_path)
        
        # Extraer texto de la transcripción
        text = result["text"]
        logger.info(f"Transcripción completada: {len(text)} caracteres")
        
        return text
    
    def process_clinical_text(self, text: str) -> ClinicalSummary:
        """
        Procesa texto clínico usando LLM para extraer información estructurada.
        
        Esta es la función principal de inference del agente.
        Usa un LLM (GPT-4) para analizar el texto y extraer:
        - Síntomas
        - Duración y severidad
        - Factores de riesgo
        - Condiciones relevantes
        - Resumen narrativo
        
        Args:
            text: Texto de la conversación clínica
        
        Returns:
            ClinicalSummary con información estructurada
        
        Explicación del flujo:
            1. Construimos un prompt detallado para el LLM
            2. Enviamos el prompt a la API de OpenAI
            3. El LLM procesa el texto (inference) - esto puede tardar varios segundos
            4. Parseamos la respuesta del LLM
            5. Construimos el objeto ClinicalSummary estructurado
        """
        logger.info(f"Procesando texto clínico: {len(text)} caracteres")
        
        # Construir prompt para el LLM
        # El prompt es crítico - le dice al LLM qué hacer y cómo estructurar la respuesta
        prompt = self._build_clinical_prompt(text)
        
        # Llamar a la API de OpenAI
        # Esta es la llamada de inference - el LLM procesa el prompt
        # y genera una respuesta. Esto puede tardar 5-30 segundos dependiendo
        # de la complejidad del texto y el modelo usado.
        logger.info("Enviando prompt a LLM...")
        response = self.openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un asistente médico experto que extrae información estructurada de conversaciones clínicas."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # Baja temperatura para respuestas más consistentes
            max_tokens=2000  # Límite de tokens en la respuesta
        )
        
        # Extraer texto de la respuesta
        llm_response = response.choices[0].message.content
        logger.info(f"Respuesta del LLM recibida: {len(llm_response)} caracteres")
        
        # Parsear respuesta y construir ClinicalSummary
        # En producción, podríamos pedirle al LLM que devuelva JSON directamente
        clinical_summary = self._parse_llm_response(text, llm_response)
        
        return clinical_summary
    
    def _build_clinical_prompt(self, text: str) -> str:
        """
        Construye el prompt para el LLM.
        
        Un buen prompt es esencial para obtener resultados útiles del LLM.
        Le decimos explícitamente qué información extraer y cómo estructurarla.
        """
        prompt = f"""
Analiza la siguiente conversación clínica y extrae información estructurada.

CONVERSACIÓN:
{text}

Por favor, extrae y estructura la siguiente información:

1. INFORMACIÓN DEL PACIENTE:
   - Edad (si está disponible)
   - Género (si está disponible)

2. SÍNTOMAS:
   Para cada síntoma mencionado, identifica:
   - Nombre del síntoma
   - Duración (ej: "3 días", "2 semanas")
   - Severidad (leve, moderado, severo)
   - Descripción adicional

3. FACTORES DE RIESGO:
   Lista de factores de riesgo mencionados (ej: "fumador", "diabetes", "historial familiar")

4. CONDICIONES RELEVANTES:
   Lista de condiciones médicas mencionadas o sugeridas

5. RESUMEN NARRATIVO:
   Un resumen claro y conciso de la conversación en lenguaje médico profesional.

Responde en formato JSON con la siguiente estructura:
{{
    "patient_age": <número o null>,
    "patient_gender": "<texto o null>",
    "symptoms": [
        {{
            "name": "<nombre del síntoma>",
            "duration": "<duración>",
            "severity": "<severidad>",
            "description": "<descripción>"
        }}
    ],
    "risk_factors": ["<factor1>", "<factor2>"],
    "relevant_conditions": ["<condición1>", "<condición2>"],
    "narrative_summary": "<resumen narrativo>"
}}
"""
        return prompt
    
    def _parse_llm_response(self, original_text: str, llm_response: str) -> ClinicalSummary:
        """
        Parsea la respuesta del LLM y construye un ClinicalSummary.
        
        En producción, podríamos usar JSON mode de OpenAI para obtener
        JSON directamente, pero por ahora parseamos el texto.
        """
        import json
        import re
        
        # Intentar extraer JSON de la respuesta
        # El LLM puede devolver texto con JSON embebido
        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                logger.warning("No se pudo parsear JSON, usando valores por defecto")
                data = {}
        else:
            logger.warning("No se encontró JSON en la respuesta, usando valores por defecto")
            data = {}
        
        # Construir lista de síntomas
        symptoms = []
        for symptom_data in data.get("symptoms", []):
            symptoms.append(Symptom(
                name=symptom_data.get("name", ""),
                duration=symptom_data.get("duration"),
                severity=symptom_data.get("severity"),
                description=symptom_data.get("description")
            ))
        
        # Construir ClinicalSummary
        summary = ClinicalSummary(
            patient_age=data.get("patient_age"),
            patient_gender=data.get("patient_gender"),
            symptoms=symptoms,
            risk_factors=data.get("risk_factors", []),
            relevant_conditions=data.get("relevant_conditions", []),
            narrative_summary=data.get("narrative_summary", llm_response)  # Fallback al texto completo
        )
        
        return summary

