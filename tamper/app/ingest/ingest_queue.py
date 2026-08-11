import asyncio
import logging
from .ingest_worker import IngestWorker
from .ingest import Ingest, IngestStatus

logger = logging.getLogger(__name__)


class IngestQueue:
    """
    An asynchronous queue for processing data ingest jobs.
    """

    def __init__(self, worker: IngestWorker, num_workers: int = 1):
        """
        :param worker: An ingest worker used by the background workers
        :param num_workers: The number of async background workers to use.
        """
        self.queue = asyncio.Queue()
        self._worker_tasks = []
        self.num_workers = num_workers
        self.worker = worker

    async def start(self):
        """Starts the background worker tasks."""
        for i in range(self.num_workers):
            self._worker_tasks.append(asyncio.create_task(self._run_worker(i)))

    async def stop(self):
        for task in self._worker_tasks:
            task.cancel()
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()

        self.queue.shutdown()
        while True:
            try:
                ingest: Ingest = self.queue.get_nowait()
                ingest.status = IngestStatus.FAILED
            except asyncio.QueueEmpty, asyncio.QueueShutDown:
                break

    def put_ingest(self, ingest: Ingest):
        self.queue.put_nowait(ingest)

    async def _run_worker(self, worker_id: int):
        logger.info("(ingest worker %s): Starting worker", worker_id)
        while True:
            try:
                ingest: Ingest = await self.queue.get()
            except asyncio.QueueShutDown:
                logger.info(
                    "(ingest worker %s): Queue shut down, stopping worker", worker_id
                )
                return

            logger.info(
                "(ingest worker %s): Processing ingest job %s", worker_id, ingest.id
            )
            try:
                ingest.status = IngestStatus.COMMITTING
                await asyncio.to_thread(self.worker.commit, ingest)
                logger.info(
                    "(ingest worker %s): Ingest %s processed", worker_id, ingest.id
                )
            except asyncio.CancelledError:
                ingest.status = IngestStatus.FAILED
                raise
            except Exception as e:
                ingest.status = IngestStatus.FAILED
                logger.exception(
                    "(ingest worker %s): Error processing ingest job %s: %s",
                    worker_id,
                    ingest.id,
                    str(e),
                )
