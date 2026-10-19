"""Typical agent prompt template: includes volatile timestamps, date, and environment metadata."""

from datetime import datetime, timezone


def render_typical_template(
    system_instructions: str,
    timestamp: str | None = None,
    session_id: str = "sess-001",
    branch: str = "main",
) -> str:
    """Renders typical real-world agent prompt with dynamic metadata prepended at the top."""
    now_iso = timestamp or datetime.now(timezone.utc).isoformat()
    return (
        f"Current time: {now_iso}\n"
        f"Active Session: {session_id}\n"
        f"Git Branch: {branch} (dirty=False)\n\n"
        "You are an expert autonomous software engineer and reasoning assistant.\n"
        "Your task is to analyze problems, use available tools, and produce correct, complete solutions.\n\n"
        f"Role Instructions:\n{system_instructions}\n\n"
        "Execution Rules:\n"
        "1. Plan before taking actions.\n"
        "2. Inspect data thoroughly using provided tools.\n"
        "3. Provide clear and verified final answers."
    )
