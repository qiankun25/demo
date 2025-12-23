import asyncio

from .tool_service import IndexerToolService


def main() -> None:
    asyncio.run(IndexerToolService().start())


if __name__ == "__main__":
    main()


