import uuid

from tabulate import tabulate

from telegram import Update
from telegram.ext import ContextTypes

import m3u8
from creart import it

from extras.telegram_bot.src.auth import check_auth
from extras.telegram_bot.src.config import bot_config
from extras.telegram_bot.src.db import user_db
from extras.telegram_bot.src.handlers.notifications import send_job_summary
from extras.telegram_bot.src.models import BotJob, BotJobResult, SongProcessResult
from extras.telegram_bot.src.queue import QueueFullError

from src.api import WebAPI
from src.config import Config
from src.flags import Flags
from src.grpc.manager import WrapperManager
from src.metadata import SongMetadata
from src.task import Status
from src.url import AppleMusicURL, URLType, Song
from src.utils import get_codec_from_codec_id, playlist_write_song_index


SUPPORTED_CODECS = ["alac", "ec3", "aac", "aac-binaural", "aac-downmix", "aac-legacy", "ac3"]


def _resolve_language_code(telegram_language: str | None, fallback: str) -> str:
    lang_map = {
        "zh-hans": "zh-Hans-CN",
        "zh-hant": "zh-Hant-TW",
        "en": "en-US",
    }
    if not telegram_language:
        return fallback
    return lang_map.get(telegram_language.lower(), telegram_language)


def _parse_dl_args(args: list[str]):
    force_download = False
    codec_override = None
    url_str = None

    i = 0
    while i < len(args):
        if args[i] == '-f':
            force_download = True
            i += 1
        elif args[i] == '-c':
            if i + 1 >= len(args):
                raise ValueError('Missing codec value after -c')
            codec_override = args[i + 1]
            i += 2
        else:
            url_str = args[i]
            i += 1

    if not url_str:
        raise ValueError('Missing Apple Music URL.')
    return force_download, codec_override, url_str


@check_auth
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue = context.bot_data.get('job_queue')
    if not queue:
        await update.message.reply_text('队列尚未初始化。')
        return

    current, pending = queue.describe_user(update.effective_user.id)
    lines = []
    if current:
        lines.append(f'当前执行：{current.request_type} {current.request_url}')
    if pending:
        lines.append('排队中的任务：')
        for index, job in enumerate(pending, start=1):
            lines.append(f'- 第 {index} 位：{job.request_type} {job.request_url}')
    if not lines:
        lines.append('你当前没有排队中的任务。')
    await update.message.reply_text('\n'.join(lines))


@check_auth
async def quality_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        codecs = it(Config).download.codecPriority
        await update.message.reply_text(
            f"Available system codecs: {', '.join(codecs)}\n\nUsage to inspect a song: `/quality <url>`",
            parse_mode='Markdown')
        return

    raw_url = context.args[0]
    url_obj = AppleMusicURL.parse_url(raw_url)
    if not url_obj or url_obj.type != URLType.Song:
        await update.message.reply_text('Please provide a valid single Apple Music Song URL.')
        return

    msg = await update.message.reply_text('Fetching audio qualities...')
    try:
        user_settings = await user_db.get_user_settings(update.effective_user.id)
        language = user_settings.get('language', bot_config.user_default.language)
        if language == 'follow-user':
            language = update.effective_user.language_code or it(Config).region.language

        m3u8_url = await it(WrapperManager).m3u8(url_obj.id)
        if not m3u8_url:
            await msg.edit_text('Failed to get M3U8 URL from WrapperManager.')
            return

        raw_metadata = await it(WebAPI).get_song_info(url_obj.id, url_obj.storefront, language)
        if not raw_metadata:
            await msg.edit_text('Failed to fetch song metadata.')
            return

        metadata = SongMetadata.parse_from_song_data(raw_metadata)
        parsed_m3u8 = m3u8.loads(await it(WebAPI).download_m3u8(m3u8_url), uri=m3u8_url)

        headers = ["Codec ID", "Codec", "Bitrate", "Average Bitrate", "Channels", "Sample Rate", "Bit Depth"]
        table_data = []
        for playlist in parsed_m3u8.playlists:
            codec = get_codec_from_codec_id(playlist.stream_info.audio)
            if codec:
                codec_id = playlist.stream_info.audio
                bitrate = playlist.stream_info.bandwidth
                average_bitrate = getattr(playlist.stream_info, 'average_bandwidth', None)
                channels = playlist.media[0].channels if playlist.media else None
                sample_rate = playlist.media[0].extras.get('sample_rate', None) if playlist.media else None
                bit_depth = playlist.media[0].extras.get('bit_depth', None) if playlist.media else None
                table_data.append([codec_id, codec, bitrate, average_bitrate, channels, sample_rate, bit_depth])

        if not table_data:
            await msg.edit_text('No playable audio tracks found in M3U8.')
            return

        table_str = tabulate(table_data, headers=headers, tablefmt='presto')
        title_text = f"Available audio qualities for song: {metadata.artist} - {metadata.title}\n"
        await msg.edit_text(f"{title_text}```text\n{table_str}\n```", parse_mode='Markdown')

    except Exception as e:
        await msg.edit_text(f'Error checking quality: {str(e)}')


