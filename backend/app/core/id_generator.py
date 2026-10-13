from datetime import datetime, timezone
from uuid import uuid4


def generate_public_id(prefix: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = uuid4().hex[:10]
    return f"{prefix}_{timestamp}_{suffix}"
