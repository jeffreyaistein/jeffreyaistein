"""
Jeffrey AIstein - Text-to-Speech Service
ElevenLabs TTS integration
"""

import re
from typing import Optional, AsyncGenerator

import httpx
import structlog

from config import settings

logger = structlog.get_logger()

# ElevenLabs API base URL
ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"

# Emoji pattern for stripping
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed characters
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols extended-A
    "\U00002600-\U000026FF"  # misc symbols
    "\U00002700-\U000027BF"  # dingbats
    "\U0001F000-\U0001F02F"  # mahjong
    "\U0001F0A0-\U0001F0FF"  # playing cards
    "]+",
    flags=re.UNICODE,
)

# Hashtag pattern
HASHTAG_PATTERN = re.compile(r"#\w+", re.UNICODE)


def sanitize_text_for_tts(text: str) -> str:
    """
    Sanitize text before sending to TTS.
    Removes emojis, hashtags, and cleans whitespace.
    """
    # Strip emojis
    text = EMOJI_PATTERN.sub("", text)
    # Strip hashtags
    text = HASHTAG_PATTERN.sub("", text)
    # Clean up whitespace
    text = " ".join(text.split())
    return text.strip()


class TTSError(Exception):
    """TTS-specific error."""
    pass


class ElevenLabsTTS:
    """ElevenLabs TTS client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        output_format: Optional[str] = None,
    ):
        self.api_key = api_key or settings.elevenlabs_api_key
        self.voice_id = voice_id or settings.elevenlabs_voice_id
        self.model_id = model_id or settings.elevenlabs_model_id
        self.output_format = output_format or settings.elevenlabs_output_format

        if not self.api_key:
            raise TTSError("ELEVENLABS_API_KEY not configured")
        if not self.voice_id:
            raise TTSError("ELEVENLABS_VOICE_ID not configured")

    async def synthesize(
        self,
        text: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        use_speaker_boost: bool = True,
    ) -> bytes:
        """
        Synthesize text to speech.

        Returns audio bytes (MP3 format by default).
        """
        # Sanitize text (enforce hard rules)
        clean_text = sanitize_text_for_tts(text)

        if not clean_text:
            raise TTSError("Text is empty after sanitization")

        # Enforce max length
        if len(clean_text) > settings.tts_max_text_length:
            clean_text = clean_text[:settings.tts_max_text_length]
            logger.warning(
                "tts_text_truncated",
                original_length=len(text),
                truncated_length=len(clean_text),
            )

        url = f"{ELEVENLABS_API_BASE}/text-to-speech/{self.voice_id}"

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        payload = {
            "text": clean_text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": use_speaker_boost,
            },
        }

        # Add output format to query params
        params = {"output_format": self.output_format}

        logger.info(
            "tts_request",
            text_length=len(clean_text),
            voice_id=self.voice_id,
            model_id=self.model_id,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                    params=params,
                )

                if response.status_code == 200:
                    logger.info(
                        "tts_success",
                        audio_size=len(response.content),
                    )
                    return response.content
                elif response.status_code == 401:
                    logger.error("elevenlabs_auth_error", status=401)
                    raise TTSError("Invalid ElevenLabs API key")
                elif response.status_code == 422:
                    try:
                        error_detail = response.json().get("detail", {})
                    except Exception:
                        error_detail = response.text[:200]
                    logger.error("elevenlabs_validation_error", status=422, detail=str(error_detail)[:200])
                    raise TTSError(f"Invalid request: {error_detail}")
                elif response.status_code == 429:
                    logger.error("elevenlabs_rate_limit", status=429)
                    raise TTSError("Rate limited by ElevenLabs")
                else:
                    # Truncate error body to avoid logging secrets
                    error_body = response.text[:500] if response.text else "No body"
                    logger.error(
                        "elevenlabs_api_error",
                        status=response.status_code,
                        body_preview=error_body,
                    )
                    raise TTSError(
                        f"ElevenLabs API error: {response.status_code}"
                    )

            except httpx.TimeoutException:
                raise TTSError("ElevenLabs API timeout")
            except httpx.RequestError as e:
                raise TTSError(f"Request error: {str(e)}")

    async def synthesize_streaming(
        self,
        text: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text to speech with streaming response.

        Yields audio chunks as they arrive.
        """
        clean_text = sanitize_text_for_tts(text)

        if not clean_text:
            raise TTSError("Text is empty after sanitization")

        if len(clean_text) > settings.tts_max_text_length:
            clean_text = clean_text[:settings.tts_max_text_length]

        url = f"{ELEVENLABS_API_BASE}/text-to-speech/{self.voice_id}/stream"

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        payload = {
            "text": clean_text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
            },
        }

        params = {"output_format": self.output_format}

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
                params=params,
            ) as response:
                if response.status_code != 200:
                    content = await response.aread()
                    raise TTSError(
                        f"ElevenLabs API error: {response.status_code} - {content.decode()}"
                    )

                async for chunk in response.aiter_bytes(chunk_size=1024):
                    yield chunk


def get_tts_client() -> ElevenLabsTTS:
    """Get a configured TTS client."""
    return ElevenLabsTTS()


def is_tts_configured() -> bool:
    """Check if TTS is properly configured."""
    return bool(
        settings.elevenlabs_api_key
        and settings.elevenlabs_voice_id
        and settings.enable_tts
    )
