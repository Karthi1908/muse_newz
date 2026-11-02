from __future__ import annotations
from typing import Tuple
import httpx
from config.settings import settings


class SpeechToTextService:
    """
    Voice Speech-to-Text Service wrapping Meta Muse Voice Transcribe
    (Constitution §2; Spec FR-002, Story 8).
    Reads MUSE_VOICE_MODEL and LLM_API_BASE_URL from .env.
    """

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "voice_topic.webm",
        fallback_hint: str | None = None,
    ) -> Tuple[bool, str, str]:
        """
        Returns (success, transcript, message).
        Rejects empty/tiny audio (<500 bytes) and tells the reader what was heard.
        """
        if not audio_bytes or len(audio_bytes) < 500:
            if fallback_hint and fallback_hint.strip():
                return True, fallback_hint.strip(), f"Heard: \"{fallback_hint.strip()}\""
            return (
                False,
                "",
                "Audio recording was empty or unclear (<0.5 seconds). Please retry speaking or type your topic change below.",
            )

        if len(audio_bytes) > 5 * 1024 * 1024:
            return (
                False,
                "",
                "Audio file exceeds the 5 MB / 30-second boundary limit. Please record a shorter command or type instead.",
            )

        if settings.DEMO_CACHE_MODE != "always" and settings.has_live_api_key:
            try:
                headers = {"Authorization": f"Bearer {settings.MODEL_API_KEY}"}
                files = {"file": (filename, audio_bytes, "audio/webm")}
                data = {"model": settings.MUSE_VOICE_MODEL}
                async with httpx.AsyncClient(timeout=settings.STT_TIMEOUT_SECONDS) as client:
                    resp = await client.post(settings.voice_transcribe_url, headers=headers, data=data, files=files)
                    resp.raise_for_status()
                    payload = resp.json()
                    text = (payload.get("text") or "").strip()
                    if not text:
                        return (
                            False,
                            "",
                            "Muse Voice Transcribe heard silence or unclear speech. Please retry or type your change.",
                        )
                    return True, text, f"Heard via {settings.MUSE_VOICE_MODEL}: \"{text}\""
            except Exception as exc:
                if fallback_hint and fallback_hint.strip():
                    return True, fallback_hint.strip(), f"Heard: \"{fallback_hint.strip()}\""
                return (
                    False,
                    "",
                    f"Voice transcription unavailable ({exc}); please retry or type your topic change directly.",
                )

        # Offline / Demo transcript resolution
        if fallback_hint and fallback_hint.strip():
            return True, fallback_hint.strip(), f"Heard: \"{fallback_hint.strip()}\""
        return (
            False,
            "",
            "No clear speech detected in demo audio stream. You can retry speaking or type your command.",
        )
