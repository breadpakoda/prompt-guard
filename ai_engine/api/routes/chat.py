"""
ai_engine/api/routes/chat.py
────────────────────────────
Chat routes for the FastAPI application.

Exposes:
  POST /chat
  GET  /status/{conversation_id}
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

from ai_engine.llm import conversation as conv_store
from ai_engine.llm.bot import generate_response
from ai_engine.api.routes.layer3 import forward_prompt_injection_alert

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    prompt: str
    conversation_id: str

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("prompt must not be empty")
        return v.strip()

    @field_validator("conversation_id")
    @classmethod
    def conversation_id_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("conversation_id must not be empty")
        return v.strip()


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    l1_flagged: bool = False
    l2_flagged: bool = False
    prompt_injection_detected: bool = False
    layer1_score: float = 0.0
    layer2_score: float = 0.0
    combined_score: float = 0.0
    combined_threshold: float = 0.5
    alert_forwarded: bool = False
    l3_triggered: bool = False
    l3_result: bool | None = None


class StatusResponse(BaseModel):
    conversation_id: str
    security_status: str
    message_count: int


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """
    Main chat route.
    1. Checks if the conversation is blocked or pending security analysis.
    2. Calls generate_response(), which scores Layers 1 and 2 concurrently.
    3. For a detector alert, forwards a notification without blocking the conversation.
    4. Returns response JSON or a structured error.
    """
    existing = conv_store.get_state(req.conversation_id)
    if existing is not None:
        async with existing.lock:
            status_now = existing.security_status

        if status_now == "blocked":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "conversation_blocked",
                    "message": (
                        "This conversation has been blocked because a prompt "
                        "injection attempt was detected. Please start a new conversation."
                    ),
                },
            )

        if status_now == "pending":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "security_check_in_progress",
                    "message": (
                        "A security check is currently in progress for this "
                        "conversation. Please retry in a moment."
                    ),
                },
            )

    try:
        result = await generate_response(
            user_prompt=req.prompt,
            conversation_id=req.conversation_id,
        )
    except ValueError as exc:
        err_msg = str(exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": err_msg},
        )
    except RuntimeError as exc:
        msg = str(exc)
        if "blocked" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "conversation_blocked",
                    "message": msg,
                },
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "llm_error",
                "message": msg,
            },
        )

    if result["prompt_injection_detected"]:
        forwarded, _ = await forward_prompt_injection_alert(
            conversation_id=req.conversation_id,
            layer1_score=result["layer1_score"],
            layer2_score=result["layer2_score"],
            combined_score=result["combined_score"],
        )
        result["alert_forwarded"] = forwarded

    return ChatResponse(**result)


@router.get("/status/{conversation_id}", response_model=StatusResponse)
async def get_status(conversation_id: str) -> StatusResponse:
    """Return security status and total message count for a given conversation."""
    state = conv_store.get_state(conversation_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": f"Conversation '{conversation_id}' not found"},
        )

    return StatusResponse(
        conversation_id=conversation_id,
        security_status=state.security_status,
        message_count=state.message_count,
    )
