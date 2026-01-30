import logging

from app.config import get_settings


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format=LOG_FORMAT)
