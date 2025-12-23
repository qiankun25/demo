"""Services package for business logic components."""

"""
注意：不要在此处做“带副作用”的导入。

例如 storage.py 里可能会在 import 时初始化单例并读取环境变量；
这会导致仅仅导入 `app.services.*` 就要求完整的生产配置。

各处请直接从子模块导入：
- `from app.services.downloader import PDFDownloader`
- `from app.services.storage import MinIOStorage`
- `from app.services.validator import URLValidator`
"""

__all__ = ["MinIOStorage", "URLValidator", "PDFDownloader"]
