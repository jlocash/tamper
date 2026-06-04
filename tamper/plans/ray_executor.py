from datetime import datetime
import mimetypes
import os
import tempfile

from ray.actor import ActorHandle
from ray.types import ObjectRef

from tamper.assets import load_asset_from_file
from tamper.ops.audio import ResampleAudio, TranscodeAudio
from tamper.ops.image import (
    CompressJPEG,
    CompressWebP,
    AddGaussianNoise,
    Resize,
    MedianFilter,
    GaussianBlur,
    CropImage,
)
from tamper.ops.video import TranscodeVideo

from .operation_plan import OperationPlanExecutor, OperationPlan, PlanStep
from rdflib import PROV, Graph, Literal, Node
from tamper.vocabularies import TAMPER, PLAN
from pathlib import Path
import ray

operation_map = {
    TAMPER.CompressJPEG: CompressJPEG,
    TAMPER.CompressWebP: CompressWebP,
    TAMPER.TranscodeVideo: TranscodeVideo,
    TAMPER.AddGaussianNoise: AddGaussianNoise,
    TAMPER.Resize: Resize,
    TAMPER.MedianFilter: MedianFilter,
    TAMPER.GaussianBlur: GaussianBlur,
    TAMPER.ResampleAudio: ResampleAudio,
    TAMPER.TranscodeAudio: TranscodeAudio,
    TAMPER.CropImage: CropImage,
}


@ray.remote
class RemoteGraph:
    def __init__(self, graph: Graph):
        self.graph = graph

    def add_statements(self, statements: Graph):
        self.graph += statements

    def get_asset_file_path(self, asset_uri: Node) -> Path | None:
        file_path = self.graph.value(asset_uri, TAMPER.filePath)
        if file_path is None:
            return None
        return Path(str(file_path))

    def get_graph(self) -> Graph:
        return self.graph


@ray.remote
def execute_step(
    plan_graph: Graph,
    step_uri: Node,
    result_graph: ActorHandle[RemoteGraph],
    out_dir: Path,
    mapped_uri: Node,
) -> Node:
    params_uri = plan_graph.value(step_uri, PLAN.operationParameters)
    if params_uri is None:
        raise ValueError("No operation parameters found")
    op_type = plan_graph.value(params_uri, predicate=PLAN.operationType)
    if op_type is None:
        raise ValueError("No operation type found")
    if op_type not in operation_map:
        raise ValueError(f"Unsupported operation type: {op_type}")

    # prep operation
    op = operation_map[op_type].copy_from_graph(plan_graph, params_uri)

    asset_file = ray.get(result_graph.get_asset_file_path.remote(mapped_uri))
    if asset_file is None:
        raise ValueError(f"Asset {mapped_uri} does not have a local file path")

    fd, tmp_path = tempfile.mkstemp()
    os.close(fd)

    start = datetime.now()
    op.transform(asset_file, tmp_path)
    end = datetime.now()

    # move asset to final location
    subgraph = Graph()
    new_asset = load_asset_from_file(subgraph, tmp_path)
    suffix = mimetypes.guess_extension(new_asset.media_type)
    checksum = new_asset.checksum.split(":")[-1]
    new_asset.move_file(out_dir / (checksum + suffix))

    # construct the subgraph
    subgraph.add((op.subject, PROV.startedAtTime, Literal(start)))
    subgraph.add((op.subject, PROV.endedAtTime, Literal(end)))
    subgraph.add((op.subject, PROV.used, mapped_uri))
    subgraph.add((new_asset.subject, PROV.wasGeneratedBy, op.subject))

    # update remote graph
    ray.get(result_graph.add_statements.remote(subgraph))
    return new_asset.subject


class RayExecutor(OperationPlanExecutor):
    def __init__(self, out_dir: os.PathLike[str], max_in_flight: int = 32):
        self.out_dir = Path(out_dir)
        self.max_in_flight = max_in_flight

    def execute(
        self,
        plan: OperationPlan,
        seed_graph: Graph,
        initial_variables: dict[Node, Node],
    ) -> Graph:
        # make immutable copy of plan_graph shared by all workers
        plan_graph_ref = ray.put(plan.graph)

        # actor to hold the final result graph, updated by each worker task
        result_graph = RemoteGraph.remote(seed_graph)

        # maps variable URIs to asset URIs
        var_futures: dict[Node, ObjectRef[Node]] = {
            var: ray.put(val) for var, val in initial_variables.items()
        }

        # steps that have been submitted
        ref_to_step: dict[ObjectRef[Node], Node] = {}

        # steps that are ready but can't be submitted because max_in_flight is reached
        pending: list[Node] = []

        sorter = plan.get_sorter()
        sorter.prepare()

        # start workers
        while sorter.is_active():
            # get_ready() eagerly pops all ready nodes
            # we need to track them in case max_in_flight is reached so they aren't silently discarded
            pending.extend(sorter.get_ready())

            while pending and len(ref_to_step) < self.max_in_flight:
                step: PlanStep = pending.pop(0)
                step_input = step.input_variables[0]
                step_output = step.output_variables[0]
                if step_input.identifier not in var_futures:
                    raise RuntimeError(
                        f"Missing input variables for step {step.identifier}"
                    )

                print(f"Executing step {step.identifier.n3()}")
                ref = execute_step.remote(
                    plan_graph_ref,
                    step.identifier,
                    result_graph,
                    self.out_dir,
                    var_futures[step_input.identifier],
                )

                var_futures[step_output.identifier] = ref
                ref_to_step[ref] = step

            # wait for at least one to complete, then mark done to unlock dependents
            done_refs, _ = ray.wait(list(ref_to_step), num_returns=1)
            for ref in done_refs:
                step_uri = ref_to_step.pop(ref)
                sorter.done(step_uri)
                print(f"Step {step.identifier.n3()} competed")

        ray.get(list(var_futures.values()))

        final_result_graph = ray.get(result_graph.get_graph.remote())
        return final_result_graph
