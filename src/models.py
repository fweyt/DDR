from dataclasses import dataclass
from datetime import datetime


@dataclass
class QueueItem:
    id: int
    sender: str
    message: str
    channel: str
    status: str
    reply: str | None
    created_at: datetime
