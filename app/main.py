"""
UniApply + JobApply - AI Agent Platform
"""
from fastapi import FastAPI
import logging
from app.api.webhook import router as webhook_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(
    title="UniApply",
    description="AI agent helping SA students apply to universities and find jobs via WhatsApp",
    version="2.0.0"
)

app.include_router(webhook_router, prefix="/webhook")


@app.get("/")
async def root():
    return {
        "service": "UniApply + JobApply",
        "status": "running",
        "version": "2.0.0"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
