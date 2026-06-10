import abc
from rdflib import Graph, Node
from tamper.core.operation_plan import OperationPlan


class OperationPlanExecutor(abc.ABC):
    @abc.abstractmethod
    def execute(
        self,
        plan: OperationPlan,
        seed_graph: Graph,
        initial_variables: dict[Node, Node],
    ):
        """
        Executes the given operation plan and returns the materialized subgraph

        :param plan: The OperationPlan to execute
        :param seed_graph: A starting graph used to initiate plan execution
        :initial_variables: A dictionary mapping variable URIs in the plan graph to asset URIs in the seed graph

        :returns: A Graph representing the subgraph of materialized operations
        """

        pass
