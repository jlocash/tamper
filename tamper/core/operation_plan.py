from graphlib import TopologicalSorter

from rdflib import URIRef

from tamper.vocabularies import PLAN

from ._common import Resource, MappedProperty


class PlanVariable(Resource):
    __rdf_type__ = PLAN.Variable

    @property
    def producer(self) -> PlanStep | None:
        step_uri = self.graph.value(
            predicate=PLAN.hasOutputVariable, object=self.identifier
        )
        if step_uri is not None:
            return PlanStep(self.graph, step_uri)


class OperationParameters(Resource):
    __rdf_type__ = PLAN.OperationParameters

    operation_type: MappedProperty[URIRef] = MappedProperty(PLAN.operationType)


class PlanStep(Resource):
    __rdf_type__ = PLAN.Step

    operation_type: MappedProperty[URIRef] = MappedProperty(PLAN.operationType)

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

    @property
    def parameters(self) -> Resource:
        return self.value(PLAN.parameters)


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
