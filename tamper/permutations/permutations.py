import logging
from graphlib import TopologicalSorter
from pathlib import Path

import ray
from ray.actor import ActorHandle
from ray.types import ObjectRef
from rdflib import Graph, Node, RDF

from tamper.namespaces import P_PLAN, TAMPER
from tamper.ops.image import CompressImage, AddGaussianNoise

logger = logging.getLogger(__name__)

operation_map = {
    TAMPER.CompressImage: CompressImage,
    TAMPER.AddGaussianNoise: AddGaussianNoise,
}


@ray.remote
class RemoteGraph:
    def __init__(self, graph: Graph):
        print("Initializing RemoteGraph with graph:")
        graph.print()
        self.graph = graph

    def add_statements(self, statements: Graph):
        self.graph += statements

    def get_graph(self) -> Graph:
        return self.graph


@ray.remote
class RemoteStepExecutor:
    def __init__(self, plan_graph: Graph, step_uri: Node,
                 result_graph: ActorHandle[RemoteGraph]):
        self.plan_graph = plan_graph
        self.step_uri = step_uri
        self.result_graph = result_graph
        self.op = self._get_operation()

    def _get_operation(self):
        op_type = self.plan_graph.value(subject=self.step_uri, predicate=TAMPER.operationType)
        if op_type is None:
            raise ValueError("No operation type found")
        if op_type not in operation_map:
            raise ValueError(f"Unsupported operation type: {op_type}")
        return operation_map[op_type].from_rdf(self.plan_graph, self.step_uri)

    def execute(self, out_dir: Path, input_var_uri: Node, mapped_uri: Node) -> Node:
        """
        Executes the media operation and returns the resulting asset URI.
        NOTE: Currently, this method is a stub and will simply copy the plan's step and variable URIs to the result graph.
        """
        print(f"executing step {self.step_uri}")
        asset_graph = ray.get(self.result_graph.get_graph.remote())
        asset_graph.print()

        new_asset_uri, subgraph = self.op.apply(asset_graph, mapped_uri, out_dir)

        ray.get(self.result_graph.add_statements.remote(subgraph))
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

    def execute(self, out_dir: Path, initial_variables: dict[Node, Node]) -> Graph:
        # make immutable copy of plan_graph shared by all workers
        plan_graph_ref = ray.put(self.plan_graph)

        # a map of each step to the set of precursor steps
        step_topology = {}

        # map each step to an executor
        step_uris = list(self.plan_graph.subjects(RDF.type, P_PLAN.Step))
        step_actors = {}

        for step_uri in step_uris:
            step_actors[step_uri] = RemoteStepExecutor.remote(plan_graph_ref, step_uri, self.result_graph)
            step_topology[step_uri] = self._get_step_dependencies(step_uri)

        # Futures maps all variables in the plan to their corresponding Ray ObjectRef
        # As executors finish, the refs will resolve to the resulting asset URIs
        futures: dict[Node, ObjectRef[Node]] = {var: ray.put(val) for var, val in initial_variables.items()}

        sorter = TopologicalSorter(step_topology)
        step_order = list(sorter.static_order())
        logger.info(f"[Driver] Submitting DAG with steps: {step_order}")

        for step_uri in step_order:
            # input_var_uris = list(self.plan_graph.objects(step_uri, P_PLAN.hasInputVariable))
            input_var_uri = next(self.plan_graph.objects(step_uri, P_PLAN.hasInputVariable))
            output_var_uri = next(self.plan_graph.objects(step_uri, P_PLAN.hasOutputVariable))

            # if not all(var in futures for var in input_var_uris):
            if not input_var_uri in futures:
                raise RuntimeError(f"Missing input variables for step {step_uri}")

            # input_mapping = {var: futures[var] for var in input_var_uris}
            # ref_uri = step_actors[step_uri].execute.remote(out_dir, input_mapping.keys(), list(input_mapping.values()))
            ref_uri = step_actors[step_uri].execute.remote(out_dir, input_var_uri, futures[input_var_uri])
            futures[output_var_uri] = ref_uri

        logger.info("[Driver] DAG submitted. Waiting for completion...")
        ray.get(list(futures.values()))

        final_result_graph = ray.get(self.result_graph.get_graph.remote())
        return final_result_graph
