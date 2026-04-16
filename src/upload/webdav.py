from pathlib import Path
from urllib.parse import quote

import httpx

from src.upload.base import BaseUploader
from src.upload.models import UploadItemResult


class WebDAVUploader(BaseUploader):
    def __init__(self, url: str, username: str = "", password: str = "", base_path: str = "/", timeout: int = 120):
        self.url = url.rstrip("/")
        self.base_path = base_path.strip("/")
        auth = (username, password) if username or password else None
        self.client = httpx.Client(timeout=timeout, auth=auth)

    def _full_path(self, remote_path: str) -> str:
        normalized = "/".join(part for part in [self.base_path, remote_path.strip("/")] if part)
        return f"{self.url}/{quote(normalized, safe='/')}"

    def ensure_dir(self, remote_dir: str):
        normalized = "/".join(part for part in [self.base_path, remote_dir.strip("/")] if part)
        if not normalized:
            return
        current = []
        for segment in normalized.split("/"):
            if not segment:
                continue
            current.append(segment)
            resp = self.client.request("MKCOL", f"{self.url}/{quote('/'.join(current), safe='/')}")
            if resp.status_code not in (200, 201, 204, 301, 405):
                raise RuntimeError(f"WebDAV 创建目录失败: {resp.status_code} {resp.text[:200]}")

    def upload_file(self, local_path: Path, remote_path: str) -> UploadItemResult:
        with local_path.open("rb") as fh:
            resp = self.client.put(self._full_path(remote_path), content=fh.read())
        if resp.status_code < 200 or resp.status_code >= 300:
            return UploadItemResult(
                kind=local_path.suffix.lstrip('.') or 'file',
                local_path=str(local_path),
                remote_path=remote_path,
                success=False,
                error_message=f"WebDAV 上传失败: {resp.status_code} {resp.text[:200]}",
            )
        return UploadItemResult(kind=local_path.suffix.lstrip('.') or 'file', local_path=str(local_path), remote_path=remote_path, success=True)
