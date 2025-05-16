# logger_setup.py
import logging
import os

LOG_FILE = os.path.join(os.path.dirname(__file__), "logfile.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("voice-agent")
