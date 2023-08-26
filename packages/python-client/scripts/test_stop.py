import asyncio
from aiohttp import web


async def main():
    socket_path = "./tmp.sock"

    app =  web.Application()

    app.add_routes([
        web.get("/", lambda res: web.json_response({"ok": True}))
    ])

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.UnixSite(runner, socket_path)
    await site.start()

    await asyncio.sleep(1)
    print("Shutting down")

    await runner.cleanup()
    print("After cleanup")


if __name__ == "__main__":
    asyncio.run(main())
