from datetime import datetime, timedelta
from typing import Optional

from nextcord import Member

from dataclasses import dataclass

@dataclass
class Infraction:
    actiontype: str
    reason: str
    moderator: Member
    actiontime: datetime
    duration: Optional[timedelta]
    attachment_url: Optional[str]
