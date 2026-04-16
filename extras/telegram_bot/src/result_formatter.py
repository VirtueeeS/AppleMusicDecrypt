from extras.telegram_bot.src.models import BotJobResult


def format_job_result(result: BotJobResult) -> str:
    lines = [
        '处理完成',
        '',
        f'类型：{result.request_type}',
        f'成功：{result.success_count}',
        f'失败：{result.failed_count}',
        '',
    ]
    if result.successful_songs:
        lines.append('成功曲目：')
        for song in result.successful_songs:
            lines.append(f'- {song.title}')
        lines.append('')
    if result.failed_songs:
        lines.append('失败曲目：')
        for song in result.failed_songs:
            reason = song.error_message or '未知错误'
            lines.append(f'- {song.title} —— {reason}')
        lines.append('')
        lines.append('请单独发送失败歌曲的 Apple Music 单曲链接进行补传。')
        lines.append('补传任务将按普通队列顺序处理。')
    return '\n'.join(lines).strip()
