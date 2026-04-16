import asyncio
import unittest

from extras.telegram_bot.src.models import BotJob
from extras.telegram_bot.src.queue import JobQueue


class QueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_processes_jobs_in_fifo_order(self):
        processed = []

        async def processor(job):
            processed.append(job.job_id)

        queue = JobQueue(processor=processor, max_size=10)
        await queue.start()
        try:
            await queue.enqueue(BotJob(job_id='1', user_id=1, chat_id=1, request_url='a', request_type='song'))
            await queue.enqueue(BotJob(job_id='2', user_id=2, chat_id=2, request_url='b', request_type='song'))
            await asyncio.wait_for(queue.join(), timeout=2)
        finally:
            await queue.stop()

        self.assertEqual(processed, ['1', '2'])


if __name__ == '__main__':
    unittest.main()
