import asyncio
import socket
import time

import aiohttp


def find_free_port():
    with socket.socket() as s:
        s.bind(("", 0))  # Bind to a free port provided by the host.
        return s.getsockname()[1]  # Return the port number assigned.


async def wait_for_server(url: str, timeout: float) -> None:
    async with aiohttp.ClientSession() as session:
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = await session.get(url)
                resp.raise_for_status()
                return
            except aiohttp.ClientError as err:
                await asyncio.sleep(0.1)

        raise TimeoutError
