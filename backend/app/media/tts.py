"""Text-to-Speech using FREE providers.

- gtts : Google Translate TTS (no key, many Indian languages)
- edge : Microsoft Edge neural voices (no key, very natural) -- free public
- coqui: fully offline neural TTS (optional heavy install)

All return a path to an audio file.
"""
from __future__ import annotations

from pathlib import Path

# language name -> (gtts code, edge voice)
LANG_MAP = {
    "english": ("en", "en-US-AriaNeural"),
    "hindi": ("hi", "hi-IN-SwaraNeural"),
    "hinglish": ("hi", "hi-IN-SwaraNeural"),
    "tamil": ("ta", "ta-IN-PallaviNeural"),
    "telugu": ("te", "te-IN-ShrutiNeural"),
    "kannada": ("kn", "kn-IN-SapnaNeural"),
    "malayalam": ("ml", "ml-IN-SobhanaNeural"),
    "marathi": ("mr", "mr-IN-AarohiNeural"),
    "gujarati": ("gu", "gu-IN-DhwaniNeural"),
    "bengali": ("bn", "bn-IN-TanishaaNeural"),
    "punjabi": ("pa", "pa-IN-OjasNeural"),
    "urdu": ("ur", "ur-IN-GulNeural"),
    "spanish": ("es", "es-ES-ElviraNeural"),
    "french": ("fr", "fr-FR-DeniseNeural"),
    "german": ("de", "de-DE-KatjaNeural"),
    "arabic": ("ar", "ar-SA-ZariyahNeural"),
}


def _resolve(language: str) -> tuple[str, str]:
    return LANG_MAP.get(language.strip().lower(), ("en", "en-US-AriaNeural"))


def synthesize(text: str, language: str, out_path: str | Path, provider: str) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    provider = provider.lower()
    gcode, evoice = _resolve(language)
    text = (text or "").strip() or "..."

    if provider == "edge":
        return _edge(text, evoice, out_path.with_suffix(".mp3"))
    if provider == "coqui":
        try:
            return _coqui(text, out_path.with_suffix(".wav"))
        except Exception:
            pass  # fall back to gtts
    return _gtts(text, gcode, out_path.with_suffix(".mp3"))


def _gtts(text: str, code: str, out: Path) -> Path:
    from gtts import gTTS

    try:
        gTTS(text=text, lang=code).save(str(out))
    except Exception:
        gTTS(text=text, lang="en").save(str(out))
    return out


def _edge(text: str, voice: str, out: Path) -> Path:
    import asyncio

    import edge_tts

    async def _run():
        await edge_tts.Communicate(text, voice).save(str(out))

    asyncio.run(_run())
    return out


def _coqui(text: str, out: Path) -> Path:
    from TTS.api import TTS  # heavy, optional

    tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
    tts.tts_to_file(text=text, file_path=str(out))
    return out