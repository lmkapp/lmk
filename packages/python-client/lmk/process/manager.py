import asyncio
import json
import os
import uuid
import dataclasses as dc
from datetime import date, datetime
from typing import Optional, AsyncGenerator, List

import aiohttp

from lmk.utils import socket_exists


@dc.dataclass(frozen=True)
class NewJob:
    """ """

    job_id: str
    job_dir: str
    pid_file: str


@dc.dataclass(frozen=True)
class RunningJob(NewJob):
    """ """

    running: bool
    target_pid: int
    notify_on: str
    started_at: datetime


class JobManager:
    """ """

    def __init__(self, base_path: Optional[str] = None) -> None:
        self.base_path = base_path
        self.pids_dir = os.path.join(base_path, "job-pids")
        self.jobs_dir = os.path.join(base_path, "jobs")

    def create_job(self, process_name: Optional[str] = None) -> NewJob:
        parts = [process_name] if process_name else []
        parts.append(date.today().strftime("%Y%m%d"))

        job_id = None
        job_dir = None

        while True:
            job_hash = uuid.uuid4().hex[:8]
            job_id = "-".join(parts + [job_hash])

            job_dir = os.path.join(self.jobs_dir, job_id)
            if os.path.exists(job_dir):
                continue

            os.makedirs(job_dir)
            break

        if not os.path.exists(self.pids_dir):
            os.makedirs(self.pids_dir)

        pid_file = os.path.join(self.pids_dir, f"{job_id}.pid")
        return NewJob(job_id, job_dir, pid_file)

    def get_not_started_job(self, job_id: str) -> NewJob:
        job_dir = os.path.join(self.jobs_dir, job_id)
        if not os.path.exists(job_dir):
            raise ValueError(f"Job does not exist: {job_id}")

        pid_file = os.path.join(self.pids_dir, f"{job_id}.pid")
        return NewJob(job_id, job_dir, pid_file)

    async def get_job(self, job_id: str) -> Optional[RunningJob]:
        job_dir = os.path.join(self.jobs_dir, job_id)
        if not os.path.exists(job_dir):
            return None

        pid_file = os.path.join(self.pids_dir, f"{job_id}.pid")

        socket_path = os.path.join(job_dir, "daemon.sock")
        if not socket_exists(socket_path):
            result_file = os.path.join(job_dir, "result.json")
            if not os.path.exists(result_file):
                return None

            with open(result_file) as f:
                result = json.load(f)
                return RunningJob(
                    job_id=job_id,
                    job_dir=job_dir,
                    pid_file=pid_file,
                    running=False,
                    target_pid=result["pid"],
                    notify_on=result["notify_on"],
                    started_at=datetime.fromisoformat(result["started_at"]),
                )

        connector = aiohttp.UnixConnector(path=socket_path)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get("http://daemon/status") as response:
                body = await response.json()
                return RunningJob(
                    job_id=job_id,
                    job_dir=job_dir,
                    pid_file=pid_file,
                    running=True,
                    target_pid=body["pid"],
                    notify_on=body["notify_on"],
                    started_at=datetime.fromisoformat(body["started_at"]),
                )

    async def list_running_jobs(self) -> AsyncGenerator[RunningJob, None]:
        if not os.path.exists(self.pids_dir):
            return

        job_ids = []

        for filename in os.listdir(self.pids_dir):
            job_id = filename.rsplit(".", 1)[0]
            job_ids.append(job_id)

        async for result in self.get_jobs(job_ids):
            if result.running:
                yield result

    def get_all_job_ids(self) -> List[str]:
        if not os.path.exists(self.jobs_dir):
            return []

        return os.listdir(self.jobs_dir)

    async def get_jobs(self, ids: List[str]) -> AsyncGenerator[RunningJob, None]:
        tasks = []

        for job_id in ids:
            tasks.append(asyncio.create_task(self.get_job(job_id)))

        while tasks:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                res = task.result()
                if res is None:
                    continue
                yield res

            tasks = pending
