import asyncio

import systemd.daemon


async def main() -> None:
    systemd.daemon.notify("READY=1")
