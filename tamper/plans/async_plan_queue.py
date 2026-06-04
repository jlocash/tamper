import asyncio
import logging
from rdflib import Graph, Node
from tamper.plans import OperationPlan, OperationPlanExecutor

logger = logging.getLogger(__name__)


class PlanQueueShutDown(Exception):
    """Raised on outstanding plan futures when the queue is shut down before they complete."""


class AsyncPlanQueue:
    """
    An asynchronous queue for executing operation plans.
    """

    def __init__(self, plan_executor: OperationPlanExecutor, num_workers: int = 1):
        """
        :param plan_executor: A plan executor used by the background workers
        :param num_workers: The number of async background workers to use.
        """
        self.queue = asyncio.Queue()
        self._worker_tasks = []
        self.num_workers = num_workers
        self.plan_executor = plan_executor

    async def start(self):
        """Starts the background worker tasks."""
        for i in range(self.num_workers):
            self._worker_tasks.append(asyncio.create_task(self._run_worker(i)))

    async def stop(self):
        """Gracefully shuts down the queue and fails any plans that did not complete.

        Pending plans are discarded and the in-flight plan (if any) is interrupted;
        the underlying transform may keep running in its worker thread until it finishes
        on its own, but its result is abandoned. Every outstanding future is resolved with
        an ``asyncio.QueueShutDown`` exception so awaiting callers are not left hanging.
        """
        # interrupt workers first so nothing keeps pulling from the queue;
        # each worker fails its own in-flight plan as it unwinds (see _run_worker)
        for task in self._worker_tasks:
            task.cancel()
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()

        # close the queue to new plans, then fail the ones still waiting to start
        self.queue.shutdown()
        while True:
            try:
                *_, future = self.queue.get_nowait()
            except asyncio.QueueEmpty, asyncio.QueueShutDown:
                break
            if not future.done():
                future.set_exception(
                    asyncio.QueueShutDown("Plan queue is shutting down")
                )

    def put_plan(
        self,
        plan: OperationPlan,
        seed_graph: Graph,
        initial_variables: dict[Node, Node],
    ) -> asyncio.Future:
        """Enqueues a plan for execution and returns a future resolved with its result graph.

        Must be called from within the event loop running the queue's workers, so the
        returned future is bound to that loop. The queue is unbounded, so the put never
        blocks (``put_nowait`` only raises once the queue has been shut down).
        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.queue.put_nowait((plan, seed_graph, initial_variables, future))
        return future

    async def _run_worker(self, worker_id: int):
        logger.info(f"(worker {worker_id}): Starting worker")
        while True:
            try:
                (
                    plan,
                    seed_graph,
                    initial_variables,
                    future,
                ) = await self.queue.get()
            except asyncio.QueueShutDown:
                logger.info(f"(worker {worker_id}): Queue shut down, stopping worker")
                return

            logger.info(f"(worker {worker_id}): Executing plan {plan.identifier}")
            try:
                result_graph = await asyncio.to_thread(
                    self.plan_executor.execute,
                    plan,
                    seed_graph,
                    initial_variables,
                )
                logger.info(f"(worker {worker_id}): Plan {plan} completed")
                future.set_result(result_graph)
            except asyncio.CancelledError:
                # shutting down mid-execution: this plan is no longer in the queue,
                # so the worker is the only one that can fail its future
                if not future.done():
                    future.set_exception(
                        PlanQueueShutDown("Plan queue is shutting down")
                    )
                raise
            except Exception as e:
                logger.error(
                    f"(worker {worker_id}): Error executing plan {plan.identifier} failed: {e}"
                )
                future.set_exception(e)
