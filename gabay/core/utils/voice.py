import logging
import os
from groq import Groq
from gabay.core.config import settings

logger = logging.getLogger(__name__)

def transcribe_audio(file_path: str) -> str:
    """
    Transcribes an audio file (e.g., .oga, .mp3, .wav) using Groq's Whisper API.
    """
    if not settings.groq_api_key or settings.groq_api_key == "your_groq_api_key_here":
        logger.error("Groq API Key is missing. Cannot transcribe audio.")
        return ""

    try:
        client = Groq(api_key=settings.groq_api_key)
        with open(file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(file_path), file.read()),
                model="whisper-large-v3",
                response_format="json",
            )
            return transcription.text
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        return ""
