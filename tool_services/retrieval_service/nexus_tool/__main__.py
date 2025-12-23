import asyncio

from .tool_service import RetrievalToolService


def main() -> None:
    asyncio.run(RetrievalToolService().start())


if __name__ == "__main__":
    main()


