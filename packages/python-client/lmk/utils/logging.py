from logging.config import dictConfig
from typing import Optional, IO, Dict, Any, Union


LOG_FORMAT = "%(asctime)s [%(name)s - %(levelname)s] %(message)s"


def setup_logging(
    disable_existing: bool = True,
    level: Union[str, int] = "INFO",
    format: str = LOG_FORMAT,
    log_file: Optional[str] = None,
    log_stream: Optional[IO[str]] = None,
) -> None:
    handler_kwargs: Dict[str, Any] = {"class": "logging.StreamHandler"}
    if log_file is not None:
        handler_kwargs = {"class": "logging.FileHandler", "filename": log_file}
    elif log_stream is not None:
        handler_kwargs = {"class": "logging.StreamHandler", "stream": log_stream}

    config = {
        "version": 1,
        "disable_existing_loggers": disable_existing,
        "formatters": {
            "standard": {
                "format": format,
            }
        },
        "handlers": {
            "default": {"level": level, "formatter": "standard", **handler_kwargs}
        },
        "loggers": {
            "": {"handlers": ["default"], "level": "ERROR", "propagate": False},
            "lmk": {"handlers": ["default"], "level": level, "propagate": False},
        },
    }

    dictConfig(config)
