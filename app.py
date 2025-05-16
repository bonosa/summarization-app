import os
import uuid
import json
import fitz
import requests
import streamlit as st
from io import BytesIO
from docx import Document
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from utils import voice_map, get_voice_prompt_style, AUDIO_DIR
from generate_audio import generate_audio
from logger_setup import logger

# Load API keys
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# Streamlit config
st.set_page_config(page_title="Voice Agent Pro", page_icon="🎧")
logger.info("🎬 Streamlit app started")

# Inject large fonts + tips
st.markdown("""
    <style>
    .big-title {
        font-size: 2.4em !important;
        font-weight: bold;
        color: #333333;
        text-align: center;
    }
    .big-answer {
        font-size: 1.6em;
        line-height: 1.5;
        color: #111;
    }
    textarea, input {
        font-size: 1.2em !important;
    }
    .instructions {
        font-size: 1.1em;
        padding: 0.5em;
        background-color: #f0f4ff;
        border-radius: 0.5em;
        margin-bottom: 1em;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">🎧 Voice Agent Pro</div>', unsafe_allow_html=True)
st.markdown('<div class="instructions">Ask a question <b>OR</b> paste a URL <b>OR</b> upload a file — and I’ll summarize it in bullet points with expressive AI narration!</div>', unsafe_allow_html=True)

# Voice selection
st.sidebar.header("🎚️ Voice Settings")
voice_label = st.sidebar.selectbox("Choose a voice:", list(voice_map.keys()))
voice_id = voice_map[voice_label]
tone_prompt = get_voice_prompt_style(voice_label)
font_size = st.sidebar.radio("Font Size", ["Normal", "Large"])
font_class = "big-answer" if font_size == "Large" else ""

# One-liners per voice
preview_lines = {
    "grandma GG": "Back in my day, we didn’t need AI to sound this fabulous.",
    "tech wizard": "System online. You may now enter your query, human.",
    "perky sidekick": "You got this! Let’s answer that question together!",
    "bill the newscaster": "Breaking news — you’ve just selected the perfect voice.",
    "spunky charlie": "Whoa! Is it story time already? Let’s go!",
    "sassy teen": "Seriously? You better ask something cool."
}

preview_line = preview_lines.get(voice_label, "Testing voice.")
st.markdown(f"🎧 <b>{voice_label}</b> says:", unsafe_allow_html=True)
st.markdown(f"_“{preview_line}”_", unsafe_allow_html=True)

# Stream preview audio (no autoplay)
try:
    stream = client.text_to_speech.convert_as_stream(
        text=preview_line,
        voice_id=voice_id,
        model_id="eleven_multilingual_v2"
    )
    preview_audio = BytesIO()
    for chunk in stream:
        if isinstance(chunk, bytes):
            preview_audio.write(chunk)
    st.audio(preview_audio.getvalue())
except Exception as e:
    st.warning("Voice preview unavailable.")
    logger.exception("🎧 Voice preview error")

# Session state
if "answer" not in st.session_state: st.session_state.answer = ""
if "audio_key" not in st.session_state: st.session_state.audio_key = None
if "file_text" not in st.session_state: st.session_state.file_text = ""
if "key_points" not in st.session_state: st.session_state.key_points = []

# Inputs
query = st.text_area("🗨️ Ask your question:", value="", placeholder="Ask your question", key="query")
url = st.text_input("🌐 Or paste a URL:")
uploaded_file = st.file_uploader("📎 Or upload a file (PDF, TXT, DOCX)", type=["pdf", "txt", "docx"])

# File reader
def extract_text_from_file(file):
    file_type = file.name.split('.')[-1].lower()

    if file_type == "pdf":
        try:
            with fitz.open(stream=file.read(), filetype="pdf") as doc:
                return "\n".join(page.get_text() for page in doc)
        except Exception as e:
            logger.error(f"❌ PDF read failed: {e}")
            return "Failed to read the PDF."

    elif file_type == "txt":
        return file.read().decode("utf-8", errors="ignore")

    elif file_type == "docx":
        try:
            doc = Document(file)
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            logger.error(f"❌ DOCX read failed: {e}")
            return "Failed to read the DOCX file."

    return "Unsupported file type."

if uploaded_file:
    st.session_state.file_text = extract_text_from_file(uploaded_file)
    logger.info(f"📄 Extracted from file: {uploaded_file.name}")

# Clear app
if st.button("🧹 Clear All"):
    logger.info("🧼 Reset clicked")
    st.rerun()

# GPT streaming
def stream_openai_response(payload, headers):
    with requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, stream=True) as r:
        for line in r.iter_lines():
            if line and line.startswith(b"data: "):
                yield line[len(b"data: "):].decode()

# Summarize
if st.button("🔁 Summarize"):
    if not query and not url and not uploaded_file:
        st.warning("Please enter a question, a URL, or upload a file.")
        logger.warning("⚠️ Summarize clicked with no input")
    else:
        with st.spinner("Talking to GPT..."):
            try:
                context = ""
                if st.session_state.file_text:
                    context += st.session_state.file_text + "\n\n"
                if url:
                    context += f"Summarize this page: {url}\n\n"

                context += (
                    "You are a voice assistant with the following tone:\n"
                    f"{tone_prompt}\n\n"
                )

                if query.strip():
                    context += f"Now answer this in bullet points:\n{query}"
                else:
                    context += "Summarize the content above in bullet points."

                headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
                payload = {
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": context}],
                    "temperature": 0.7,
                    "stream": True
                }

                st.session_state.answer = ""
                answer_box = st.empty()
                logger.info("🧠 GPT stream started")

                for chunk in stream_openai_response(payload, headers):
                    if chunk.strip() == "[DONE]":
                        logger.info("🟢 GPT done")
                        continue
                    try:
                        parsed = json.loads(chunk)
                        delta = parsed['choices'][0]['delta'].get('content', '')
                        st.session_state.answer += delta
                        answer_box.markdown(f'<div class="{font_class}">{st.session_state.answer}</div>', unsafe_allow_html=True)
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ Non-JSON chunk skipped: {chunk}")
                        continue

                audio_key = str(uuid.uuid4())
                generate_audio(st.session_state.answer, voice_id, audio_key)
                st.session_state.audio_key = audio_key
                logger.info(f"🎧 Audio ready: {audio_key}")

            except Exception as e:
                st.error(f"🔥 Error: {e}")
                logger.exception("🔥 GPT/audio failed")

# Output
    if st.session_state.answer:
        st.subheader("📜 Answer")
        st.success(st.session_state.answer)

    if st.session_state.audio_key:
        audio_path = os.path.join(AUDIO_DIR, f"{st.session_state.audio_key}.mp3")
        if os.path.exists(audio_path):
            st.audio(audio_path)
        else:
            st.error("❗ Audio file missing.")
            logger.warning(f"❌ Missing audio file: {audio_path}")
