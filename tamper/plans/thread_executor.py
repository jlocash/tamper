from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime
from os import PathLike
from pathlib import Path

from rdflib import Graph, Node, URIRef

from tamper.core.operation import OperationURI
from tamper.ops.validation import validate_operations
from tamper.vocabularies._TAMPER import TAMPER
from tamper.ops.transcode import Transcode
from tamper.ops.audio import ResampleAudio
from tamper.ops.compress import Compress
from tamper.ops.image import (
    AddGaussianNoise,
    Resize,
    MedianFilter,
    GaussianBlur,
    CropImage,
)

from .operation_plan import OperationPlanExecutor
from tamper.core import Operation, OperationPlan, PlanStep, MediaAsset

operation_map: dict[URIRef, type[Operation]] = {
    TAMPER.Compress: Compress,
    TAMPER.Transcode: Transcode,
    TAMPER.AddGaussianNoise: AddGaussianNoise,
    TAMPER.Resize: Resize,
    TAMPER.MedianFilter: MedianFilter,
    TAMPER.GaussianBlur: GaussianBlur,
    TAMPER.ResampleAudio: ResampleAudio,
    TAMPER.CropImage: CropImage,
}


def materialize_operations(plan: OperationPlan) -> tuple[Graph, dict[Node, Node]]:
    """
    Eagerly materializes all operations in the plan graph. This is done so SHACL validation
    can be run on the resulting graph prior to the plan actually executing

    :returns: A dictionary mapping step nodes in ``plan`` to operation nodes in ``graph``
    :raises GraphValidationError: if any operation contains an invalid shape
    """
    result = Graph(store="Oxigraph")
    step_to_op = {}
    for step in plan.steps:
        # TODO: Implement support for an operation registry so
        # users can register their own operation types
        op_type = step.operation_type
        if op_type not in operation_map:
            raise ValueError(f"Unsupported operation type {op_type}")

        op_uri = OperationURI()
        op = operation_map[op_type].new(result, op_uri)
        params = step.parameters
        for p, o in params.graph.predicate_objects(params.identifier):
            op[p] = o

        step_to_op[step.identifier] = op_uri

    # throw if plan has bad operation parameters
    validate_operations(result)

    return result, step_to_op


class StepExecutor:
    def __init__(self, step: PlanStep, out_dir: Path):
        self.step = step
        self.out_dir = out_dir

    def execute(self, subgraph: Graph, mapping: dict[Node, Node]) -> tuple[Node, Graph]:
        print(f"Executing step {self.step}")

        op_uri = mapping.pop(self.step.identifier)

        # instantiate operation and pass parameters
        # NOTE: the operation should be pre-materialized by the plan executor
        op = operation_map[self.step.operation_type](subgraph, op_uri)

        # TODO: For now, mapping only has one entry. To support multiple,
        # additional context needs to be carried in the step alongside var_uri
        for var_uri, asset_uri in mapping.items():
            op.used(asset_uri)

        # mutate subgraph
        op.started_at_time = datetime.now()
        op.mutate(self.out_dir)
        op.ended_at_time = datetime.now()

        result = next(op.get_generated(), None)
        return result.identifier, subgraph


class ThreadPoolPlanExecutor(OperationPlanExecutor):
    """Executes an operation plan using a local ThreadPoolExecutor"""

    def __init__(
        self,
        out_dir: PathLike[str],
        max_workers: int = 1,
        max_in_flight: int = 10,
    ):
        """
        :param out_dir: The directory where new assets are written
        :param max_workers: Used when initializing the ThreadPoolExecutor
        :param max_in_flight: The max number of steps to submit to the executor before block
        """

        self.out_dir = Path(out_dir)
        self.max_workers = max_workers
        self.max_in_flight = max_in_flight

    def execute(
        self,
        plan: OperationPlan,
        seed_graph: Graph,
        initial_variables: dict[Node, Node],
    ):
        sorter = plan.get_sorter()
        sorter.prepare()

        # eagerly materialize the operations so we can validate their shape/params
        result_graph, step_to_op = materialize_operations(plan)
        result_graph += seed_graph

        # maps variable URIs to the future producing their asset URI.
        var_to_future: dict[Node, Future] = {}
        for var_uri, asset_uri in initial_variables.items():
            future: Future = Future()
            future.set_result((asset_uri, Graph()))
            var_to_future[var_uri] = future

        # ready steps not yet submitted
        pending: list[PlanStep] = []

        # in-flight steps
        future_to_step: dict[Future, PlanStep] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as thread_pool:
            while sorter.is_active():
                # get_ready() eagerly pops all ready nodes
                # we need to track them in case max_in_flight is reached so they aren't silently discarded
                pending.extend(sorter.get_ready())

                while pending and len(future_to_step) < self.max_in_flight:
                    step: PlanStep = pending.pop(0)
                    step_output = step.output_variables[0]

                    mapping = {step.identifier: step_to_op[step.identifier]}
                    subgraph = result_graph.cbd(step_to_op[step.identifier])
                    for step_input in step.input_variables:
                        if step_input.identifier not in var_to_future:
                            raise RuntimeError(
                                f"Missing input variables for step {step.identifier}"
                            )

                        asset_uri, _ = var_to_future[step_input.identifier].result()
                        mapping[step_input.identifier] = asset_uri
                        result_graph.cbd(asset_uri, target_graph=subgraph)

                        # Ensure asset has a local file
                        asset = MediaAsset(subgraph, asset_uri)
                        asset_file = Path(asset.file_path)
                        if asset_file is None or not asset_file.exists():
                            raise ValueError(
                                f"Asset {asset} does not have a local file"
                            )

                    step_executor = StepExecutor(step, self.out_dir)
                    future = thread_pool.submit(
                        step_executor.execute, subgraph, mapping
                    )

                    var_to_future[step_output.identifier] = future
                    future_to_step[future] = step

                if not future_to_step:
                    continue

                done, _ = wait(future_to_step, return_when=FIRST_COMPLETED)
                for future in done:
                    step = future_to_step.pop(future)
                    _, subgraph = future.result()
                    result_graph += subgraph
                    sorter.done(step)
                    print(f"Step {step} complete")

        return result_graph
