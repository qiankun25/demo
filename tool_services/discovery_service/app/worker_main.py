from __future__ import annotations

import asyncio
import logging

from app.db import DiscoveryDB
from app.mq_worker import MQWorker
from tool_services.discovery_service.settings import settings


def _setup_logging() -> None:
    level = settings.log_level.upper()
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


async def main() -> None:
    _setup_logging()
    db_url = settings.database_url
    db = DiscoveryDB.from_url(db_url)
    worker = MQWorker(db)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())


