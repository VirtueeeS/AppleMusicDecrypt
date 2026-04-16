import tomllib
from typing import Type

from creart import exists_module
from creart.creator import AbstractCreator, CreateTargetInfo
from pydantic import BaseModel, Field

CONFIG_VERSION = "0.0.10"


class Instance(BaseModel):
    url: str = "127.0.0.1:8080"
    secure: bool = False


class LocalInstance(BaseModel):
    enable: bool = False
    enableHardwareAcceleration: bool = False
    hardwareAccelerator: str = ""
    memorySize: str = "512M"
    cpuModel: str = "Cascadelake-Server-v5"
    showWindow: bool = False
    startArgs: str = "-host 0.0.0.0 -port 32767 -debug"


class Region(BaseModel):
    language: str = "zh-Hant-HK"
    languageNotExistWarning: bool = True


class Download(BaseModel):
    proxy: str = ""
    parallelNum: int = 1
    maxRunningTasks: int = 128
    appleCDNIP: str = ""
    codecAlternative: bool = True
    codecPriority: list[str] = ["alac", "ec3", "ac3", "aac"]
    atmosConventToM4a: bool = True
    failedSongNotPassIntegrityCheck: bool = False
    audioInfoFormat: str = ""
    songNameFormat: str = "{disk}-{tracknum:02d} {title}"
    dirPathFormat: str = "downloads/{album_artist}/{album}"
    playlistDirPathFormat: str = "downloads/playlists/{playlistName}"
    playlistSongNameFormat: str = "{playlistSongIndex:02d}. {artist} - {title}"
    saveLyrics: bool = True
    lyricsFormat: str = "lrc"
    lyricsExtra: list[str] = ["translation", "pronunciation"]
    saveCover: bool = True
    coverFormat: str = "jpg"
    coverSize: str = "5000x5000"
    maxSampleRate: int = 192000
    maxBitDepth: int = 24
    afterDownloaded: str = ""
    retryTime: int = 8
    maxWaitTime: int = 30


class Metadata(BaseModel):
    embedMetadata: list[str] = ["title", "artist", "album", "album_artist", "composer", "album_created",
                                "genre", "created", "track", "tracknum", "disk", "lyrics", "cover", "copyright",
                                "record_company", "upc", "isrc", "rtng"]


class UploadWebDAV(BaseModel):
    url: str = ""
    username: str = ""
    password: str = ""
    basePath: str = "/"
    timeout: int = 120


class UploadOpenList(BaseModel):
    url: str = ""
    username: str = ""
    password: str = ""
    token: str = ""
    basePath: str = "/"
    timeout: int = 120


class Upload(BaseModel):
    enable: bool = False
    provider: str = "webdav"
    tempDir: str = "tmp_upload"
    deleteLocalAfterUpload: bool = True
    webdav: UploadWebDAV = Field(default_factory=UploadWebDAV)
    openlist: UploadOpenList = Field(default_factory=UploadOpenList)


class Config(BaseModel):
    version: str = "0.0.0"
    region: Region = Field(default_factory=Region)
    instance: Instance = Field(default_factory=Instance)
    localInstance: LocalInstance = Field(default_factory=LocalInstance)
    download: Download = Field(default_factory=Download)
    metadata: Metadata = Field(default_factory=Metadata)
    upload: Upload = Field(default_factory=Upload)

    @classmethod
    def load_from_config(cls, config_file: str = "config.toml"):
        with open(config_file, "r", encoding="utf-8") as f:
            config = tomllib.loads(f.read())
        return cls.model_validate(config)


class ConfigCreator(AbstractCreator):
    targets = (
        CreateTargetInfo("src.config", "Config"),
    )

    @staticmethod
    def available() -> bool:
        return exists_module("src.config")

    @staticmethod
    def create(create_type: Type[Config]) -> Config:
        return create_type.load_from_config()
