"""
Transcriber Agent

Converts audio to text using OpenAI Whisper.

Input: {"audio_path": "...", "language": "en"}
Output: {"transcript": "...", "confidence": 0.95}
"""
from typing import Dict, Any
from agents.base_agent import BaseAgent


class TranscriberAgent(BaseAgent):
    """Transcriber Agent - Converts speech to text."""

    def __init__(self, sector=None):
        super().__init__("TranscriberAgent", sector)

    def validate_input(self, input_data: Any) -> bool:
        if not isinstance(input_data, dict):
            return False
        return "audio_path" in input_data or "audio_data" in input_data

    def execute(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from tools.audio_tools import (
            validate_audio_file, transcribe_audio, estimate_confidence
        )
        from config.settings import settings

        audio_path = input_data.get("audio_path", "")
        audio_data = input_data.get("audio_data")
        language = input_data.get("language", "en")

        if audio_data:
            self.logger.info(f"Transcribing from in-memory audio data ({len(audio_data)} bytes)")
            from tools.audio_tools import transcribe_audio_data
            result = transcribe_audio_data(
                audio_data=audio_data,
                api_key=settings.OPENAI_API_KEY,
                language=language,
            )
        else:
            self.logger.info(f"Transcribing: {audio_path}")
            if not validate_audio_file(audio_path):
                raise ValueError(f"Invalid or missing audio file: {audio_path}")
            result = transcribe_audio(
                audio_path=audio_path,
                api_key=settings.OPENAI_API_KEY,
                language=language,
            )

        # Estimate confidence
        confidence = estimate_confidence(
            result["transcript"],
            result.get("duration_seconds"),
        )

        self.logger.info(f"Transcribed {result.get('duration_seconds', 0):.1f}s audio — confidence: {confidence:.0%}")

        return {
            "transcript": result["transcript"],
            "confidence": confidence,
            "language": result["language"],
            "duration_seconds": result.get("duration_seconds"),
        }

    def format_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "transcript": result.get("transcript", ""),
            "confidence": result.get("confidence", 0.0),
            "language": result.get("language", "en"),
            "duration_seconds": result.get("duration_seconds"),
            "sector": self.sector,
        }
