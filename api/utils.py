import os
from api.constants import LOG_BASE_DIR

def get_timeline_path(item_id: str) -> str:
    return os.path.join(LOG_BASE_DIR, item_id.upper(), "timeline.jsonl")
