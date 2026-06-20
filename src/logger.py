import logging
import os
import sys

def setup_logger():
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("cleaner")
    logger.setLevel(logging.INFO)

    # Check if handlers are already set to prevent duplicate logging
    if not logger.handlers:
        # File handler - appends logs to logs/cleaner.log
        file_handler = logging.FileHandler("logs/cleaner.log", mode="a", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(file_handler)

        # Console handler - prints to stdout
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console_handler)

    return logger

log = setup_logger()
