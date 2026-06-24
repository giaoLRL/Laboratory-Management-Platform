import logging
import os

# Use a logger that writes to both console and a rotating file when available
_log_level = os.getenv('LAB_MANAGER_LOG_LEVEL', 'INFO')

logger = logging.getLogger('lab_manager')
logger.setLevel(getattr(logging, _log_level, logging.INFO))

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s %(name)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))
    logger.addHandler(handler)
