"""
Audio Tools

Used by: TranscriberAgent
Responsibilities:
- Transcribe audio files using OpenAI Whisper API
- Validate audio file formats
- Clean up transcript text
"""
import re
from pathlib import Path


SUPPORTED_FORMATS = {".mp3", ".mp4", ".wav", ".m4a", ".webm", ".ogg", ".flac"}


def validate_audio_file(audio_path: str | Path) -> bool:
    """Return True if the file exists and has a supported audio extension."""
    path = Path(audio_path)
    return path.exists() and path.suffix.lower() in SUPPORTED_FORMATS


def transcribe_audio(
    audio_path: str | Path,
    api_key: str,
    language: str = "en",
) -> dict:
    """
    Transcribe an audio file using the OpenAI Whisper API.

    Args:
        audio_path: Path to the audio file
        api_key: OpenAI API key
        language: ISO-639-1 language code (default "en")

    Returns:
        {
            "transcript": str,
            "language": str,
            "duration_seconds": float | None,
        }
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    audio_path = Path(audio_path)

    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language=language,
            response_format="verbose_json",
        )

    transcript = response.text or ""
    duration = getattr(response, "duration", None)

    return {
        "transcript": clean_transcript(transcript),
        "language": language,
        "duration_seconds": duration,
    }


def transcribe_audio_data(
    audio_data: bytes,
    api_key: str,
    language: str = "en",
    filename: str = "audio.mp3",
) -> dict:
    """
    Transcribe in-memory audio data using the OpenAI Whisper API.

    Args:
        audio_data: Raw bytes of the audio file
        api_key: OpenAI API key
        language: ISO-639-1 language code (default "en")
        filename: Name to pass to the API (determines format inference)

    Returns:
        {
            "transcript": str,
            "language": str,
            "duration_seconds": float | None,
        }
    """
    from io import BytesIO
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    response = client.audio.transcriptions.create(
        model="whisper-1",
        file=(filename, BytesIO(audio_data)),
        language=language,
        response_format="verbose_json",
    )

    transcript = response.text or ""
    duration = getattr(response, "duration", None)

    return {
        "transcript": clean_transcript(transcript),
        "language": language,
        "duration_seconds": duration,
    }


def clean_transcript(text: str) -> str:
    """
    Clean up raw Whisper transcript output.

    - Collapse multiple spaces/newlines
    - Fix common punctuation artifacts
    """
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


def estimate_confidence(transcript: str, duration_seconds: float | None) -> float:
    """
    Heuristic confidence estimate when Whisper doesn't return word-level scores.

    Based on transcript length relative to audio duration.
    Returns a value between 0.0 and 1.0.
    """
    if not transcript or not duration_seconds or duration_seconds <= 0:
        return 0.5

    words = len(transcript.split())
    # English speech averages ~130 words per minute
    expected_words = (duration_seconds / 60) * 130
    ratio = words / expected_words if expected_words > 0 else 0

    # Confidence is high when actual word count is close to expected
    if 0.5 <= ratio <= 1.5:
        return 0.9
    elif 0.3 <= ratio < 0.5 or 1.5 < ratio <= 2.0:
        return 0.7
    else:
        return 0.5
