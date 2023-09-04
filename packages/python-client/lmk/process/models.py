from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Job(Base):
    """ """

    __tablename__ = "job"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    pid: Mapped[Optional[int]]
    command: Mapped[Optional[str]]
    notify_on: Mapped[str]
    notify_status: Mapped[Optional[str]]
    error_type: Mapped[Optional[str]]
    error: Mapped[Optional[str]]
    channel_id: Mapped[Optional[str]]
    session_id: Mapped[Optional[str]]
    started_at: Mapped[Optional[datetime]]
    ended_at: Mapped[Optional[datetime]]
    exit_code: Mapped[Optional[int]]

    def is_running(self) -> bool:
        if self.ended_at:
            return False
        if not self.started_at:
            return False
        return True
