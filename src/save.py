import os
from pathlib import Path

from creart import it

from src.config import Config
from src.metadata import SongMetadata
from src.models import PlaylistInfo
from src.upload.models import LocalFiles
from src.utils import ttml_convent, get_song_name_and_dir_path, get_suffix


def save(song: bytes, codec: str, metadata: SongMetadata, playlist: PlaylistInfo = None):
    song_name, remote_dir = get_song_name_and_dir_path(codec.upper(), metadata, playlist)
    upload_enabled = it(Config).upload.enable
    if upload_enabled:
        work_dir = Path(it(Config).upload.tempDir) / remote_dir
    else:
        work_dir = remote_dir
    if not work_dir.exists() or not work_dir.is_dir():
        os.makedirs(work_dir.absolute(), exist_ok=True)
    song_path = work_dir / Path(song_name + get_suffix(codec, it(Config).download.atmosConventToM4a))
    with open(song_path.absolute(), "wb") as f:
        f.write(song)

    cover_path = None
    if it(Config).download.saveCover and not playlist:
        cover_path = work_dir / Path(f"cover.{it(Config).download.coverFormat}")
        with open(cover_path.absolute(), "wb") as f:
            f.write(metadata.cover)

    lyrics_path = None
    if it(Config).download.saveLyrics and metadata.lyrics:
        lrc = ttml_convent(metadata.lyrics)
        if lrc:
            if it(Config).download.lyricsFormat == "ttml":
                lyrics_path = work_dir / Path(song_name + ".ttml")
            else:
                lyrics_path = work_dir / Path(song_name + ".lrc")
            lyrics_path.write_text(lrc, encoding="utf-8")

    return LocalFiles(
        audio_path=song_path.absolute(),
        lyrics_path=lyrics_path.absolute() if lyrics_path else None,
        cover_path=cover_path.absolute() if cover_path else None,
        work_dir=work_dir.absolute(),
        remote_dir=remote_dir.as_posix(),
        display_name=song_name,
    )
