import asyncio
from collections import deque
from datetime import datetime, UTC


class QueueFullError(Exception):
    pass


class JobQueue:
    def __init__(self, processor, max_size: int = 20):
        self.processor = processor
        self.max_size = max_size
        self.queue = asyncio.Queue()
        self.pending_jobs = deque()
        self.current_job = None
        self._worker_task = None

    async def start(self):
        if not self._worker_task:
            self._worker_task = asyncio.create_task(self._run())

    async def stop(self):
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    async def enqueue(self, job):
        if len(self.pending_jobs) >= self.max_size:
            raise QueueFullError('queue full')
        self.pending_jobs.append(job)
        await self.queue.put(job)
        return len(self.pending_jobs)

    async def join(self):
        await self.queue.join()

    async def _run(self):
        while True:
            job = await self.queue.get()
            try:
                if self.pending_jobs and self.pending_jobs[0].job_id == job.job_id:
                    self.pending_jobs.popleft()
                else:
                    self.pending_jobs = deque(item for item in self.pending_jobs if item.job_id != job.job_id)
                self.current_job = job
                job.status = 'running'
                job.started_at = datetime.now(UTC)
                await self.processor(job)
                if job.status == 'running':
                    job.status = 'done'
                job.finished_at = datetime.now(UTC)
            except Exception:
                job.status = 'failed'
                job.finished_at = datetime.now(UTC)
                raise
            finally:
                self.current_job = None
                self.queue.task_done()

    def describe_user(self, user_id: int):
        current = self.current_job if self.current_job and self.current_job.user_id == user_id else None
        pending = [job for job in self.pending_jobs if job.user_id == user_id]
        return current, pending
