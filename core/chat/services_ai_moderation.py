from chat.services_ai_input import build_ai_input


def ai_analyze_message(message):
    """
    AI moderation analyzer.
    AI reads text + extracts attachments itself.
    Must return dict with keys:
      flagged: bool
      severity: safe|warn|high
      reason: str
    """

    payload = build_ai_input(message)

    # -------------------------
    # TEMPORARY AI LOGIC
    # (replace later with OpenAI / LLM)
    # -------------------------

    text = payload["text"].lower()

    # example rules (simple, deterministic)
    dangerous_keywords = [
        "kill", "suicide", "illegal", "fake report",
        "prescription fraud", "harm", "abuse"
    ]

    flagged = any(word in text for word in dangerous_keywords)

    # file-based moderation (AI *assumes* extraction)
    if payload["attachments"]:
        for a in payload["attachments"]:
            if a["name"].lower().endswith((".exe", ".bat", ".sh")):
                flagged = True

    if not flagged:
        return {
            "flagged": False,
            "severity": "safe",
            "reason": "",
            "suggested_reply": None,
        }

    # severity logic
    severity = "high" if "kill" in text or "suicide" in text else "warn"

    return {
        "flagged": True,
        "severity": severity,
        "reason": "Potentially unsafe or inappropriate content detected",
        "suggested_reply": None,
    }
