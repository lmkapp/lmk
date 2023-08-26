import asyncio
import dataclasses as dc
import enum
import logging
import time
from datetime import datetime
from typing import Optional

from blinker import signal
from IPython import get_ipython
from IPython.core.interactiveshell import (
    InteractiveShell,
    ExecutionInfo,
    ExecutionResult,
)

from lmk.jupyter.utils import background_ctx


LOGGER = logging.getLogger(__name__)

jupyter_state_changed = signal("juptyer-state-changed")

jupyter_cell_state_changed = signal("jupyter-cell-state-changed")


class IPythonShellState(str, enum.Enum):
    Idle = "idle"
    Running = "running"


@dc.dataclass(frozen=True)
class IPythonCellState:
    execution_count: int
    info: ExecutionInfo
    started_at: datetime
    result: Optional[ExecutionResult]
    finished_at: Optional[datetime]

    def error(self) -> Optional[Exception]:
        if not self.result:
            return None
        if self.result.error_before_exec:
            return self.result.error_before_exec
        if self.result.error_in_exec:
            return self.result.error_in_exec
        return None


class IPythonHistory:
    def __init__(
        self,
        shell: Optional[InteractiveShell] = None,
    ) -> None:
        if shell is None:
            shell = get_ipython()
        self._state = IPythonShellState.Idle
        self.shell = shell

        self._idle_start = None
        self._last_cell_state = None

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, value: IPythonShellState) -> None:
        if self._state == value:
            return
        old_value = self._state
        self._state = value
        jupyter_state_changed.send(self, old_state=old_value, new_state=value)

    def _pre_execute(self) -> None:
        with background_ctx(LOGGER, type(self).__name__):
            self._idle_start = None

    def _pre_run_cell(self, info: ExecutionInfo) -> None:
        with background_ctx(LOGGER, type(self).__name__):
            self.state = IPythonShellState.Running
            self._idle_start = None
            execution_count = 0
            if self._last_cell_state:
                execution_count = self._last_cell_state.execution_count + 1
            prev_state = self._last_cell_state
            self._last_cell_state = IPythonCellState(
                execution_count=execution_count,
                info=info,
                started_at=datetime.utcnow(),
                result=None,
                finished_at=None,
            )
            jupyter_cell_state_changed.send(
                self, old_state=prev_state, new_state=self._last_cell_state
            )

    def _post_execute(self) -> None:
        with background_ctx(LOGGER, type(self).__name__):
            self._idle_start = time.time()

    def _post_run_cell(self, result: ExecutionResult) -> None:
        with background_ctx(LOGGER, type(self).__name__):
            self.state = IPythonShellState.Running
            self._idle_start = time.time()
            prev_state = self._last_cell_state
            now = datetime.utcnow()
            started_at = now
            execution_count = result.execution_count
            if self._last_cell_state:
                started_at = self._last_cell_state.started_at
            if self._last_cell_state and execution_count is None:
                execution_count = self._last_cell_state.execution_count
            if execution_count is None:
                execution_count = -1
            self._last_cell_state = IPythonCellState(
                execution_count=execution_count,
                info=result.info,
                started_at=started_at,
                result=result,
                finished_at=now,
            )
            jupyter_cell_state_changed.send(
                self, old_state=prev_state, new_state=self._last_cell_state
            )

    async def main_loop(self) -> None:
        while True:
            cutoff = 1
            if (
                self.state == IPythonShellState.Running
                and self._idle_start
                and time.time() - self._idle_start > cutoff
            ):
                self.state = IPythonShellState.Idle

            await asyncio.sleep(0.1)

    def connect(self) -> None:
        self.shell.events.register("pre_execute", self._pre_execute)
        self.shell.events.register("pre_run_cell", self._pre_run_cell)
        self.shell.events.register("post_execute", self._post_execute)
        self.shell.events.register("post_run_cell", self._post_run_cell)

    def disconnect(self) -> None:
        self.shell.events.unregister("pre_execute", self._pre_execute)
        self.shell.events.unregister("pre_run_cell", self._pre_run_cell)
        self.shell.events.unregister("post_execute", self._post_execute)
        self.shell.events.unregister("post_run_cell", self._post_run_cell)
