import logging
from logging.config import dictConfig
import os

# Ensure logs directory exists using absolute path
CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CONFIG_DIR))
logs_dir = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(logs_dir, exist_ok=True)
log_file_path = os.path.join(logs_dir, "application.log")

log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": { 
        "console": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(asctime)s - %(message)s",
        },
        "file": {
            "format": "%(levelname)s: %(asctime)s - %(name)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "formatter": "console",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "file": {
            "formatter": "file",
            "class": "logging.FileHandler",
            "filename": log_file_path,  # log file absolute path
            "mode": "a",  # append mode
            "encoding": "utf-8"
        },
    },
    "loggers": {
        "agent_system": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "watchfiles": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    }
}

dictConfig(log_config)
logger = logging.getLogger("agent_system")
