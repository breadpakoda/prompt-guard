"""
ai_engine/api/routes/layer3.py
──────────────────────────────
Dedicated routes for Layer-3 security alerts and standalone checks.

Exposes:
  POST /layer3-alert   – Receives alerts from bot.py and forwards to Node.js server
  POST /layer3-check   – Standalone Layer-3 scan utility endpoint
"""

import logging

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

from ai_engine.llm import conversation as conv_store
from ai_engine.llm.config import NODE_ALERT_URL

router = APIRouter(tags=["layer3"])
logger = logging.getLogger(__name__)


async def forward_prompt_injection_alert(
    conversation_id: str,
    layer1_score: float,
    layer2_score: float,
    combined_score: float,
) -> tuple[bool, int | None]:
    """Forward a detector alert without changing conversation security state."""
    if not NODE_ALERT_URL:
        logger.warning("Prompt-injection alert not forwarded: NODE_ALERT_URL is unset")
        return False, None

    payload = {
        "conversation_id": conversation_id,
        "is_malicious": True,
        "alert_type": "prompt_injection",
        "reason": "Combined Layer 1 and Layer 2 prompt-injection detection",
        "layer1_score": layer1_score,
        "layer2_score": layer2_score,
        "combined_score": combined_score,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(NODE_ALERT_URL, json=payload)
        if not response.is_success:
            logger.warning(
                "Prompt-injection alert forwarding failed with HTTP %s",
                response.status_code,
            )
        return response.is_success, response.status_code
    except httpx.HTTPError:
        logger.exception("Prompt-injection alert forwarding failed")
        return False, None


class Layer3AlertRequest(BaseModel):
    conversation_id: str
    is_malicious: bool
    messages: list[dict] = []
    reason: str | None = None

    @field_validator("conversation_id")
    @classmethod
    def conversation_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("conversation_id must not be empty")
        return v.strip()


class Layer3AlertResponse(BaseModel):
    status: str
    conversation_id: str
    is_malicious: bool
    forwarded: bool
    node_response_status: int | None = None


class Layer3CheckRequest(BaseModel):
    conversation_id: str
    messages: list[dict]

    @field_validator("conversation_id")
    @classmethod
    def conversation_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("conversation_id must not be empty")
        return v.strip()


class Layer3CheckResponse(BaseModel):
    conversation_id: str
    is_danger: bool
    security_status: str


@router.post("/layer3-alert", response_model=Layer3AlertResponse)
async def layer3_alert(alert: Layer3AlertRequest) -> Layer3AlertResponse:
    """
    Receives Layer-3 security alerts.
    Updates the local conversation security status and forwards the alert
    to the configured Node.js server endpoint.
    """
    state = await conv_store.get_or_create(alert.conversation_id)
    async with state.lock:
        if alert.is_malicious:
            state.security_status = "blocked"

    forwarded = False
    node_status_code = None

    if NODE_ALERT_URL:
        payload = {
            "conversation_id": alert.conversation_id,
            "is_malicious": alert.is_malicious,
            "reason": alert.reason or "Layer 3 contextual prompt injection detected",
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(NODE_ALERT_URL, json=payload)
                node_status_code = res.status_code
                forwarded = res.is_success
        except httpx.HTTPError:
            # The server may be offline or may reject the alert.
            logger.exception("Layer-3 alert forwarding failed")
            forwarded = False

    return Layer3AlertResponse(
        status="alert_processed",
        conversation_id=alert.conversation_id,
        is_malicious=alert.is_malicious,
        forwarded=forwarded,
        node_response_status=node_status_code,
    )


@router.post("/layer3-check", response_model=Layer3CheckResponse)
async def layer3_check(req: Layer3CheckRequest) -> Layer3CheckResponse:
    """
    Standalone Layer-3 security check utility endpoint.
    Runs is_danger_l3() on the provided messages list and updates security state.
    """
    from ai_engine.layer3 import is_danger_l3

    try:
        danger = is_danger_l3(req.messages)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "layer3_invalid_response", "message": str(exc)},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "layer3_unavailable", "message": str(exc)},
        )

    state = await conv_store.get_or_create(req.conversation_id)
    async with state.lock:
        if danger:
            state.security_status = "blocked"
        else:
            state.security_status = "clear"
        new_status = state.security_status

    return Layer3CheckResponse(
        conversation_id=req.conversation_id,
        is_danger=danger,
        security_status=new_status,
    )
