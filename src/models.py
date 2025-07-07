from datetime import datetime, timedelta
from typing import Optional, List, Union

from nextcord import Member

from dataclasses import dataclass, field

@dataclass
class Infraction:
    actiontype: str
    reason: str
    moderator: Member
    actiontime: datetime
    duration: Optional[timedelta]
    attachment_url: Optional[str]
    update: List[dict] = field(default_factory=list)