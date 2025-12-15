"""
Módulo para convertir datos clínicos a formato FHIR-like.

FHIR (Fast Healthcare Interoperability Resources) es un estándar
para intercambio de información médica. Este módulo convierte
nuestros ClinicalSummary a un formato compatible con FHIR.

Nota: Esta es una versión simplificada. FHIR completo es mucho más complejo.
"""

from typing import Dict, Any, List
from app.models import ClinicalSummary, Symptom


def clinical_summary_to_fhir(clinical_summary: ClinicalSummary) -> Dict[str, Any]:
    """
    Convierte un ClinicalSummary a formato FHIR-like.
    
    FHIR usa recursos estructurados. Los principales que usamos:
    - Patient: Información del paciente
    - Condition: Condiciones médicas
    - Observation: Observaciones (síntomas, signos)
    - ClinicalImpression: Impresión clínica (resumen)
    
    Args:
        clinical_summary: Resumen clínico a convertir
    
    Returns:
        Diccionario con estructura FHIR-like
    """
    fhir_bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": []
    }
    
    # Recurso Patient
    if clinical_summary.patient_age or clinical_summary.patient_gender:
        patient_resource = {
            "resource": {
                "resourceType": "Patient",
                "id": "patient-1"
            }
        }
        
        if clinical_summary.patient_age:
            # En FHIR, la edad se calcula desde la fecha de nacimiento
            # Por simplicidad, usamos una extensión
            patient_resource["resource"]["extension"] = [
                {
                    "url": "http://example.org/fhir/StructureDefinition/age",
                    "valueInteger": clinical_summary.patient_age
                }
            ]
        
        if clinical_summary.patient_gender:
            # FHIR usa: male, female, other, unknown
            gender_map = {
                "masculino": "male",
                "femenino": "female",
                "m": "male",
                "f": "female"
            }
            gender = gender_map.get(
                clinical_summary.patient_gender.lower(),
                clinical_summary.patient_gender.lower()
            )
            patient_resource["resource"]["gender"] = gender
        
        fhir_bundle["entry"].append(patient_resource)
    
    # Recurso Condition para cada condición relevante
    for idx, condition in enumerate(clinical_summary.relevant_conditions):
        condition_resource = {
            "resource": {
                "resourceType": "Condition",
                "id": f"condition-{idx + 1}",
                "code": {
                    "text": condition
                },
                "subject": {
                    "reference": "Patient/patient-1"
                },
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                            "code": "active",
                            "display": "Active"
                        }
                    ]
                }
            }
        }
        fhir_bundle["entry"].append(condition_resource)
    
    # Recurso Observation para cada síntoma
    for idx, symptom in enumerate(clinical_summary.symptoms):
        observation_resource = {
            "resource": {
                "resourceType": "Observation",
                "id": f"observation-{idx + 1}",
                "status": "final",
                "code": {
                    "text": symptom.name
                },
                "subject": {
                    "reference": "Patient/patient-1"
                },
                "valueString": symptom.description or symptom.name
            }
        }
        
        # Agregar extensión para duración si está disponible
        if symptom.duration:
            observation_resource["resource"]["extension"] = [
                {
                    "url": "http://example.org/fhir/StructureDefinition/duration",
                    "valueString": symptom.duration
                }
            ]
        
        # Agregar extensión para severidad si está disponible
        if symptom.severity:
            observation_resource["resource"]["extension"] = (
                observation_resource["resource"].get("extension", [])
            )
            observation_resource["resource"]["extension"].append({
                "url": "http://example.org/fhir/StructureDefinition/severity",
                "valueString": symptom.severity
            })
        
        fhir_bundle["entry"].append(observation_resource)
    
    # Recurso ClinicalImpression para el resumen narrativo
    clinical_impression = {
        "resource": {
            "resourceType": "ClinicalImpression",
            "id": "impression-1",
            "status": "completed",
            "subject": {
                "reference": "Patient/patient-1"
            },
            "summary": clinical_summary.narrative_summary,
            "finding": [
                {
                    "itemReference": {
                        "reference": f"Observation/observation-{idx + 1}"
                    }
                }
                for idx in range(len(clinical_summary.symptoms))
            ]
        }
    }
    fhir_bundle["entry"].append(clinical_impression)
    
    return fhir_bundle


def fhir_to_clinical_summary(fhir_bundle: Dict[str, Any]) -> ClinicalSummary:
    """
    Convierte formato FHIR-like de vuelta a ClinicalSummary.
    
    Esta función es útil si recibimos datos en formato FHIR
    y queremos convertirlos a nuestro formato interno.
    """
    from app.models import ClinicalSummary, Symptom
    
    # Extraer información del paciente
    patient = None
    for entry in fhir_bundle.get("entry", []):
        if entry.get("resource", {}).get("resourceType") == "Patient":
            patient = entry["resource"]
            break
    
    patient_age = None
    patient_gender = None
    if patient:
        # Extraer edad de extensión
        for ext in patient.get("extension", []):
            if "age" in ext.get("url", ""):
                patient_age = ext.get("valueInteger")
        patient_gender = patient.get("gender")
    
    # Extraer síntomas (Observations)
    symptoms = []
    for entry in fhir_bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Observation":
            symptom_name = resource.get("code", {}).get("text", "")
            duration = None
            severity = None
            
            # Extraer duración y severidad de extensiones
            for ext in resource.get("extension", []):
                url = ext.get("url", "")
                if "duration" in url:
                    duration = ext.get("valueString")
                elif "severity" in url:
                    severity = ext.get("valueString")
            
            symptoms.append(Symptom(
                name=symptom_name,
                duration=duration,
                severity=severity,
                description=resource.get("valueString")
            ))
    
    # Extraer condiciones
    relevant_conditions = []
    for entry in fhir_bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Condition":
            condition_text = resource.get("code", {}).get("text", "")
            if condition_text:
                relevant_conditions.append(condition_text)
    
    # Extraer resumen narrativo
    narrative_summary = ""
    for entry in fhir_bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "ClinicalImpression":
            narrative_summary = resource.get("summary", "")
            break
    
    return ClinicalSummary(
        patient_age=patient_age,
        patient_gender=patient_gender,
        symptoms=symptoms,
        risk_factors=[],  # No mapeado directamente en esta versión simplificada
        relevant_conditions=relevant_conditions,
        narrative_summary=narrative_summary
    )

