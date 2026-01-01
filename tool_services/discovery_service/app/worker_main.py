from __future__ import annotations

import asyncio
import logging
import os

from app.db import DiscoveryDB
from app.mq_worker import MQWorker


def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


async def main() -> None:
    _setup_logging()
    db_url = os.getenv("DISCOVERY_DATABASE_URL", "postgresql://discovery_user:discovery_pass@localhost:5434/discovery")
    db = DiscoveryDB.from_url(db_url)
    worker = MQWorker(db)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())


