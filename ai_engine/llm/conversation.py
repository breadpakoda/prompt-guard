"""
ai_engine/llm/conversation.py
──────────────────────────────
In-memory conversation store.

Responsibilities
────────────────
• Keep a separate message list per conversation_id.
• Count total messages so the caller knows when to trigger a Layer-3 check.
• Track per-conversation security status (blocked / pending / clear).
• Provide thread-safe access via a per-conversation asyncio.Lock so that
  concurrent HTTP requests for the same conversation_id cannot race.

Security states
───────────────
  "clear"   – conversation is allowed to continue.
  "blocked" – Layer 3 detected an injection; all subsequent requests are
               rejected without calling the target LLM.
  "pending" – a Layer-3 check is in progress; new requests for this
               conversation must wait until the check finishes.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Literal

# ── Types ─────────────────────────────────────────────────────────────────────

SecurityStatus = Literal["clear", "blocked", "pending"]


@dataclass
class ConversationState:
    messages:        list[dict]    = field(default_factory=list)
    message_count:   int           = 0          # total messages ever added
    checked_up_to:   int           = 0          # message_count at last L3 check
    security_status: SecurityStatus = "clear"
    lock:            asyncio.Lock  = field(default_factory=asyncio.Lock)


# ── Store ─────────────────────────────────────────────────────────────────────

# Keyed by conversation_id (str).  Lives for the lifetime of the process.
_store: dict[str, ConversationState] = {}
_store_lock = asyncio.Lock()          # protects creation of new ConversationState objects


# ── Public API ────────────────────────────────────────────────────────────────

async def get_or_create(conversation_id: str) -> ConversationState:
    """Return the ConversationState for *conversation_id*, creating it if new."""
    async with _store_lock:
        if conversation_id not in _store:
            _store[conversation_id] = ConversationState()
        return _store[conversation_id]


def get_state(conversation_id: str) -> ConversationState | None:
    """Synchronous lookup — returns None if the conversation does not exist."""
    return _store.get(conversation_id)


def add_message(state: ConversationState, role: str, content: str) -> None:
    """
    Append one message to *state* and increment its counter.

    Must be called while holding state.lock.
    """
    state.messages.append({"role": role, "content": content})
    state.message_count += 1


def get_recent(state: ConversationState, n: int) -> list[dict]:
    """Return the *n* most-recent messages from *state* (or all if fewer than n)."""
    return state.messages[-n:]


def should_check_l3(state: ConversationState, threshold: int) -> bool:
    """
    Return True when a new Layer-3 check is due.

    A check is due when:
      • The conversation has reached or passed the threshold, AND
      • We have not already checked this exact batch
        (checked_up_to < message_count means new messages have arrived
         since the last check).
    """
    return (
        state.message_count >= threshold
        and state.message_count > state.checked_up_to
        and state.message_count % threshold == 0
    )


def mark_check_done(state: ConversationState) -> None:
    """Record that a Layer-3 check was completed at the current message_count."""
    state.checked_up_to = state.message_count

