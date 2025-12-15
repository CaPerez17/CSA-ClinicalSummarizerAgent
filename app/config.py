"""
Configuración centralizada usando Pydantic Settings.

Este archivo carga variables de entorno y las valida.
Pydantic Settings automáticamente lee el archivo .env si existe.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Clase de configuración que hereda de BaseSettings.
    
    BaseSettings automáticamente:
    1. Lee variables de entorno del sistema
    2. Lee el archivo .env si existe
    3. Valida los tipos
    4. Proporciona valores por defecto
    """
    
    # Redis configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # OpenAI configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"
    
    # Server configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Whisper configuration
    whisper_model: str = "base"  # base, small, medium, large
    
    class Config:
        """
        Configuración interna de Pydantic.
        
        env_file = ".env" le dice a Pydantic que busque un archivo .env
        case_sensitive = False permite usar mayúsculas/minúsculas indistintamente
        """
        env_file = ".env"
        case_sensitive = False


# Instancia global de configuración
# Se crea una sola vez cuando se importa el módulo
settings = Settings()

