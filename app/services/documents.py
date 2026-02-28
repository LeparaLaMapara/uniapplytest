"""
Document Service - Extract structured data from matric certs, IDs and CVs
Uses Claude Vision for intelligent extraction
"""
import anthropic
import base64
import json
import logging
from app.core.config import settings
from app.services.whatsapp import download_media

logger = logging.getLogger(__name__)
claude = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def image_to_base64(image_bytes: bytes) -> str:
    return base64.standard_b64encode(image_bytes).decode("utf-8")


async def extract_matric_results(media_url: str) -> dict:
    """
    Extract matric results from image/PDF using Claude Vision.
    Returns structured dict with subjects, APS, endorsement.
    """
    try:
        image_bytes = await download_media(media_url)
        image_b64 = image_to_base64(image_bytes)

        response = claude.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": """Analyze this South African National Senior Certificate (Matric) results document.

Extract ALL information and return ONLY valid JSON:
{
  "student_name": "string or null",
  "id_number": "string or null",
  "school_name": "string or null",
  "year": "string or null",
  "passed": true/false,
  "endorsement": "Bachelor's Pass / Diploma Pass / Higher Certificate Pass / Failed",
  "subjects": [
    {
      "name": "exact subject name",
      "percentage": number,
      "symbol": "A/B/C/D/E/F/G",
      "is_home_language": true/false
    }
  ],
  "aps_score": number
}

APS calculation: Use best 6 subjects excluding Life Orientation.
Symbol to APS: A=8, B=7, C=6, D=5, E=4, F=3, G=2, H=1
Percentage to symbol: 80+=A, 70-79=B, 60-69=C, 50-59=D, 40-49=E, 30-39=F, below=G

If NOT a matric certificate: {"error": "Not a matric certificate"}"""
                    }
                ]
            }]
        )

        text = response.content[0].text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        return json.loads(text)

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error extracting matric: {e}")
        return {"error": "Could not read document clearly. Please send a clearer photo."}
    except Exception as e:
        logger.error(f"Error extracting matric results: {e}")
        return {"error": f"Failed to process document: {str(e)}"}


async def extract_id_document(media_url: str) -> dict:
    """Extract info from SA ID document"""
    try:
        image_bytes = await download_media(media_url)
        image_b64 = image_to_base64(image_bytes)

        response = claude.messages.create(
            model="claude-opus-4-6",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": """Extract info from this South African ID document. Return ONLY JSON:
{
  "full_name": "string or null",
  "id_number": "13 digit string or null",
  "date_of_birth": "YYYY-MM-DD or null",
  "gender": "Male/Female or null",
  "document_type": "Smart ID / Green Book / Other"
}
If NOT a SA ID: {"error": "Not a valid SA ID document"}"""
                    }
                ]
            }]
        )

        text = response.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)

    except Exception as e:
        logger.error(f"Error extracting ID: {e}")
        return {"error": str(e)}


async def extract_cv(media_url: str, media_type: str = "image/jpeg") -> dict:
    """
    Extract structured data from CV (image or PDF).
    Returns skills, experience, qualifications, contact info.
    """
    try:
        file_bytes = await download_media(media_url)
        file_b64 = image_to_base64(file_bytes)

        # Determine content type
        if "pdf" in media_type.lower():
            source_type = "base64"
            content_type = "application/pdf"
        else:
            source_type = "base64"
            content_type = "image/jpeg"

        response = claude.messages.create(
            model="claude-opus-4-6",
            max_tokens=3000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image" if "image" in content_type else "document",
                        "source": {
                            "type": source_type,
                            "media_type": content_type,
                            "data": file_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": """Extract ALL information from this CV/resume. Return ONLY valid JSON:
{
  "full_name": "string or null",
  "email": "string or null",
  "phone": "string or null",
  "location": "city, province or null",
  "summary": "brief professional summary or null",
  "highest_qualification": "Matric / Certificate / Diploma / Degree / Postgrad",
  "qualifications": [
    {
      "name": "qualification name",
      "institution": "school/college/university",
      "year": "year completed",
      "field": "field of study"
    }
  ],
  "experience_years": number,
  "experience": [
    {
      "title": "job title",
      "company": "company name",
      "duration": "e.g. 2 years",
      "responsibilities": ["key responsibility 1", "key responsibility 2"]
    }
  ],
  "skills": ["skill1", "skill2", "skill3"],
  "certifications": ["cert1", "cert2"],
  "languages": ["English", "Zulu"],
  "fields": ["IT", "Engineering"]
}

If NOT a CV/resume: {"error": "Not a CV"}"""
                    }
                ]
            }]
        )

        text = response.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)

    except Exception as e:
        logger.error(f"Error extracting CV: {e}")
        return {"error": str(e)}


def calculate_aps(subjects: list) -> int:
    """Calculate APS from subjects list"""
    def pct_to_aps(pct):
        if pct >= 80: return 8
        elif pct >= 70: return 7
        elif pct >= 60: return 6
        elif pct >= 50: return 5
        elif pct >= 40: return 4
        elif pct >= 30: return 3
        elif pct >= 20: return 2
        return 1

    eligible = [s for s in subjects
                if "life orientation" not in s.get("name", "").lower()]
    for s in eligible:
        s["aps"] = pct_to_aps(s.get("percentage", 0))
    eligible.sort(key=lambda x: x.get("aps", 0), reverse=True)
    return sum(s.get("aps", 0) for s in eligible[:6])
