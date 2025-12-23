import asyncio

from .tool_service import DownloaderToolService


def main() -> None:
    asyncio.run(DownloaderToolService().start())


if __name__ == "__main__":
    main()


