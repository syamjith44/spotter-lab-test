import json
import hashlib


def generate_cache_key(prefix, *args):
    """Stable hash key from any args — avoids key length/character issues."""
    raw = json.dumps(args, sort_keys=True)
    hashed = hashlib.md5(raw.encode()).hexdigest()
    return f"{prefix}_{hashed}"
