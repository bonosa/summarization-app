import os
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

AUDIO_DIR = "audio_outputs"

voice_map = {'grandma GG': 'rKVm0Cb9J2wrzmZupJea', 'tech wizard': 'ocn9CucaUfmmP6Two6Ik', 'perky sidekick': 'DWR3ijzKmphlRUhbBI7t', 'bill the newscaster': 'R1vZMopVRO75M5xBKX52', 'spunky charlie': 'q3yXDjF0aq4JCEo9u2g4', 'sassy teen': 'mBj2IDD9aXruPJHLGCAv'}

def sanitize_url(url):
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url

def extract_internal_links(html_content, base_url):
    soup = BeautifulSoup(html_content, "html.parser")
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc

    links = set()
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        parsed_href = urlparse(href)

        if parsed_href.netloc == "" or parsed_href.netloc == base_domain:
            full_url = parsed_href.geturl()
            if not full_url.startswith("http"):
                full_url = f"{parsed_base.scheme}://{base_domain}{href}"
            links.add(full_url)

    return list(links)

def crawl_documentation(url):
    import requests
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"Error fetching page: {e}"

def get_voice_prompt_style(voice):
    tone = {'grandma GG': 'dry, witty, and brutally honest — will roast you if you mess up.', 'tech wizard': 'cryptic, snarky, and a prodigy with code — speaks in digital spells.', 'perky sidekick': 'energetic, cheerful, and endlessly supportive — like a high-five machine.', 'bill the newscaster': 'polished, confident, and composed — delivers everything like breaking news.', 'spunky charlie': 'wildly curious, playful, and full of devil-may-care energy.', 'sassy teen': 'sarcastic, sharp-tongued, and too cool to care — flexes brainpower with attitude.'}
    return tone.get(voice.lower(), "neutral")

def save_audio_file(audio_path, content):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    with open(audio_path, "wb") as f:
        f.write(content)

__all__ = [
    "sanitize_url",
    "extract_internal_links",
    "crawl_documentation",
    "get_voice_prompt_style",
    "save_audio_file",
    "voice_map",
    "AUDIO_DIR",
]
