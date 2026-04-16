import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from creart import it, add_creator

from src.logger import LoggerCreator
add_creator(LoggerCreator)
from src.config import ConfigCreator
add_creator(ConfigCreator)
from src.api import APICreator
add_creator(APICreator)
from src.grpc.manager import WMCreator
add_creator(WMCreator)
from src.measurer import MeasurerCreator
add_creator(MeasurerCreator)

from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram import Update

from extras.telegram_bot.src.config import bot_config
from extras.telegram_bot.src.handlers.download import dl_handler, status_handler, quality_handler, process_bot_job
from extras.telegram_bot.src.handlers.login import get_login_handler
from extras.telegram_bot.src.handlers.admin import logout_handler, whitelist_handler, blacklist_handler, gstatus_handler
from extras.telegram_bot.src.handlers.settings import settings_handler, settings_callback
from extras.telegram_bot.src.queue import JobQueue


async def start_handler(update: Update, context):
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"Welcome to AppleMusicDecrypt Bot!\nYour User ID: {user_id}\n\n"
        "Send /dl <url> to download a song/album/playlist.\n"
        "Send /status to check your queued jobs.\n"
        "Send /quality to check codecs."
    )


from src.api import WebAPI
from src.config import Config
from src.grpc.manager import WrapperManager
from src.rip import Ripper
from src.utils import run_sync
from extras.telegram_bot.src.db import user_db


async def post_init(app):
    await run_sync(it(WebAPI).init)
    await user_db.load_initial()

    url = it(Config).instance.url
    secure = it(Config).instance.secure
    await it(WrapperManager).init(url, secure)

    ripper = Ripper()
    app.bot_data['ripper'] = ripper

    job_queue = JobQueue(lambda job: process_bot_job(app, job), max_size=bot_config.queue.max_size)
    await job_queue.start()
    app.bot_data['job_queue'] = job_queue

    await it(WrapperManager).decrypt_init(
        on_success=ripper.on_decrypt_success,
        on_failure=ripper.on_decrypt_failed
    )

    print("Bot Services Initialized.")


def main():
    builder = ApplicationBuilder().post_init(post_init)
    if bot_config.bot.token:
        builder = builder.token(bot_config.bot.token)
    if bot_config.bot.base_url:
        builder = builder.base_url(bot_config.bot.base_url)

    app = builder.build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("dl", dl_handler, block=False))
    app.add_handler(get_login_handler())
    app.add_handler(CommandHandler("logout", logout_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("quality", quality_handler))
    app.add_handler(CommandHandler("whitelist", whitelist_handler))
    app.add_handler(CommandHandler("blacklist", blacklist_handler))
    app.add_handler(CommandHandler("gstatus", gstatus_handler))
    app.add_handler(CommandHandler("settings", settings_handler))
    app.add_handler(CallbackQueryHandler(settings_callback))

    print("Bot application built successfully. Starting polling...")
    app.run_polling()


if __name__ == '__main__':
    main()
