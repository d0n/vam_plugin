"""Languages of the menu "Language" (tab Voice; Leon, 22.11.2026).

The codes are the ones xAI text to speech supports (docs.x.ai, Text to Speech > Supported Languages, read 22.11.2026):
auto plus 20 BCP-47 codes; every built-in voice speaks every one of them. The plugin's chooser shows "German (de)" etc.
and sends the code as ai.language.
"""
from __future__ import annotations

LANGUAGES: dict[str, str] = {
    "de": "German", "en": "English", "fr": "French", "es-ES": "Spanish (Spain)", "es-MX": "Spanish (Mexico)",
    "it": "Italian", "pt-BR": "Portuguese (Brazil)", "pt-PT": "Portuguese (Portugal)", "ru": "Russian", "tr": "Turkish",
    "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "hi": "Hindi", "bn": "Bengali", "id": "Indonesian",
    "vi": "Vietnamese", "ar-EG": "Arabic (Egypt)", "ar-SA": "Arabic (Saudi Arabia)", "ar-AE": "Arabic (UAE)",
}
CODES: tuple[str, ...] = ("auto", *LANGUAGES)


def name(code: str) -> str:
    """English name of a language code ("de" -> "German"); an unknown code is returned as it is."""
    for key, value in LANGUAGES.items():
        if key.lower() == (code or "").lower():
            return value
    return code


def base(code: str) -> str:
    """The plain language for speech to text ("pt-BR" -> "pt", "auto" stays)."""
    return (code or "auto").split("-")[0].lower() if code and code != "auto" else "auto"


def answer_rule(code: str) -> str:
    """The instruction line for the language model / realtime session ("" for auto)."""
    if not code or code == "auto":
        return ""
    return (f"Always answer in {name(code)}, even when the user or the app notes use other words or languages; "
            f"pronounce every word as a {name(code)} speaker would.")
