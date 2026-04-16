from pathlib import PurePosixPath, Path

import httpx

from src.upload.base import BaseUploader
from src.upload.models import UploadItemResult


class OpenListUploader(BaseUploader):
    def __init__(self, url: str, username: str = "", password: str = "", token: str = "", base_path: str = "/", timeout: int = 120):
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.token = token
        self.base_path = base_path.strip("/")
        self.client = httpx.Client(timeout=timeout)

    def _api(self, path: str) -> str:
        return f"{self.url}{path}"

    def _headers(self) -> dict:
        if not self.token:
            self._login()
        return {"Authorization": self.token}

    def _login(self):
        if self.token:
            return
        resp = self.client.post(self._api('/api/auth/login'), json={"username": self.username, "password": self.password})
        if resp.status_code >= 400:
            raise RuntimeError(f"OpenList 登录失败: {resp.status_code} {resp.text[:200]}")
        payload = resp.json()
        token = (payload.get('data') or {}).get('token') or payload.get('token')
        if not token:
            raise RuntimeError('OpenList 登录失败: 响应中没有 token')
        self.token = token

    def _full_remote_dir(self, remote_dir: str) -> str:
        return '/' + '/'.join(part for part in [self.base_path, remote_dir.strip('/')] if part)

    def ensure_dir(self, remote_dir: str):
        remote_path = self._full_remote_dir(remote_dir)
        resp = self.client.post(self._api('/api/fs/mkdir'), json={"path": remote_path}, headers=self._headers())
        if resp.status_code >= 400:
            raise RuntimeError(f"OpenList 创建目录失败: {resp.status_code} {resp.text[:200]}")

    def upload_file(self, local_path: Path, remote_path: str) -> UploadItemResult:
        parent = PurePosixPath(self._full_remote_dir(PurePosixPath(remote_path).parent.as_posix())).as_posix()
        with local_path.open('rb') as fh:
            resp = self.client.post(
                self._api('/api/fs/form'),
                data={"path": parent},
                files={"file": (local_path.name, fh, 'application/octet-stream')},
                headers=self._headers(),
            )
        if resp.status_code >= 400:
            return UploadItemResult(
                kind=local_path.suffix.lstrip('.') or 'file',
                local_path=str(local_path),
                remote_path=remote_path,
                success=False,
                error_message=f"OpenList 上传失败: {resp.status_code} {resp.text[:200]}",
            )
        return UploadItemResult(kind=local_path.suffix.lstrip('.') or 'file', local_path=str(local_path), remote_path=remote_path, success=True)
