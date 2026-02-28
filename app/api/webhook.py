"""
WhatsApp Webhook - Receives messages from Twilio and passes to agent
"""
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
import logging
from app.services.whatsapp import parse_webhook
from app.agent.agent import run_agent

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Main webhook - Twilio sends every WhatsApp message here.
    We parse it and hand it to the AI agent.
    """
    try:
        form_data = dict(await request.form())
        msg = parse_webhook(form_data)

        phone = msg["from"]
        text = msg["body"]
        media_urls = msg["media_urls"]
        media_types = msg["media_types"]

        logger.info(f"Message from {phone}: '{text[:80]}' | Files: {len(media_urls)}")

        # Hand off to AI agent - it handles everything from here
        await run_agent(
            phone=phone,
            user_message=text,
            media_urls=media_urls,
            media_types=media_types
        )

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)

    # Always return 200 to Twilio (prevents retries)
    return PlainTextResponse("OK", status_code=200)


@router.get("/whatsapp")
async def webhook_health():
    return PlainTextResponse("UniApply webhook active")
