from pathlib import Path

try:
    from creart import it
except ModuleNotFoundError:
    it = None

from src.upload.models import LocalFiles, UploadBundleResult, UploadItemResult


class UploadService:
    def __init__(self, uploader=None, provider: str | None = None):
        self.provider = provider or ('custom' if uploader is not None else self._config().upload.provider)
        self.uploader = uploader or self._build_uploader(self.provider)

    def _config(self):
        if it is None:
            raise RuntimeError('creart is required when UploadService builds uploaders from config')
        from src.config import Config
        return it(Config)

    def _build_uploader(self, provider: str):
        if provider == 'webdav':
            from src.upload.webdav import WebDAVUploader
            cfg = self._config().upload.webdav
            return WebDAVUploader(cfg.url, cfg.username, cfg.password, cfg.basePath, cfg.timeout)
        if provider == 'openlist':
            from src.upload.openlist import OpenListUploader
            cfg = self._config().upload.openlist
            return OpenListUploader(cfg.url, cfg.username, cfg.password, cfg.token, cfg.basePath, cfg.timeout)
        raise ValueError(f'Unsupported upload provider: {provider}')

    def upload(self, local_files: LocalFiles) -> UploadBundleResult:
        remote_dir = local_files.remote_dir.strip('/').replace('\\', '/')
        results: list[UploadItemResult] = []
        try:
            self.uploader.ensure_dir(remote_dir)
            for kind, path in [('audio', local_files.audio_path), ('lyrics', local_files.lyrics_path), ('cover', local_files.cover_path)]:
                if not path:
                    continue
                local_path = Path(path)
                if not local_path.exists():
                    continue
                remote_path = '/'.join(part for part in [remote_dir, local_path.name] if part)
                item_result = self.uploader.upload_file(local_path, remote_path)
                item_result.kind = kind
                results.append(item_result)
                if not item_result.success:
                    return UploadBundleResult(
                        provider=self.provider,
                        remote_dir=remote_dir,
                        items=results,
                        success=False,
                        error_message=item_result.error_message or f'{kind} upload failed',
                    )
            return UploadBundleResult(provider=self.provider, remote_dir=remote_dir, items=results, success=True)
        except Exception as exc:
            return UploadBundleResult(provider=self.provider, remote_dir=remote_dir, items=results, success=False, error_message=str(exc))


def cleanup_local_files(local_files: LocalFiles):
    all_paths = [local_files.audio_path, local_files.lyrics_path, local_files.cover_path]
    for path in all_paths:
        if not path:
            continue
        path = Path(path)
        if path.exists():
            path.unlink()
    work_dir = Path(local_files.work_dir) if local_files.work_dir else None
    while work_dir and work_dir.exists() and work_dir.is_dir():
        if any(work_dir.iterdir()):
            break
        work_dir.rmdir()
        work_dir = work_dir.parent
