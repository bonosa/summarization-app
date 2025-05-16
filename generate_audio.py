import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from logger_setup import logger

# Load environment variables
load_dotenv()

# Use absolute path for output
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "audio_outputs")

# Verify API key
api_key = os.getenv("ELEVENLABS_API_KEY")
if not api_key:
    logger.error("❌ ELEVENLABS_API_KEY is missing or not loaded from .env")
    raise RuntimeError("ELEVENLABS_API_KEY missing")

client = ElevenLabs(api_key=api_key)

def generate_audio(text: str, voice_id: str, audio_key: str):
    try:
        logger.info("🎯 Starting ElevenLabs audio generation")
        os.makedirs(AUDIO_DIR, exist_ok=True)

        try:
            audio_stream = client.text_to_speech.convert_as_stream(
                text=text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2"
            )
            logger.info("✅ Audio stream received from ElevenLabs")
        except Exception as stream_err:
            logger.error(f"❌ Failed to get audio stream: {stream_err}")
            raise

        output_path = os.path.join(AUDIO_DIR, f"{audio_key}.mp3")

        try:
            with open(output_path, "wb") as f:
                for chunk in audio_stream:
                    if isinstance(chunk, bytes):
                        f.write(chunk)
            logger.info(f"✅ Audio saved to {output_path}")
        except Exception as write_err:
            logger.error(f"❌ Failed to save audio to file: {write_err}")
            raise

    except Exception as e:
        logger.exception("🔥 Exception in generate_audio")
        raise
