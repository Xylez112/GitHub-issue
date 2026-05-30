import logging
import sys

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    deepseek_api_key: str = ""
    github_token: str = ""
    chroma_persist_dir: str = "./chroma_data"
    log_level: str = "INFO"


settings = Settings()


def setup_logging(name: str) -> logging.Logger:
    """Create a logger with the project's standard format.

    Usage in any module:
        from ..core.config import setup_logging
        logger = setup_logging(__name__)
        logger.info("something happened")
    """
    logger = logging.getLogger(name)

    # Only configure once (avoid duplicate handlers)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s [%(levelname)-7s] %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Don't propagate to root logger (avoid duplicate output)
    logger.propagate = False
    return logger
