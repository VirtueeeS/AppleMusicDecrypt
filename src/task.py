import asyncio

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional, TYPE_CHECKING

from src.logger import RipLogger
from src.metadata import SongMetadata
from src.models import PlaylistInfo
from src.types import SongInfo, M3U8Info, ParentDoneHandler

if TYPE_CHECKING:
    from src.upload.models import LocalFiles, UploadBundleResult


class Status(StrEnum):
    WAITING = "WAITING"
    DOWNLOADING = "DOWNLOADING"
    DECRYPTING = "DECRYPTING"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass
class Task:
    adamId: str
    parentDone: Optional[ParentDoneHandler] = None
    playlist: Optional[PlaylistInfo] = None
    status: Status = Status.WAITING
    info: Optional[SongInfo] = None
    m3u8Info: Optional[M3U8Info] = None
    metadata: Optional[SongMetadata] = None
    logger: Optional[RipLogger] = None
    decrypted_samples_futures: dict[int, asyncio.Future] = field(default_factory=dict)
    error: Optional[Exception] = None
    source_url: str = ""
    saved_files: Optional['LocalFiles'] = None
    upload_result: Optional['UploadBundleResult'] = None

    def update_status(self, status: Status):
        self.status = status
