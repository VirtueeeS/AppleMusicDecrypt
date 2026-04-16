from extras.telegram_bot.src.result_formatter import format_job_result


async def send_job_summary(bot, job, result):
    await bot.send_message(chat_id=job.chat_id, text=format_job_result(result), reply_to_message_id=job.reply_message_id)
