import abc
from graphlib import TopologicalSorter
from rdflib.resource import Resource
from tamper.vocabularies import PLAN
from rdflib import Graph, Node


class PlanVariable(Resource):
    @property
    def producer(self) -> PlanStep | None:
        step_uri = self.graph.value(
            predicate=PLAN.hasOutputVariable, object=self.identifier
        )
        if step_uri is not None:
            return PlanStep(self.graph, step_uri)


class PlanStep(Resource):
    @property
    def input_variables(self) -> list[PlanVariable]:
        return list(
            map(
                lambda resource: PlanVariable(self.graph, resource.identifier),
                self.objects(PLAN.hasInputVariable),
            )
        )

    @property
    def output_variables(self):
        return list(
            map(
                lambda resource: PlanVariable(self.graph, resource.identifier),
                self.objects(PLAN.hasOutputVariable),
            )
        )


class OperationPlan(Resource):
    @property
    def steps(self) -> list[PlanStep]:
        return list(
            map(
                lambda resource: PlanStep(self.graph, resource.identifier),
                self.subjects(PLAN.isStepOfPlan),
            )
        )

    @property
    def variables(self) -> list[PlanVariable]:
        return list(
            map(
                lambda var_uri: PlanVariable(self.graph, var_uri),
                self.graph.subjects(PLAN.isVariableOfPlan, self.identifier),
            )
        )

    @property
    def topology(self):
        step_topology = {}
        for step in self.steps:
            step_topology[step] = {
                var.producer for var in step.input_variables if var.producer is not None
            }
        return step_topology

    def get_sorter(self) -> TopologicalSorter:
        return TopologicalSorter(self.topology)


class OperationPlanExecutor(abc.ABC):
    @abc.abstractmethod
    def execute(
        self,
        plan: OperationPlan,
        seed_graph: Graph,
        initial_variables: dict[Node, Node],
    ):
        pass
