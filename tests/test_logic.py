from logic import (
    apply_usage,
    can_talk,
    cooldown_remaining,
    empty_permissions,
    format_update_message,
    format_update_prompt,
    get_fallback_update_message,
    message_too_long,
    should_announce_update,
    split_chunks,
    strip_mention,
)



def test_empty_allow_and_deny_lets_anyone_talk():
    assert can_talk("1", empty_permissions()) is True
    assert can_talk("1", None) is True


def test_denylist_blocks_even_if_also_allowed():
    perms = {"allowlist": ["1"], "denylist": ["1"]}
    assert can_talk("1", perms) is False


def test_allowlist_is_exclusive_when_nonempty():
    perms = {"allowlist": ["1"], "denylist": []}
    assert can_talk("1", perms) is True
    assert can_talk("2", perms) is False


def test_ids_coerced_to_str():
    assert can_talk("7", {"allowlist": [7], "denylist": []}) is True
    assert can_talk("7", {"allowlist": [], "denylist": [7]}) is False


def test_strip_mention_and_length():
    text = strip_mention("<@123> hello", "<@123>")
    assert text == "hello"
    assert message_too_long("a" * 1000) is False
    assert message_too_long("a" * 1001) is True


def test_split_chunks_discord_limit():
    assert split_chunks("hi") == ["hi"]
    chunks = split_chunks("x" * 4500, 2000)
    assert chunks == ["x" * 2000, "x" * 2000, "x" * 500]


def test_cooldown_and_token_bucket():
    now = 1_000_000.0
    assert cooldown_remaining(None, now) == 0
    assert cooldown_remaining({"cooldown_until": now + 90}, now) == 90

    after = apply_usage({"tokens": 4900}, 200, now, token_limit=5000, cooldown_duration=3600)
    assert after["tokens"] == 0
    assert after["cooldown_until"] == now + 3600
    assert cooldown_remaining(after, now) == 3600

    under = apply_usage({"tokens": 10}, 5, now, token_limit=5000, cooldown_duration=3600)
    assert under["tokens"] == 15
    assert under["cooldown_until"] == 0


def test_should_announce_update():
    assert should_announce_update(None, None) is False
    assert should_announce_update("", "") is False
    assert should_announce_update("abc", None) is True
    assert should_announce_update("abc", "") is True
    assert should_announce_update("abc", "abc") is False
    assert should_announce_update("abc", "def") is True
    assert should_announce_update(" abc \n", "abc") is False
    assert should_announce_update("abc", " def ") is True


def test_format_update_prompt():
    info = {
        "sha": "1234567890abcdef",
        "short_sha": "1234567",
        "message": "fix a bug in permissions",
        "author": "Auggie Nastic",
    }
    prompt = format_update_prompt(info)
    assert "Auggie Nastic" in prompt
    assert "1234567" in prompt
    assert "fix a bug in permissions" in prompt
    assert "Vlad" in prompt


def test_format_update_message():
    info = {
        "short_sha": "abc1234",
        "message": "updated soul personality",
        "author": "Auggie",
    }
    msg = format_update_message("oh great, another pointless reboot.", info)
    assert msg.startswith("oh great, another pointless reboot.\n\n> 📦 **Deployed:** `abc1234` — updated soul personality *(Auggie)*")

    # Empty reaction fallback to details card
    card_only = format_update_message("", info)
    assert card_only == "> 📦 **Deployed:** `abc1234` — updated soul personality *(Auggie)*"


def test_get_fallback_update_message():
    info = {
        "sha": "abcdef123456",
        "message": "rewrite logic",
        "author": "Auggie",
    }
    fallback = get_fallback_update_message(info)
    assert "auggie just pushed another update" in fallback
    assert "`abcdef1` — rewrite logic *(Auggie)*" in fallback

