import asyncio

from .tool_service import ParserToolService


def main() -> None:
    asyncio.run(ParserToolService().start())


if __name__ == "__main__":
    main()


