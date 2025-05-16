import os
import uuid
import logging
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from utils import (
    sanitize_url,
    crawl_documentation,
    get_voice_prompt_style,
    voice_map,
)
from ai_agents import Runner, setup_agents
from generate_audio import generate_audio

app = FastAPI()
Path("audio_outputs").mkdir(parents=True, exist_ok=True)
AUDIO_DIR = "audio_outputs"

logging.basicConfig(
    filename="voice_agent.log",
    filemode="w",
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

class QueryRequest(BaseModel):
    query: str
    url: str = None
    voice: str = None
    file_text: str = None

from typing import Optional

class QueryResponse(BaseModel):
    answer: str
    audio_key: Optional[str] = None
    sources: list = []
    key_points: list[str] = []

@app.post("/process", response_model=QueryResponse)
async def process_query(req: QueryRequest, background_tasks: BackgroundTasks):
    try:
        start = datetime.now()
        logger.info(f"🧠 Processing query: {req.query}")
        logger.info(f"🌐 URL: {req.url}")
        logger.info(f"📎 File text preview: {req.file_text[:100] if req.file_text else 'None'}")
        logger.info(f"🎙️ Voice: {req.voice}")

        key_points = []
        if req.file_text:
            from ai_agents import Agent
            extract_agent = Agent(
                name="KeyPointAgent",
                instructions="Extract the 5–7 most important key points from this content. Respond only as a bullet list.",
                model="gpt-4o"
            )
            key_points_raw = await extract_agent.run(req.file_text)
            key_points = [line.strip('-•* ').strip() for line in key_points_raw.splitlines() if line.strip()]
            if not key_points:
                logger.info('⚠️ No bullet points detected from GPT, using fallback.')
                key_points = [key_points_raw.strip()]
            logger.info(f'🔎 Final key points: {key_points}')

        if req.url:
            try:
                content = crawl_documentation(req.url)
                context = f"{content}\n\nNow answer the user's question: {req.query}"
            except Exception as e:
                logger.warning(f"⚠️ URL crawl failed: {e}")
                context = f"Answer the following using your general knowledge:\n\n{req.query}"
        elif req.file_text:
            context = f"{req.file_text}\n\nNow answer the user's question: {req.query}"
        else:
            context = f"Answer the following using your general knowledge:\n\n{req.query}"

        tone = get_voice_prompt_style(req.voice or "")
        if tone:
            context = tone + "\n\n" + context

        processor, _ = setup_agents()
        logger.info("🧠 Sending context to GPT")
        answer = await Runner.run(processor, context)

        if not answer:
            raise HTTPException(status_code=500, detail="No GPT response.")

        logger.info(f"✅ GPT returned: {answer[:100]}...")
        logger.info(f"🤖 GPT answer complete. ⏱️ {datetime.now() - start}")

        audio_key = None
        if req.voice and req.voice in voice_map:
            voice_id = voice_map[req.voice]
            audio_key = str(uuid.uuid4())

            generate_audio(answer, voice_id, audio_key)
            logger.info(f"🎙️ Audio generation triggered for voice: {req.voice}")

            # ✅ Check if audio file actually exists
            output_path = os.path.join(AUDIO_DIR, f"{audio_key}.mp3")
            if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
                logger.warning("🛑 Audio generation failed or file is too small.")
                audio_key = None
        else:
            logger.warning("🛑 Invalid voice")

        return QueryResponse(answer=answer, audio_key=audio_key, sources=[], key_points=key_points)

    except Exception as e:
        logger.error(f"🔥 Internal error: {str(e)}")
        import traceback
        logger.error("".join(traceback.format_exception(None, e, e.__traceback__)))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-audio/{key}")
async def get_audio(key: str, request: Request):
    audio_path = os.path.join(AUDIO_DIR, f"{key}.mp3")
    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio not found")

    if request.method == "HEAD":
        return StreamingResponse(iter([]), status_code=200)

    def iterfile():
        with open(audio_path, mode="rb") as file:
            yield from file
    return StreamingResponse(iterfile(), media_type="audio/mpeg")
