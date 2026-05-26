from graphlib import TopologicalSorter
from pathlib import Path

import ray
from ray.actor import ActorHandle
from ray.types import ObjectRef
from rdflib import Graph, Node, RDF

from tamper.namespaces import P_PLAN, TAMPER
from tamper.ops.image import CompressImage, AddGaussianNoise

operation_map = {
    TAMPER.CompressImage: CompressImage,
    TAMPER.AddGaussianNoise: AddGaussianNoise,
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
    op_type = plan_graph.value(subject=step_uri, predicate=TAMPER.operationType)
    if op_type is None:
        raise ValueError("No operation type found")
    if op_type not in operation_map:
        raise ValueError(f"Unsupported operation type: {op_type}")

    # prep operation
    op = operation_map[op_type].from_rdf(plan_graph, step_uri)

    asset_file = ray.get(result_graph.get_asset_file_path.remote(mapped_uri))
    if asset_file is None:
        raise ValueError(f"Asset {mapped_uri} does not have a local file path")

    # apply operation
    new_asset_uri, subgraph = op.apply(asset_file, mapped_uri, out_dir)

    # update remote graph
    ray.get(result_graph.add_statements.remote(subgraph))
    return new_asset_uri


class PermutationPlanExecutor:
    def __init__(self, plan_graph: Graph, result_graph: Graph):
        self.plan_graph = plan_graph
        self.result_graph = RemoteGraph.remote(result_graph)

    def _get_step_dependencies(self, step_uri: Node) -> set[Node]:
        deps = set()
        input_vars = list(self.plan_graph.objects(step_uri, P_PLAN.hasInputVariable))
        for input_var in input_vars:
            input_producer = self.plan_graph.value(predicate=P_PLAN.hasOutputVariable, object=input_var)
            if input_producer:
                deps.add(input_producer)
        return deps

    def execute(self, out_dir: Path, initial_variables: dict[Node, Node], max_in_flight: int = 32) -> Graph:
        # make immutable copy of plan_graph shared by all workers
        plan_graph_ref = ray.put(self.plan_graph)

        step_topology = {
            step_uri: self._get_step_dependencies(step_uri)
            for step_uri in self.plan_graph.subjects(RDF.type, P_PLAN.Step)
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
                input_var_uri = next(self.plan_graph.objects(step_uri, P_PLAN.hasInputVariable))
                output_var_uri = next(self.plan_graph.objects(step_uri, P_PLAN.hasOutputVariable))

                if input_var_uri not in var_futures:
                    raise RuntimeError(f"Missing input variables for step {step_uri}")

                print(f"Executing step {step_uri.n3()}")
                ref = execute_step.remote(plan_graph_ref, step_uri, self.result_graph, out_dir,
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

        final_result_graph = ray.get(self.result_graph.get_graph.remote())
        return final_result_graph
