import unittest

from extras.telegram_bot.src.models import BotJobResult, SongProcessResult
from extras.telegram_bot.src.result_formatter import format_job_result


class ResultFormatterTests(unittest.TestCase):
    def test_formatter_lists_successes_and_failures_with_retry_hint(self):
        result = BotJobResult(
            job_id='job-1',
            request_type='album',
            request_url='https://music.apple.com/x',
            total_count=3,
            success_count=2,
            failed_count=1,
            successful_songs=[
                SongProcessResult(song_id='1', title='Song A', artist='Artist', album='Album', source_url='u1', status='success'),
                SongProcessResult(song_id='2', title='Song B', artist='Artist', album='Album', source_url='u2', status='success'),
            ],
            failed_songs=[
                SongProcessResult(song_id='3', title='Song C', artist='Artist', album='Album', source_url='u3', status='failed', error_message='上传失败：超时'),
            ],
        )

        text = format_job_result(result)

        self.assertIn('成功：2', text)
        self.assertIn('失败：1', text)
        self.assertIn('Song C —— 上传失败：超时', text)
        self.assertIn('单独发送失败歌曲的 Apple Music 单曲链接', text)


if __name__ == '__main__':
    unittest.main()
