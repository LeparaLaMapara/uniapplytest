"""
WhatsApp Service - Send and receive messages via Twilio
"""
from twilio.rest import Client
import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_client() -> Client:
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


async def send_message(to: str, text: str) -> bool:
    """Send WhatsApp message to student"""
    try:
        client = get_client()
        if not to.startswith("whatsapp:"):
            to = f"whatsapp:{to}"

        # Split long messages (WhatsApp 4096 char limit)
        chunks = split_message(text)
        for chunk in chunks:
            client.messages.create(
                from_=settings.TWILIO_WHATSAPP_NUMBER,
                body=chunk,
                to=to
            )
        return True
    except Exception as e:
        logger.error(f"Failed to send message to {to}: {e}")
        return False


def split_message(text: str, max_len: int = 4000) -> list:
    """Split long messages into chunks"""
    if len(text) <= max_len:
        return [text]
    
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            if current:
                chunks.append(current.strip())
            current = line
        else:
            current += ("\n" if current else "") + line
    if current:
        chunks.append(current.strip())
    return chunks


async def download_media(url: str) -> bytes:
    """Download media file from Twilio (requires auth)"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        )
        response.raise_for_status()
        return response.content


def parse_webhook(form_data: dict) -> dict:
    """Parse incoming Twilio webhook into clean dict"""
    num_media = int(form_data.get("NumMedia", 0))
    return {
        "from": form_data.get("From", ""),
        "body": form_data.get("Body", "").strip(),
        "num_media": num_media,
        "media_urls": [form_data.get(f"MediaUrl{i}", "") for i in range(num_media)],
        "media_types": [form_data.get(f"MediaContentType{i}", "") for i in range(num_media)],
        "profile_name": form_data.get("ProfileName", ""),
    }
