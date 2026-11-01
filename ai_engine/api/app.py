"""
ai_engine/api/app.py
────────────────────
Main FastAPI application entry-point for the AI Engine API service.

Mounts routers:
  • /chat and /status from routes/chat.py
  • /layer3-alert and /layer3-check from routes/layer3.py

Run with:
    uvicorn ai_engine.api.app:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_engine.api.routes.chat import router as chat_router
from ai_engine.api.routes.layer3 import router as layer3_router

app = FastAPI(
    title="PromptGuard AI Engine API",
    version="2.0.0",
    description="Separated API layer coordinating LLM business logic, security layers (L1, L2, L3), and Node.js server.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(layer3_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "prompt-guard-api"}