@check_auth
async def dl_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        force_download, codec_override, raw_url = _parse_dl_args(context.args)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    url_obj = AppleMusicURL.parse_url(raw_url)
    if not url_obj:
        await update.message.reply_text('Invalid Apple Music URL.')
        return

    if url_obj.type.lower() not in bot_config.limits.allowed_types:
        await update.message.reply_text(f'Error: Downloading {url_obj.type} is disabled by the limits config.')
        return

    user_settings = await user_db.get_user_settings(update.effective_user.id)
    codec = (codec_override or user_settings.get('default_codec', bot_config.user_default.default_codec)).lower()
    if codec not in SUPPORTED_CODECS:
        await update.message.reply_text(f"Invalid codec `{codec}`. Available: {', '.join(SUPPORTED_CODECS)}", parse_mode='Markdown')
        return

    language = user_settings.get('language', bot_config.user_default.language)
    if language == 'follow-user':
        language = _resolve_language_code(update.effective_user.language_code, it(Config).region.language)

    queue = context.bot_data.get('job_queue')
    if not queue:
        await update.message.reply_text('队列尚未初始化。')
        return

    job = BotJob(
        job_id=uuid.uuid4().hex,
        user_id=update.effective_user.id,
        chat_id=update.effective_chat.id,
        request_url=raw_url,
        request_type=url_obj.type,
        codec=codec,
        language=language,
        force_download=force_download,
        reply_message_id=update.message.message_id,
    )

    try:
        position = await queue.enqueue(job)
    except QueueFullError:
        await update.message.reply_text('当前队列已满，请稍后再试。')
        return

    await update.message.reply_text(
        f'已加入队列\n任务类型：{job.request_type}\n当前排队位置：{position}',
        reply_to_message_id=update.message.message_id,
    )


async def _collect_tracks(url_obj, language: str):
    songs_to_rip = []
    if url_obj.type == URLType.Song:
        song_info = await it(WebAPI).get_song_info(url_obj.id, url_obj.storefront, language)
        if song_info and song_info.data:
            duration_sec = song_info.data[0].attributes.durationInMillis / 1000
            if duration_sec > bot_config.limits.max_song_duration_sec:
                raise ValueError(f'单曲时长 {duration_sec:.0f}s 超过限制 {bot_config.limits.max_song_duration_sec}s')
        songs_to_rip.append((Song(id=url_obj.id, storefront=url_obj.storefront, url=url_obj.url, type=URLType.Song), None))
    elif url_obj.type == URLType.Album:
        album_info = await it(WebAPI).get_album_info(url_obj.id, url_obj.storefront, language)
        tracks = album_info.data[0].relationships.tracks.data if album_info and album_info.data else []
        if len(tracks) > bot_config.limits.max_tracks:
            raise ValueError(f'专辑曲目数 {len(tracks)} 超过限制 {bot_config.limits.max_tracks}')
        total_duration_sec = sum([t.attributes.durationInMillis / 1000 for t in tracks if getattr(t.attributes, 'durationInMillis', 0)])
        if total_duration_sec > bot_config.limits.max_total_duration_sec:
            raise ValueError(f'专辑总时长 {total_duration_sec:.0f}s 超过限制 {bot_config.limits.max_total_duration_sec}s')
        for track in tracks:
            songs_to_rip.append((Song(id=track.id, storefront=url_obj.storefront, url=f'https://music.apple.com/{url_obj.storefront}/song/{track.id}', type=URLType.Song), None))
    elif url_obj.type == URLType.Playlist:
        playlist_info = await it(WebAPI).get_playlist_info_and_tracks(url_obj.id, url_obj.storefront, language)
        tracks = playlist_info.data[0].relationships.tracks.data if playlist_info and playlist_info.data else []
        if len(tracks) > bot_config.limits.max_tracks:
            raise ValueError(f'歌单曲目数 {len(tracks)} 超过限制 {bot_config.limits.max_tracks}')
        total_duration_sec = sum([t.attributes.durationInMillis / 1000 for t in tracks if getattr(t.attributes, 'durationInMillis', 0)])
        if total_duration_sec > bot_config.limits.max_total_duration_sec:
            raise ValueError(f'歌单总时长 {total_duration_sec:.0f}s 超过限制 {bot_config.limits.max_total_duration_sec}s')
        playlist_info = playlist_write_song_index(playlist_info)
        for track in tracks:
            songs_to_rip.append((Song(id=track.id, storefront=url_obj.storefront, url=f'https://music.apple.com/{url_obj.storefront}/song/{track.id}', type=URLType.Song), playlist_info))
    elif url_obj.type == URLType.Artist:
        artist_info = await it(WebAPI).get_artist_info(url_obj.id, url_obj.storefront, language)
        albums = getattr(artist_info.data[0].relationships.albums, 'data', []) if artist_info and artist_info.data and getattr(artist_info.data[0].relationships, 'albums', None) else []
        all_tracks = []
        for album in albums:
            album_info = await it(WebAPI).get_album_info(album.id, url_obj.storefront, language)
            if album_info and album_info.data:
                all_tracks.extend(album_info.data[0].relationships.tracks.data)
        if len(all_tracks) > bot_config.limits.max_tracks:
            raise ValueError(f'艺术家曲目数 {len(all_tracks)} 超过限制 {bot_config.limits.max_tracks}')
        total_duration_sec = sum([t.attributes.durationInMillis / 1000 for t in all_tracks if getattr(t.attributes, 'durationInMillis', 0)])
        if total_duration_sec > bot_config.limits.max_total_duration_sec:
            raise ValueError(f'艺术家总时长 {total_duration_sec:.0f}s 超过限制 {bot_config.limits.max_total_duration_sec}s')
        for track in all_tracks:
            songs_to_rip.append((Song(id=track.id, storefront=url_obj.storefront, url=f'https://music.apple.com/{url_obj.storefront}/song/{track.id}', type=URLType.Song), None))
    return songs_to_rip


