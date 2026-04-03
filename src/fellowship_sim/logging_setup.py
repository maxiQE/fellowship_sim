import sys
from typing import Any

from loguru import logger

from fellowship_sim.base_classes.state import get_state


def get_game_time() -> str:
    return f"{get_state().time:>7.2f}"


def patch_game_time(record: Any) -> None:
    """Injects the current game time into every log record's 'extra' dict."""
    if "pytest" not in sys.modules:
        record["extra"]["game_time"] = get_game_time()


def configure_logging(
    level: str = "WARNING",
    mode: str = "user",
) -> None:
    USER_FORMAT = "<level>{level: <8}</level> | <cyan>{extra[game_time]}</cyan> | <level>{message}</level>"
    DEV_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[game_time]}</cyan> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"

    logger.remove()

    fmt = DEV_FORMAT if mode == "dev" else USER_FORMAT

    logger.configure(
        handlers=[
            {
                "sink": sys.stderr,
                "format": fmt,
                "level": level,
            },
        ],
        patcher=patch_game_time,
    )


# Default logging setup
configure_logging(level="WARNING", mode="user")
