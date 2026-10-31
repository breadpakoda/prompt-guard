"""
Layer 3 – Contextual and Indirect Prompt Injection Detector.

Uses an LLM-as-judge pattern via LangChain's ChatOpenAI to analyze full
conversation histories for multi-turn, indirect, and context-dependent
prompt injection attempts.

Public API:
    is_danger_l3(conversation: list[dict]) -> bool
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .prompts import SYSTEM_PROMPT

# ── Load environment variables ──────────────────────────────────────────────
load_dotenv()

# ── LLM singleton (initialized once at module load) ─────────────────────────
llm = ChatOpenAI(
    base_url=os.getenv("base_url_l3"),
    api_key=os.getenv("api_l3"),
    model=os.getenv("model_l3"),
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _format_conversation(conversation: list[dict]) -> str:
    """
    Serialize the conversation list into a plain-text block for the LLM.

    Each message is rendered as:
        [ROLE]: content

    The result is clearly labelled so the LLM understands it is reading data,
    not receiving instructions.
    """
    lines = ["=== CONVERSATION TO ANALYZE ==="]
    for i, msg in enumerate(conversation, start=1):
        role = str(msg.get("role", "unknown")).upper()
        content = str(msg.get("content", ""))
        lines.append(f"[{role}]: {content}")
    lines.append("=== END OF CONVERSATION ===")
    return "\n".join(lines)


def _validate_conversation(conversation) -> bool:
    """
    Return True if conversation is a non-empty list of dicts with 'role' and
    'content' keys. Returns False for empty / structurally invalid input so
    the caller can short-circuit without an LLM call.
    """
    if not isinstance(conversation, list) or len(conversation) == 0:
        return False
    for msg in conversation:
        if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
            return False
    return True


# ── Main detection function ───────────────────────────────────────────────────

def is_danger_l3(conversation: list[dict]) -> bool:
    """
    Analyze a conversation history for prompt injection attempts.

    Args:
        conversation: A list of message dicts, each with 'role' and 'content'.
                      Example:
                          [
                              {"role": "user",      "content": "Hello"},
                              {"role": "assistant", "content": "Hi there!"},
                          ]

    Returns:
        True  – if the LLM judges the conversation as containing a prompt
                injection attempt.
        False – if the LLM judges the conversation as benign, or if the
                conversation is empty / structurally invalid.

    Raises:
        ValueError – if the LLM returns a response other than exactly "YES"
                     or "NO" (case-insensitive, stripped). This is intentional
                     fail-closed behavior; do not catch silently.
        Any LLM / network exception is propagated unchanged.
    """
    # Guard: empty or invalid input → benign by definition, no LLM call needed
    if not _validate_conversation(conversation):
        return False

    formatted = _format_conversation(conversation)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=formatted),
    ]

    response = llm.invoke(messages)
    raw = response.content.strip().upper()

    if raw == "YES":
        return True
    elif raw == "NO":
        return False
    else:
        raise ValueError(
            f"Layer 3: Unexpected LLM response — expected 'YES' or 'NO', got: {repr(raw)}"
        )