def _task_to_song_result(task, fallback_song: Song) -> SongProcessResult:
    if task is None:
        return SongProcessResult(
            song_id=fallback_song.id,
            title=fallback_song.id,
            artist='',
            album='',
            source_url=fallback_song.url,
            status='failed',
            error_message='任务未返回结果',
        )
    title = task.metadata.title if task.metadata else fallback_song.id
    artist = task.metadata.artist if task.metadata else ''
    album = task.metadata.album if task.metadata else ''
    remote_dir = ''
    remote_files = []
    if task.upload_result:
        remote_dir = task.upload_result.remote_dir
        remote_files = [item.remote_path for item in task.upload_result.items if item.success]
    elif task.saved_files:
        remote_dir = task.saved_files.remote_dir
    if task.status == Status.DONE:
        return SongProcessResult(song_id=task.adamId, title=title, artist=artist, album=album, source_url=task.source_url or fallback_song.url, status='success', remote_dir=remote_dir, remote_files=remote_files)
    return SongProcessResult(song_id=task.adamId, title=title, artist=artist, album=album, source_url=task.source_url or fallback_song.url, status='failed', error_message=str(task.error) if task.error else '未知错误', remote_dir=remote_dir, remote_files=remote_files)


def _build_job_result(job: BotJob, song_results: list[SongProcessResult]) -> BotJobResult:
    successful = [song for song in song_results if song.status == 'success']
    failed = [song for song in song_results if song.status != 'success']
    return BotJobResult(
        job_id=job.job_id,
        request_type=job.request_type,
        request_url=job.request_url,
        total_count=len(song_results),
        success_count=len(successful),
        failed_count=len(failed),
        successful_songs=successful,
        failed_songs=failed,
    )


async def process_bot_job(app, job: BotJob):
    await app.bot.send_message(chat_id=job.chat_id, text='任务开始处理，请等待完成结果。', reply_to_message_id=job.reply_message_id)
    url_obj = AppleMusicURL.parse_url(job.request_url)
    if not url_obj:
        result = BotJobResult(job_id=job.job_id, request_type=job.request_type, request_url=job.request_url, total_count=1, success_count=0, failed_count=1, failed_songs=[SongProcessResult(song_id='', title=job.request_url, artist='', album='', source_url=job.request_url, status='failed', error_message='链接无效')])
        await send_job_summary(app.bot, job, result)
        return

    try:
        songs_to_rip = await _collect_tracks(url_obj, job.language)
    except Exception as exc:
        result = BotJobResult(job_id=job.job_id, request_type=job.request_type, request_url=job.request_url, total_count=1, success_count=0, failed_count=1, failed_songs=[SongProcessResult(song_id=url_obj.id, title=url_obj.id, artist='', album='', source_url=job.request_url, status='failed', error_message=str(exc))])
        await send_job_summary(app.bot, job, result)
        return

    ripper = app.bot_data['ripper']
    flags = Flags(force_save=job.force_download, language=job.language)
    results = []
    for song_obj, playlist in songs_to_rip:
        task = await ripper.rip_song(song_obj, job.codec, flags, playlist=playlist, timeout_sec=bot_config.limits.task_timeout_sec)
        results.append(_task_to_song_result(task, song_obj))

    job.song_results = results
    summary = _build_job_result(job, results)
    await send_job_summary(app.bot, job, summary)
