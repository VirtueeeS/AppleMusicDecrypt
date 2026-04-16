from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional


@dataclass
class SongProcessResult:
    song_id: str
    title: str
    artist: str
    album: str
    source_url: str
    status: str
    error_message: Optional[str] = None
    remote_dir: str = ""
    remote_files: list[str] = field(default_factory=list)


@dataclass
class BotJob:
    job_id: str
    user_id: int
    chat_id: int
    request_url: str
    request_type: str
    codec: str = 'alac'
    language: str = 'en-US'
    force_download: bool = False
    reply_message_id: Optional[int] = None
    status: str = 'queued'
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    song_results: list[SongProcessResult] = field(default_factory=list)


@dataclass
class BotJobResult:
    job_id: str
    request_type: str
    request_url: str
    total_count: int
    success_count: int
    failed_count: int
    successful_songs: list[SongProcessResult] = field(default_factory=list)
    failed_songs: list[SongProcessResult] = field(default_factory=list)
