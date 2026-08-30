"""Pure helpers for permissions, cooldowns, and Discord message limits.

Kept free of discord/openai imports so tests and CI never need tokens.
"""

from __future__ import annotations

from typing import Any


def empty_permissions() -> dict[str, list[str]]:
    return {"allowlist": [], "denylist": []}


def can_talk(user_id: str, perms: dict[str, Any] | None) -> bool:
    """Denylist always wins. A non-empty allowlist is exclusive."""
    perms = perms or empty_permissions()
    uid = str(user_id)
    denylist = [str(x) for x in (perms.get("denylist") or [])]
    if uid in denylist:
        return False
    allowlist = [str(x) for x in (perms.get("allowlist") or [])]
    if allowlist and uid not in allowlist:
        return False
    return True


def strip_mention(content: str, mention: str) -> str:
    return content.replace(mention, "").strip()


def message_too_long(text: str, limit: int = 1000) -> bool:
    return len(text) > limit


def split_chunks(text: str, limit: int = 2000) -> list[str]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    if text == "":
        return [""]
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def cooldown_remaining(user_usage: dict[str, Any] | None, now: float) -> int:
    if not user_usage:
        return 0
    until = float(user_usage.get("cooldown_until") or 0)
    remaining = int(until - now)
    return remaining if remaining > 0 else 0


def apply_usage(
    user_usage: dict[str, Any] | None,
    tokens_used: int,
    now: float,
    token_limit: int,
    cooldown_duration: int,
) -> dict[str, Any]:
    updated = {
        "tokens": int((user_usage or {}).get("tokens") or 0),
        "cooldown_until": float((user_usage or {}).get("cooldown_until") or 0),
    }
    updated["tokens"] += max(0, int(tokens_used))
    if token_limit > 0 and updated["tokens"] >= token_limit:
        updated["cooldown_until"] = now + cooldown_duration
        updated["tokens"] = 0
    return updated
