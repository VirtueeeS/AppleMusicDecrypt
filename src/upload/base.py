from pathlib import Path
from abc import ABC, abstractmethod

from src.upload.models import UploadItemResult


class BaseUploader(ABC):
    @abstractmethod
    def ensure_dir(self, remote_dir: str):
        raise NotImplementedError

    @abstractmethod
    def upload_file(self, local_path: Path, remote_path: str) -> UploadItemResult:
        raise NotImplementedError
