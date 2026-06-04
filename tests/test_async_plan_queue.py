"""Tests for tamper.plans.async_plan_queue — the AsyncPlanQueue worker pool."""

import asyncio
import threading
from types import SimpleNamespace

import pytest
from rdflib import Graph, Node

from tamper.plans import AsyncPlanQueue, OperationPlanExecutor, PlanQueueShutDown


# ---------------------------------------------------------------------------
# Fake executors
# ---------------------------------------------------------------------------


class RecordingExecutor(OperationPlanExecutor):
    """Records every call and returns a fresh result graph for each one."""

    def __init__(self):
        self.calls: list[SimpleNamespace] = []

    def execute(self, plan, seed_graph, initial_variables):
        result = Graph()
        self.calls.append(
            SimpleNamespace(
                plan=plan,
                seed_graph=seed_graph,
                initial_variables=initial_variables,
                result=result,
            )
        )
        return result


class FailingExecutor(OperationPlanExecutor):
    """Always raises, to exercise error propagation to the plan future."""

    def __init__(self, exc: Exception):
        self.exc = exc

    def execute(self, plan, seed_graph, initial_variables):
        raise self.exc


class BlockingExecutor(OperationPlanExecutor):
    """Blocks inside ``execute`` until released, to test in-flight shutdown."""

    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def execute(self, plan, seed_graph, initial_variables):
        self.started.set()
        # bounded so a misbehaving test can't hang the worker thread forever
        self.release.wait(5)
        return Graph()


class BarrierExecutor(OperationPlanExecutor):
    """Each call waits on a shared barrier; only concurrent calls get through.

    With ``parties`` set to the expected concurrency, a single worker can never
    satisfy the barrier and ``execute`` raises ``BrokenBarrierError`` instead.
    """

    def __init__(self, parties: int):
        self.barrier = threading.Barrier(parties, timeout=5)

    def execute(self, plan, seed_graph, initial_variables):
        self.barrier.wait()
        return Graph()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _plan_graph() -> Graph:
    """A distinct (empty) graph standing in for a plan; identity is what matters."""
    return Graph()


async def _started(executor: BlockingExecutor) -> bool:
    """Await the executor entering ``execute`` without blocking the event loop."""
    return await asyncio.to_thread(executor.started.wait, 5)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestPlanExecution:
    def test_put_plan_resolves_future_with_executor_result(self):
        async def scenario():
            executor = RecordingExecutor()
            queue = AsyncPlanQueue(executor)
            await queue.start()
            try:
                plan, seed, variables = _plan_graph(), Graph(), {}
                future = queue.put_plan(plan, seed, variables)
                result = await asyncio.wait_for(future, timeout=5)
            finally:
                await queue.stop()

            assert len(executor.calls) == 1
            # the future resolves with exactly the graph the executor returned
            assert result is executor.calls[0].result

        asyncio.run(scenario())

    def test_executor_receives_the_plan_arguments_unchanged(self):
        async def scenario():
            executor = RecordingExecutor()
            queue = AsyncPlanQueue(executor)
            await queue.start()
            try:
                plan, seed = _plan_graph(), Graph()
                variables: dict[Node, Node] = {}
                await asyncio.wait_for(queue.put_plan(plan, seed, variables), timeout=5)
            finally:
                await queue.stop()

            call = executor.calls[0]
            assert call.plan is plan
            assert call.seed_graph is seed
            assert call.initial_variables is variables

        asyncio.run(scenario())

    def test_single_worker_processes_plans_in_fifo_order(self):
        async def scenario():
            executor = RecordingExecutor()
            queue = AsyncPlanQueue(executor, num_workers=1)
            await queue.start()
            try:
                plans = [_plan_graph() for _ in range(5)]
                futures = [queue.put_plan(p, Graph(), {}) for p in plans]
                await asyncio.wait_for(asyncio.gather(*futures), timeout=5)
            finally:
                await queue.stop()

            assert [call.plan for call in executor.calls] == plans

        asyncio.run(scenario())

    def test_multiple_workers_run_plans_concurrently(self):
        async def scenario():
            # barrier of 2 only completes if two workers are inside execute at once
            executor = BarrierExecutor(parties=2)
            queue = AsyncPlanQueue(executor, num_workers=2)
            await queue.start()
            try:
                futures = [queue.put_plan(_plan_graph(), Graph(), {}) for _ in range(2)]
                # both resolve (no BrokenBarrierError) => they ran concurrently
                await asyncio.wait_for(asyncio.gather(*futures), timeout=5)
            finally:
                await queue.stop()

        asyncio.run(scenario())


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


