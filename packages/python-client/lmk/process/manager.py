import json
import os
import uuid
from datetime import date, datetime
from typing import Optional, List, Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from lmk.process import exc
from lmk.process.models import Base, Job


MISSING: Any = object()


class JobManager:
    """
    Interface for managing and querying job data. Job data is stored in a SQLite database
    """

    def __init__(self, base_path: Optional[str] = None) -> None:
        if base_path is None:
            base_path = os.path.expanduser("~/.lmk")
        self.base_path = base_path
        self.jobs_dir = os.path.join(base_path, "jobs")
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{os.path.join(base_path, 'data.db')}"
        )
        self.async_session = async_sessionmaker(
            bind=self.engine, expire_on_commit=False
        )

    async def setup(self) -> None:
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)

        if not os.path.exists(self.jobs_dir):
            os.makedirs(self.jobs_dir)

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    def _job_dir(self, name: str) -> str:
        return os.path.join(self.jobs_dir, name)

    def pid_file(self, name: str) -> str:
        return os.path.join(self._job_dir(name), "manager.pid")

    def socket_file(self, name: str) -> str:
        return os.path.join(self._job_dir(name), "manager.sock")

    def log_file(self, name: str) -> str:
        return os.path.join(self._job_dir(name), "manager.log")

    def output_file(self, name: str) -> str:
        return os.path.join(self._job_dir(name), "process.log")

    async def create_job(
        self, process_name: Optional[str] = None, notify_on: Optional[str] = None
    ) -> Job:
        if notify_on is None:
            notify_on = "none"

        parts = [process_name] if process_name else []
        parts.append(date.today().strftime("%Y%m%d"))

        async with self.async_session() as session:
            while True:
                job_hash = uuid.uuid4().hex[:8]
                job_id = "-".join(parts + [job_hash])

                existing_job = await session.scalar(
                    sa.select(Job).where(Job.name == job_id)
                )
                if existing_job is not None:
                    continue

                os.makedirs(self._job_dir(job_id))
                obj = Job(
                    name=job_id,
                    notify_on=notify_on,
                )
                session.add(obj)
                await session.commit()
                return obj

    async def get_job(self, name: str, not_started: bool = False) -> Optional[Job]:
        async with self.async_session() as session:
            query = sa.select(Job).where(Job.name == name)
            if not_started:
                query = query.where(Job.started_at == None)
            return await session.scalar(query)

    async def start_job(self, name: str) -> Job:
        job = await self.get_job(name)
        if job is None:
            raise exc.JobNotFound(name)

        async with self.async_session() as session:
            job = await session.merge(job, load=False)
            job.started_at = datetime.utcnow()
            session.add(job)
            await session.commit()

            return job

    async def update_job(
        self,
        name: str,
        pid: int = MISSING,
        command: List[str] = MISSING,
        notify_on: str = MISSING,
        notify_status: str = MISSING,
        channel_id: Optional[str] = MISSING,
        session_id: str = MISSING,
    ) -> Job:
        job = await self.get_job(name)
        if job is None:
            raise exc.JobNotFound(name)

        async with self.async_session() as session:
            job = await session.merge(job, load=False)
            if pid is not MISSING:
                job.pid = pid
            if command is not MISSING:
                job.command = json.dumps(command)
            if notify_on is not MISSING:
                job.notify_on = notify_on
            if notify_status is not MISSING:
                job.notify_status = notify_status
            if channel_id is not MISSING:
                job.channel_id = channel_id
            if session_id is not MISSING:
                job.session_id = session_id

            session.add(job)
            await session.commit()

            return job

    async def end_job(
        self,
        name: str,
        exit_code: int,
        error: Exception = MISSING,
    ) -> Job:
        job = await self.get_job(name)
        if job is None:
            raise exc.JobNotFound(name)

        async with self.async_session() as session:
            job = await session.merge(job, load=False)
            job.exit_code = exit_code
            if error is not MISSING:
                job.error_type = type(error).__name__
                job.error = str(error)
            job.ended_at = datetime.utcnow()

            session.add(job)
            await session.commit()

            return job

    async def list_jobs(self, running_only: bool = False) -> List[Job]:
        query = (
            sa.select(Job).where(Job.started_at != None).order_by(Job.started_at.desc())
        )
        if running_only:
            query = query.where(Job.ended_at == None)

        async with self.async_session() as session:
            return list(await session.scalars(query))
