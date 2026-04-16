from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LocalFiles:
    audio_path: Path
    lyrics_path: Optional[Path] = None
    cover_path: Optional[Path] = None
    work_dir: Optional[Path] = None
    remote_dir: str = ""
    display_name: str = ""


@dataclass
class UploadItemResult:
    kind: str
    local_path: str
    remote_path: str
    success: bool
    error_message: Optional[str] = None


@dataclass
class UploadBundleResult:
    provider: str
    remote_dir: str
    items: list[UploadItemResult] = field(default_factory=list)
    success: bool = False
    error_message: Optional[str] = None