class TestErrorPropagation:
    def test_executor_exception_propagates_to_future(self):
        async def scenario():
            boom = ValueError("transform blew up")
            queue = AsyncPlanQueue(FailingExecutor(boom))
            await queue.start()
            try:
                future = queue.put_plan(_plan_graph(), Graph(), {})
                with pytest.raises(ValueError, match="transform blew up") as exc_info:
                    await asyncio.wait_for(future, timeout=5)
                assert exc_info.value is boom
            finally:
                await queue.stop()

        asyncio.run(scenario())

    def test_worker_survives_a_failing_plan_and_keeps_serving(self):
        async def scenario():
            # a failing plan must not kill the worker; later plans still run
            class FlakyExecutor(OperationPlanExecutor):
                def __init__(self):
                    self.n = 0

                def execute(self, plan, seed_graph, initial_variables):
                    self.n += 1
                    if self.n == 1:
                        raise RuntimeError("first one fails")
                    return Graph()

            queue = AsyncPlanQueue(FlakyExecutor(), num_workers=1)
            await queue.start()
            try:
                first = queue.put_plan(_plan_graph(), Graph(), {})
                with pytest.raises(RuntimeError):
                    await asyncio.wait_for(first, timeout=5)

                second = queue.put_plan(_plan_graph(), Graph(), {})
                # the worker recovered and handled the next plan
                assert isinstance(await asyncio.wait_for(second, timeout=5), Graph)
            finally:
                await queue.stop()

        asyncio.run(scenario())


# ---------------------------------------------------------------------------
# Shutdown semantics
# ---------------------------------------------------------------------------


class TestShutdown:
    def test_stop_clears_worker_tasks(self):
        async def scenario():
            queue = AsyncPlanQueue(RecordingExecutor(), num_workers=3)
            await queue.start()
            assert len(queue._worker_tasks) == 3
            await queue.stop()
            assert queue._worker_tasks == []

        asyncio.run(scenario())

    def test_stop_is_idempotent(self):
        async def scenario():
            queue = AsyncPlanQueue(RecordingExecutor())
            await queue.start()
            await queue.stop()
            # a second stop on an already-drained queue must not raise
            await queue.stop()

        asyncio.run(scenario())

    def test_stop_fails_inflight_plan_with_PlanQueueShutDown(self):
        async def scenario():
            executor = BlockingExecutor()
            queue = AsyncPlanQueue(executor, num_workers=1)
            await queue.start()

            future = queue.put_plan(_plan_graph(), Graph(), {})
            assert await _started(executor), "executor never entered execute"

            # stop() while the plan is mid-flight; let the thread unwind afterwards
            stop_task = asyncio.create_task(queue.stop())
            executor.release.set()
            await asyncio.wait_for(stop_task, timeout=5)

            with pytest.raises(PlanQueueShutDown):
                await asyncio.wait_for(future, timeout=5)

        asyncio.run(scenario())

    def test_stop_fails_pending_plan_with_queue_shutdown(self):
        async def scenario():
            executor = BlockingExecutor()
            queue = AsyncPlanQueue(executor, num_workers=1)
            await queue.start()

            # first plan occupies the only worker...
            inflight = queue.put_plan(_plan_graph(), Graph(), {})
            assert await _started(executor)
            # ...so this second plan is still waiting in the queue
            pending = queue.put_plan(_plan_graph(), Graph(), {})

            stop_task = asyncio.create_task(queue.stop())
            executor.release.set()
            await asyncio.wait_for(stop_task, timeout=5)

            # in-flight plan is failed by its worker
            with pytest.raises(PlanQueueShutDown):
                await asyncio.wait_for(inflight, timeout=5)
            # the never-started plan is failed by the drain loop
            with pytest.raises(asyncio.QueueShutDown):
                await asyncio.wait_for(pending, timeout=5)

        asyncio.run(scenario())

    def test_put_plan_after_stop_raises(self):
        async def scenario():
            queue = AsyncPlanQueue(RecordingExecutor())
            await queue.start()
            await queue.stop()
            with pytest.raises(asyncio.QueueShutDown):
                queue.put_plan(_plan_graph(), Graph(), {})

        asyncio.run(scenario())
