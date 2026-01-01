from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from minio import Minio


@dataclass
class MinIOJSONStore:
    client: Minio
    bucket: str
    prefix: str

    @classmethod
    def from_env(
        cls,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
        prefix: str,
    ) -> "MinIOJSONStore":
        c = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        p = (prefix or "").lstrip("/")
        if p and not p.endswith("/"):
            p += "/"
        return cls(client=c, bucket=bucket, prefix=p)

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put_json(self, key: str, obj: Dict[str, Any]) -> str:
        """Write JSON object to prefix+key and return object_name."""
        self.ensure_bucket()
        object_name = f"{self.prefix}{key.lstrip('/')}"
        body = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        from io import BytesIO

        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_name,
            data=BytesIO(body),
            length=len(body),
            content_type="application/json",
        )
        return object_name

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        object_name = f"{self.prefix}{key.lstrip('/')}"
        try:
            resp = self.client.get_object(self.bucket, object_name)
            try:
                raw = resp.read()
            finally:
                resp.close()
                resp.release_conn()
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None


