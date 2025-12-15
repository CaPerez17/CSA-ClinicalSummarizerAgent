"""
Script de ejemplo para probar el Clinical Summarizer Agent.

Este script demuestra cómo usar la API para enviar trabajos
y consultar resultados.
"""

import requests
import time
import json

# URL base de la API
API_BASE_URL = "http://localhost:8000"


def submit_text_job(text: str) -> str:
    """
    Envía un trabajo con texto a la API.
    
    Returns:
        job_id: ID del trabajo encolado
    """
    print(f"\n📤 Enviando trabajo con texto...")
    print(f"Texto: {text[:100]}...")
    
    response = requests.post(
        f"{API_BASE_URL}/submit",
        data={"text": text}
    )
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return None
    
    result = response.json()
    job_id = result["job_id"]
    print(f"✅ Trabajo encolado. Job ID: {job_id}")
    print(f"   Estado: {result['status']}")
    print(f"   Mensaje: {result['message']}")
    
    return job_id


def check_job_status(job_id: str) -> dict:
    """
    Consulta el estado de un trabajo.
    
    Returns:
        Diccionario con el estado y resultado (si está disponible)
    """
    response = requests.get(f"{API_BASE_URL}/result/{job_id}")
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return None
    
    return response.json()


def wait_for_completion(job_id: str, max_wait: int = 300, poll_interval: int = 2):
    """
    Espera a que un trabajo se complete haciendo polling.
    
    Args:
        job_id: ID del trabajo
        max_wait: Tiempo máximo de espera en segundos
        poll_interval: Intervalo entre consultas en segundos
    
    Returns:
        Resultado del trabajo o None si falla o timeout
    """
    print(f"\n⏳ Esperando a que el trabajo se complete...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        result = check_job_status(job_id)
        
        if not result:
            print("❌ No se pudo obtener el estado del trabajo")
            return None
        
        status = result["status"]
        print(f"   Estado actual: {status}")
        
        if status == "completed":
            print("✅ Trabajo completado!")
            return result
        elif status == "failed":
            print(f"❌ Trabajo falló: {result.get('error', 'Error desconocido')}")
            return result
        
        # Esperar antes de la siguiente consulta
        time.sleep(poll_interval)
    
    print(f"⏱️  Timeout después de {max_wait} segundos")
    return None


def print_clinical_summary(result: dict):
    """
    Imprime el resumen clínico de forma legible.
    """
    if not result or result.get("status") != "completed":
        return
    
    summary = result.get("clinical_summary")
    if not summary:
        print("⚠️  No hay resumen clínico disponible")
        return
    
    print("\n" + "="*60)
    print("📋 RESUMEN CLÍNICO")
    print("="*60)
    
    # Información del paciente
    if summary.get("patient_age") or summary.get("patient_gender"):
        print("\n👤 INFORMACIÓN DEL PACIENTE:")
        if summary.get("patient_age"):
            print(f"   Edad: {summary['patient_age']} años")
        if summary.get("patient_gender"):
            print(f"   Género: {summary['patient_gender']}")
    
    # Síntomas
    symptoms = summary.get("symptoms", [])
    if symptoms:
        print("\n🩺 SÍNTOMAS:")
        for i, symptom in enumerate(symptoms, 1):
            print(f"   {i}. {symptom.get('name', 'N/A')}")
            if symptom.get("duration"):
                print(f"      Duración: {symptom['duration']}")
            if symptom.get("severity"):
                print(f"      Severidad: {symptom['severity']}")
            if symptom.get("description"):
                print(f"      Descripción: {symptom['description']}")
    
    # Factores de riesgo
    risk_factors = summary.get("risk_factors", [])
    if risk_factors:
        print("\n⚠️  FACTORES DE RIESGO:")
        for factor in risk_factors:
            print(f"   • {factor}")
    
    # Condiciones relevantes
    conditions = summary.get("relevant_conditions", [])
    if conditions:
        print("\n🏥 CONDICIONES RELEVANTES:")
        for condition in conditions:
            print(f"   • {condition}")
    
    # Resumen narrativo
    narrative = summary.get("narrative_summary", "")
    if narrative:
        print("\n📝 RESUMEN NARRATIVO:")
        print(f"   {narrative}")
    
    print("="*60 + "\n")


def main():
    """
    Función principal que demuestra el uso completo de la API.
    """
    print("="*60)
    print("🧪 EJEMPLO DE USO - Clinical Summarizer Agent")
    print("="*60)
    
    # Verificar que la API esté funcionando
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✅ API está funcionando")
        else:
            print("⚠️  API responde pero puede tener problemas")
    except requests.exceptions.ConnectionError:
        print("❌ No se puede conectar a la API. ¿Está ejecutándose?")
        print("   Ejecuta: uvicorn app.main:app --reload")
        return
    
    # Texto de ejemplo de conversación clínica
    example_text = """
    Paciente de 45 años, masculino, se presenta con dolor de cabeza 
    desde hace 3 días. El dolor es de intensidad moderada, localizado 
    en la región frontal. El paciente reporta que empeora con la luz 
    y el ruido. Tiene historial de migrañas desde los 30 años. 
    No tiene otros síntomas asociados. No ha tomado medicamentos aún.
    """
    
    # Enviar trabajo
    job_id = submit_text_job(example_text)
    if not job_id:
        return
    
    # Esperar a que se complete
    result = wait_for_completion(job_id)
    
    # Mostrar resultado
    if result:
        print_clinical_summary(result)
        
        # También mostrar JSON completo
        print("\n📄 JSON completo:")
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

