import os

from ray.actor import ActorHandle
from ray.types import ObjectRef

from tamper.core import OperationPlan, PlanStep

from .operation_plan import OperationPlanExecutor
from .thread_executor import StepExecutor, materialize_operations
from rdflib import Graph, Node, URIRef
from tamper.vocabularies import TAMPER
from pathlib import Path
import ray


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

    def cbd(self, identifiers: list[Node]) -> Graph:
        subgraph = Graph()
        for identifier in identifiers:
            self.graph.cbd(identifier, target_graph=subgraph)
        return subgraph


@ray.remote
class RemoteStepExecutor(StepExecutor):
    def __init__(self, plan_graph: Graph, step_uri: URIRef, out_dir: os.PathLike[str]):
        step = PlanStep(plan_graph, step_uri)
        super().__init__(step, out_dir)

    def execute(
        self, result_graph: ActorHandle[RemoteGraph], mapping: dict[Node, Node]
    ):
        subgraph = ray.get(result_graph.cbd.remote(mapping.values()))
        result_uri, subgraph = super().execute(subgraph, mapping)
        ray.get(result_graph.add_statements.remote(subgraph))
        return result_uri


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

        result_graph, step_to_op = materialize_operations(plan)

        # actor to hold the final result graph, updated by each worker task
        result_graph = RemoteGraph.remote(result_graph)

        # maps variable URIs to asset URIs
        var_futures: dict[Node, ObjectRef[Node]] = {
            var: ray.put(val) for var, val in initial_variables.items()
        }

        # steps that have been submitted
        ref_to_step: dict[ObjectRef[Node], PlanStep] = {}

        # steps that are ready but can't be submitted because max_in_flight is reached
        pending: list[PlanStep] = []

        sorter = plan.get_sorter()
        sorter.prepare()

        # start workers
        while sorter.is_active():
            # get_ready() eagerly pops all ready nodes
            # we need to track them in case max_in_flight is reached so they aren't silently discarded
            pending.extend(sorter.get_ready())

            while pending and len(ref_to_step) < self.max_in_flight:
                step: PlanStep = pending.pop(0)
                step_output = step.output_variables[0]

                mapping = {step.identifier: step_to_op[step.identifier]}
                for step_input in step.input_variables:
                    if step_input.identifier not in var_futures:
                        raise RuntimeError(
                            f"Missing input variables for step {step.identifier}"
                        )
                    asset_uri = ray.get(var_futures[step_input.identifier])
                    mapping[step_input.identifier] = asset_uri

                step_actor = RemoteStepExecutor.remote(
                    plan_graph_ref, step.identifier, self.out_dir
                )
                print(f"Executing step {step.identifier.n3()}")
                ref = step_actor.execute.remote(result_graph, mapping)
                var_futures[step_output.identifier] = ref
                ref_to_step[ref] = step

            # wait for at least one to complete, then mark done to unlock dependents
            done_refs, _ = ray.wait(list(ref_to_step), num_returns=1)
            for ref in done_refs:
                step = ref_to_step.pop(ref)
                sorter.done(step)
                print(f"Step {step.identifier.n3()} competed")

        ray.get(list(var_futures.values()))

        final_result_graph = ray.get(result_graph.get_graph.remote())
        return final_result_graph
