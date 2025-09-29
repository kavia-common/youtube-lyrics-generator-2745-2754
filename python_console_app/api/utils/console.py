"""
Console utilities for themed output.

Ocean Professional theme:
- Primary (blue): #2563EB
- Secondary/success (amber): #F59E0B
- Error (red): #EF4444
"""

from dataclasses import dataclass
import sys


@dataclass(frozen=True)
class Palette:
    primary: str = "\033[38;2;37;99;235m"     # #2563EB
    secondary: str = "\033[38;2;245;158;11m"  # #F59E0B
    error: str = "\033[38;2;239;68;68m"       # #EF4444
    reset: str = "\033[0m"
    dim: str = "\033[2m"
    bold: str = "\033[1m"


PALETTE = Palette()


# PUBLIC_INTERFACE
def info(msg: str) -> None:
    """Print informational message in primary blue."""
    print(f"{PALETTE.primary}{msg}{PALETTE.reset}")


# PUBLIC_INTERFACE
def success(msg: str) -> None:
    """Print success message in amber."""
    print(f"{PALETTE.secondary}{msg}{PALETTE.reset}")


# PUBLIC_INTERFACE
def error(msg: str) -> None:
    """Print error message in red to stderr."""
    print(f"{PALETTE.error}{msg}{PALETTE.reset}", file=sys.stderr)


# PUBLIC_INTERFACE
def headline(msg: str) -> None:
    """Print a bold blue headline."""
    print(f"{PALETTE.bold}{PALETTE.primary}{msg}{PALETTE.reset}")


# PUBLIC_INTERFACE
def prompt(msg: str) -> str:
    """Prompt user with a blue question; return input string."""
    return input(f"{PALETTE.primary}{msg}{PALETTE.reset} ")
