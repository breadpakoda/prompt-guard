"""
ai_engine/llm/bot.py
─────────────────────
Target-LLM business logic.  No FastAPI code lives here.

Responsibilities
────────────────
1. Initialize the target LLM singleton once at import time.
2. Run Layer-1 and Layer-2 security checks on every incoming prompt.
3. Call the target LLM with the full conversation context.
4. Maintain conversation history via conversation.py.
5. Trigger Layer-3 checks after every N messages and post a security alert
   to the API layer if an injection is detected.

Public API
──────────
    generate_response(user_prompt, conversation_id) -> dict
"""

import asyncio

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .config import (
    LLM_BASE_URL,
    LLM_API_KEY,
    LLM_MODEL,
    L3_CHECK_THRESHOLD,
    L3_WINDOW_SIZE,
    API_ALERT_URL,
)
from . import conversation as conv_store
from .ensemble import COMBINED_ALERT_THRESHOLD, combine_detector_scores

INJECTION_REFUSAL = (
    "A prompt injection attempt was detected. This request can't be fulfilled."
)

# ── Target LLM singleton (initialized once at import time) ───────────────────

_llm = ChatOpenAI(
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY,
    model=LLM_MODEL,
    max_tokens=150,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_lc_messages(history: list[dict]) -> list:
    """
    Convert plain-dict conversation history into LangChain message objects
    so the full multi-turn context is sent to the target LLM.
    """
    lc_msgs = []
    for msg in history:
        role    = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            lc_msgs.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_msgs.append(AIMessage(content=content))
        else:
            lc_msgs.append(SystemMessage(content=content))
    return lc_msgs


def _run_layer1(prompt: str) -> dict:
    """
    Run Layer-1 (DistilBERT classifier) on *prompt*.

    Returns:
        {"is_danger": bool, "attack_score": float}
    """
    from ai_engine.layer1 import is_danger
    result = is_danger(prompt)
    if hasattr(result, "attack_score"):
        attack_score = float(result.attack_score)
    elif isinstance(result, dict):
        attack_score = float(result.get("attack_score", result.get("confidence", 0.0)))
    else:
        attack_score = float(bool(result))
    is_danger = bool(result.get("is_danger", False)) if isinstance(result, dict) else bool(result)
    return {"is_danger": is_danger, "attack_score": attack_score}


def _run_layer2(prompt: str) -> dict:
    """
    Run Layer-2 (FAISS semantic similarity) on *prompt*.

    Returns:
        {"is_danger": bool, "similarity_score": float}
    """
    from ai_engine.layer2 import is_danger_l2
    result = is_danger_l2(prompt)
    if isinstance(result, dict):
        return {
            "is_danger": bool(result.get("is_malicious", result.get("is_danger", False))),
            "similarity_score": float(result.get("similarity_score", 0.0)),
        }
    return {"is_danger": bool(result), "similarity_score": float(bool(result))}


async def _post_l3_alert(conversation_id: str, is_malicious: bool, window: list[dict]) -> None:
    """
    POST a Layer-3 security alert to the API layer's /layer3-alert endpoint.

    This is a fire-and-forget call made while still inside the conversation
    lock, so timeouts are kept short.  Errors are logged but do not prevent
    the conversation from being blocked in-memory.
    """
    payload = {
        "conversation_id": conversation_id,
        "is_malicious":    is_malicious,
        "messages":        window,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(API_ALERT_URL, json=payload)
    except Exception as exc:
        # Non-fatal: in-memory block is already set; alert delivery failure
        # is logged but does not undo the block.
        print(f"[bot] L3 alert delivery failed: {exc}")


# ── Public API ────────────────────────────────────────────────────────────────

async def generate_response(user_prompt: str, conversation_id: str) -> dict:
    """
    Process one user turn and return a structured response dict.

    Pipeline
    ────────
    1. Run Layer-1 and Layer-2 checks concurrently and combine their scores.
    2. Notify and refuse the request when combined risk crosses the threshold.
    3. Acquire per-conversation lock.
    4. Append user message.
    5. Call target LLM with full history.
    6. Append assistant message.
    7. Trigger Layer-3 if threshold reached; post alert on detection.
    8. Release lock.
    9. Return result dict.

    Returns:
        {
            "conversation_id": str,
            "response":        str,
            "l1_flagged":      bool,
            "l2_flagged":      bool,
            "prompt_injection_detected": bool,
            "layer1_score":    float,
            "layer2_score":    float,
            "combined_score":  float,
            "combined_threshold": float,
            "l3_triggered":    bool,
            "l3_result":       bool | None,
        }

    Raises:
        RuntimeError – if the target LLM call fails or Layer-3 errors (fail-closed).
    """
    try:
        l1, l2 = await asyncio.gather(
            asyncio.to_thread(_run_layer1, user_prompt),
            asyncio.to_thread(_run_layer2, user_prompt),
        )
    except Exception as exc:
        raise RuntimeError(f"Layer-1/Layer-2 checks failed: {exc}") from exc

    scores = combine_detector_scores(
        float(l1.get("attack_score", l1.get("confidence", 0.0))),
        float(l2["similarity_score"]),
    )
    prompt_injection_detected = bool(scores["detected"])
    if prompt_injection_detected:
        return {
            "conversation_id": conversation_id,
            "response": INJECTION_REFUSAL,
            "l1_flagged": bool(l1["is_danger"]),
            "l2_flagged": bool(l2["is_danger"]),
            "prompt_injection_detected": True,
            "layer1_score": scores["layer1_score"],
            "layer2_score": scores["layer2_score"],
            "combined_score": scores["combined_score"],
            "combined_threshold": COMBINED_ALERT_THRESHOLD,
            "l3_triggered": False,
            "l3_result": None,
        }

    # ── Conversation lock + LLM call ─────────────────────────────────────────
    state = await conv_store.get_or_create(conversation_id)

    async with state.lock:
        conv_store.add_message(state, "user", user_prompt)

        lc_messages = _build_lc_messages(state.messages)

        try:
            llm_response = _llm.invoke(lc_messages)
            answer = llm_response.content.strip()
        except Exception as exc:
            # Roll back user message so the counter stays consistent
            state.messages.pop()
            state.message_count -= 1
            raise RuntimeError(f"Target LLM call failed: {exc}") from exc

        conv_store.add_message(state, "assistant", answer)

        # ── Layer-3 trigger ───────────────────────────────────────────────
        l3_triggered = conv_store.should_check_l3(state, L3_CHECK_THRESHOLD)
        l3_result: bool | None = None

        if l3_triggered:
            state.security_status = "pending"
            window = conv_store.get_recent(state, L3_WINDOW_SIZE)

            try:
                from ai_engine.layer3 import is_danger_l3
                l3_result = is_danger_l3(window)
            except Exception as exc:
                state.security_status = "blocked"
                conv_store.mark_check_done(state)
                raise RuntimeError(
                    f"Layer-3 check failed (conversation blocked): {exc}"
                ) from exc

            if l3_result:
                state.security_status = "blocked"
                # Post alert to API layer asynchronously (errors non-fatal)
                await _post_l3_alert(conversation_id, True, window)
            else:
                state.security_status = "clear"

            conv_store.mark_check_done(state)

    return {
        "conversation_id": conversation_id,
        "response":        answer,
        "l1_flagged":      bool(l1["is_danger"]),
        "l2_flagged":      bool(l2["is_danger"]),
        "prompt_injection_detected": False,
        "layer1_score":    scores["layer1_score"],
        "layer2_score":    scores["layer2_score"],
        "combined_score":  scores["combined_score"],
        "combined_threshold": COMBINED_ALERT_THRESHOLD,
        "l3_triggered":    l3_triggered,
        "l3_result":       l3_result,
    }
