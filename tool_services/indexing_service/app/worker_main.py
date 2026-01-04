from __future__ import annotations

import asyncio
import logging

from app.mq_worker import MQWorker
from app.core.config import settings


def _setup_logging() -> None:
    level = settings.LOG_LEVEL.upper()
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


async def main() -> None:
    _setup_logging()
    worker = MQWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())


