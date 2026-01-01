from __future__ import annotations

import asyncio
import logging
import os

from app.mq_worker import MQWorker


def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


async def main() -> None:
    _setup_logging()
    worker = MQWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())


