from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime
import mimetypes
from os import PathLike
import os
from pathlib import Path
import tempfile

from rdflib import PROV, Graph, Literal, Node

from tamper.assets import MediaAsset, load_asset_from_file
from tamper.vocabularies._TAMPER import TAMPER
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

from .operation_plan import OperationPlan, OperationPlanExecutor, PlanStep

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


class StepExecutor:
    def __init__(self, step: PlanStep, out_dir: Path):
        self.step = step
        self.out_dir = out_dir

    def execute(self, asset_uri: Node, asset_file: Path) -> tuple[Node, Graph]:
        print(f"Executing step {self.step}")
        params = self.step.operation_parameters
        op = operation_map[params.operation_type].copy_from_graph(
            params.graph, params.identifier
        )

        fd, tmp_path = tempfile.mkstemp()
        os.close(fd)

        start = datetime.now()
        op.transform(asset_file, tmp_path)
        end = datetime.now()

        # construct the subgraph
        subgraph = Graph()
        new_asset = load_asset_from_file(subgraph, tmp_path)
        suffix = mimetypes.guess_extension(new_asset.media_type)
        checksum = new_asset.checksum.split(":")[-1]
        new_asset.move_file(self.out_dir / (checksum + suffix))
        subgraph.add((op.subject, PROV.startedAtTime, Literal(start)))
        subgraph.add((op.subject, PROV.endedAtTime, Literal(end)))
        subgraph.add((op.subject, PROV.used, asset_uri))
        subgraph.add((new_asset.identifier, PROV.wasGeneratedBy, op.subject))
        subgraph += op.graph()
        return new_asset.identifier, subgraph


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

        result_graph = Graph()
        for triple in seed_graph:
            result_graph.add(triple)

        with ThreadPoolExecutor(max_workers=self.max_workers) as thread_pool:
            while sorter.is_active():
                # get_ready() eagerly pops all ready nodes
                # we need to track them in case max_in_flight is reached so they aren't silently discarded
                pending.extend(sorter.get_ready())

                while pending and len(future_to_step) < self.max_in_flight:
                    step = pending.pop(0)
                    step_input = step.input_variables[0]
                    step_output = step.output_variables[0]
                    if step_input.identifier not in var_to_future:
                        raise RuntimeError(
                            f"Missing input variables for step {step.identifier}"
                        )

                    input_asset_uri, _ = var_to_future[step_input.identifier].result()
                    asset = MediaAsset(result_graph, input_asset_uri)
                    asset_file = asset.file_path
                    if asset_file is None or not asset_file.exists():
                        raise ValueError(f"Asset {asset} does not have a local file")

                    step_executor = StepExecutor(step, self.out_dir)
                    future = thread_pool.submit(
                        step_executor.execute, input_asset_uri, asset_file
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
