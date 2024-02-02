"""Color constants."""

from enum import Enum


class Color(Enum):
    """Color constants."""

    # keep-sorted start
    BLACK = "\033[30m"
    BLUE = "\033[34m"
    BOLD_BLACK = "\033[1;30m"
    BOLD_BLUE = "\033[1;34m"
    BOLD_CYAN = "\033[1;36m"
    BOLD_GREEN = "\033[1;32m"
    BOLD_PURPLE = "\033[1;35m"
    BOLD_RED = "\033[1;31m"
    BOLD_WHITE = "\033[1;37m"
    BOLD_YELLOW = "\033[1;33m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    NONE = "\033[0m"
    PURPLE = "\033[35m"
    RED = "\033[31m"
    WHITE = "\033[37m"
    YELLOW = "\033[33m"
    # keep-sorted end
