import tempfile
import unittest
from pathlib import Path

from src.upload.models import LocalFiles, UploadItemResult
from src.upload.service import UploadService


class FakeUploader:
    def __init__(self):
        self.created_dirs = []
        self.uploaded = []

    def ensure_dir(self, remote_dir: str):
        self.created_dirs.append(remote_dir)

    def upload_file(self, local_path: Path, remote_path: str):
        self.uploaded.append((local_path.name, remote_path))
        return UploadItemResult(kind=local_path.suffix, local_path=str(local_path), remote_path=remote_path, success=True)


class UploadServiceTests(unittest.TestCase):
    def test_upload_bundle_uses_relative_directory_for_all_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio = tmp_path / '01 Song.m4a'
            lyrics = tmp_path / '01 Song.lrc'
            cover = tmp_path / 'cover.jpg'
            for path in [audio, lyrics, cover]:
                path.write_bytes(b'data')

            files = LocalFiles(
                audio_path=audio,
                lyrics_path=lyrics,
                cover_path=cover,
                work_dir=tmp_path,
                remote_dir='downloads/Artist/Album',
                display_name='Song',
            )
            uploader = FakeUploader()
            service = UploadService(uploader=uploader, provider='webdav')

            result = service.upload(files)

            self.assertTrue(result.success)
            self.assertEqual(result.remote_dir, 'downloads/Artist/Album')
            self.assertEqual(
                uploader.uploaded,
                [
                    ('01 Song.m4a', 'downloads/Artist/Album/01 Song.m4a'),
                    ('01 Song.lrc', 'downloads/Artist/Album/01 Song.lrc'),
                    ('cover.jpg', 'downloads/Artist/Album/cover.jpg'),
                ],
            )


if __name__ == '__main__':
    unittest.main()
