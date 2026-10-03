"""Upload limits for the demo service. The message has the wrong unit."""

MAX_UPLOAD_MB = 25


def size_error(size_mb):
    """The message shown when an upload is too large, or None."""
    if size_mb > MAX_UPLOAD_MB:
        return f"Upload too large: the limit is {MAX_UPLOAD_MB} GB."
    return None
