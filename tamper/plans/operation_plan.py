import mimetypes
import os
import shutil
import tempfile
from datetime import datetime
from graphlib import TopologicalSorter
from os import PathLike
from pathlib import Path

import ray

from magic import Magic
from ray.actor import ActorHandle
from ray.types import ObjectRef
from rdflib import Graph, Node, RDF, PROV, Literal

from tamper.assets import build_asset_from_file, get_file_sha256
from tamper.ops.audio import ResampleAudio, TranscodeAudio
from tamper.ops.video import TranscodeVideo
from tamper.ops.image import CompressJPEG, AddGaussianNoise, Resize, MedianFilter, GaussianBlur, CropImage, CompressWebP
from tamper.vocabularies import PLAN, TAMPER

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
def execute_step(plan_graph: Graph, step_uri: Node, result_graph: ActorHandle[RemoteGraph],
                 out_dir: Path, mapped_uri: Node) -> Node:
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
    checksum = get_file_sha256(tmp_path)
    mimetype = Magic(mime=True).from_file(tmp_path)
    suffix = mimetypes.guess_extension(mimetype)
    new_asset_file = out_dir / (checksum + suffix)
    shutil.move(tmp_path, new_asset_file)

    # construct the subgraph
    subgraph = op.graph()
    new_asset_uri = build_asset_from_file(subgraph, new_asset_file)
    subgraph.add((op.subject, PROV.startedAtTime, Literal(start)))
    subgraph.add((op.subject, PROV.endedAtTime, Literal(end)))
    subgraph.add((op.subject, PROV.used, mapped_uri))
    subgraph.add((new_asset_uri, PROV.wasGeneratedBy, op.subject))

    # update remote graph
    ray.get(result_graph.add_statements.remote(subgraph))
    return new_asset_uri


class OperationPlanExecutor:
    def __init__(self, out_dir: PathLike[str], max_in_flight: int = 32):
        self.out_dir = Path(out_dir)
        self.max_in_flight = max_in_flight

    def _get_step_dependencies(self, plan_graph: Graph, step_uri: Node) -> set[Node]:
        deps = set()
        input_vars = list(plan_graph.objects(step_uri, PLAN.hasInputVariable))
        for input_var in input_vars:
            input_producer = plan_graph.value(predicate=PLAN.hasOutputVariable, object=input_var)
            if input_producer:
                deps.add(input_producer)
        return deps

    def execute(self, plan_graph: Graph, seed_graph: Graph, initial_variables: dict[Node, Node],
                max_in_flight: int = 32) -> Graph:
        # make immutable copy of plan_graph shared by all workers
        plan_graph_ref = ray.put(plan_graph)

        # actor to hold the final result graph, updated by each worker task
        result_graph = RemoteGraph.remote(seed_graph)

        # map steps to their immediate precursors
        step_topology = {
            step_uri: self._get_step_dependencies(plan_graph, step_uri)
            for step_uri in plan_graph.subjects(RDF.type, PLAN.Step)
        }

        # maps variable URIs to asset URIs
        var_futures: dict[Node, ObjectRef[Node]] = {var: ray.put(val) for var, val in initial_variables.items()}

        # steps that have been submitted
        ref_to_step: dict[ObjectRef[Node], Node] = {}

        # steps that are ready but can't be submitted because max_in_flight is reached
        pending: list[Node] = []

        # sort steps based on dependency order
        sorter = TopologicalSorter(step_topology)
        sorter.prepare()

        # start workers
        while sorter.is_active():
            # get_ready() eagerly pops all ready nodes
            # we need to track them in case max_in_flight is reached so they aren't silently discarded
            pending.extend(sorter.get_ready())

            while pending and len(ref_to_step) < max_in_flight:
                step_uri = pending.pop(0)
                input_var_uri = next(plan_graph.objects(step_uri, PLAN.hasInputVariable))
                output_var_uri = next(plan_graph.objects(step_uri, PLAN.hasOutputVariable))

                if input_var_uri not in var_futures:
                    raise RuntimeError(f"Missing input variables for step {step_uri}")

                print(f"Executing step {step_uri.n3()}")
                ref = execute_step.remote(plan_graph_ref, step_uri, result_graph, self.out_dir,
                                          var_futures[input_var_uri])

                var_futures[output_var_uri] = ref
                ref_to_step[ref] = step_uri

            # wait for at least one to complete, then mark done to unlock dependents
            done_refs, _ = ray.wait(list(ref_to_step), num_returns=1)
            for ref in done_refs:
                step_uri = ref_to_step.pop(ref)
                sorter.done(step_uri)
                print(f"Step {step_uri.n3()} competed")

        ray.get(list(var_futures.values()))

        final_result_graph = ray.get(result_graph.get_graph.remote())
        return final_result_graph
