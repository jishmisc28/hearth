"""Minimal agent prompt template: pure static system instructions."""


def render_minimal_template(system_instructions: str) -> str:
    """Renders static prompt with zero volatile prefixes."""
    return (
        "You are an expert autonomous software engineer and reasoning assistant.\n"
        "Your task is to analyze problems, use available tools, and produce correct, complete solutions.\n\n"
        f"Role Instructions:\n{system_instructions}\n\n"
        "Execution Rules:\n"
        "1. Plan before taking actions.\n"
        "2. Inspect data thoroughly using provided tools.\n"
        "3. Provide clear and verified final answers."
    )
