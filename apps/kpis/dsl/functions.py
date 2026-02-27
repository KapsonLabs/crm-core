import statistics
from typing import List, Union


def _ensure_list(args):
    """Convert arguments to a list if needed."""
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        return list(args[0])
    return list(args)


ALLOWED_FUNCTIONS = {
    "SUM": lambda *args: sum(_ensure_list(args)),
    "AVG": lambda *args: statistics.mean(_ensure_list(args)) if _ensure_list(args) else 0,
    "MIN": lambda *args: min(_ensure_list(args)) if _ensure_list(args) else 0,
    "MAX": lambda *args: max(_ensure_list(args)) if _ensure_list(args) else 0,
    "IF": lambda cond, a, b: a if cond else b,
}
