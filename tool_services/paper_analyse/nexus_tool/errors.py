from dataclasses import dataclass
from typing import Optional


@dataclass
class ClassifiedError(Exception):
    category: str
    message: str
    cause: Optional[BaseException] = None

    def __str__(self) -> str:
        return f"[{self.category}] {self.message}"


class DownloadFailed(ClassifiedError):
    def __init__(self, message: str, cause: Optional[BaseException] = None):
        super().__init__(category="DOWNLOAD_FAILED", message=message, cause=cause)


class ParseFailed(ClassifiedError):
    def __init__(self, message: str, cause: Optional[BaseException] = None):
        super().__init__(category="PARSE_FAILED", message=message, cause=cause)


class LLMFailed(ClassifiedError):
    def __init__(self, message: str, cause: Optional[BaseException] = None):
        super().__init__(category="LLM_FAILED", message=message, cause=cause)


