"""Retry backoff delay computation."""


def compute_delay(strategy: str, base_delay: float, max_delay: float, attempt: int) -> float:
    """Return seconds to wait before the next retry attempt.

    strategy: "fixed" | "linear" | "exponential"
    attempt:  number of attempts already made (1-indexed at first failure)
    """
    if strategy == "fixed":
        delay = base_delay
    elif strategy == "linear":
        delay = base_delay * attempt
    else:  # exponential (default)
        delay = base_delay * (2 ** (attempt - 1))

    return min(delay, max_delay)
