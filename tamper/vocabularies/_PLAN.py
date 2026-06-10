from rdflib.namespace import DefinedNamespace, Namespace
from rdflib.term import URIRef


class PLAN(DefinedNamespace):
    """
    DESCRIPTION_EDIT_ME_!

    Generated from: SOURCE_RDF_FILE_EDIT_ME_!
    Date: 2026-06-10 04:32:41.536265
    """

    _NS = Namespace("https://example.org/tamper/plan#")

    OperationParameters: (
        URIRef  # A bundle carrying the parameters associated with the operation.
    )
    OperationPlan: URIRef  # A blueprint of operations that derives new media assets, materializing branches of the knowledge graph.
    Step: URIRef  # A single node in a plan. Purely structural: it wires inputs to an         output and points at the operation to run via plan:parameters.
    Variable: URIRef  # A placeholder for a media asset within a plan. Like p-plan:Variable         it is NOT the asset itself, rather it is bound to an asset at execution time.
    VariableUsage: URIRef  # The use of a variable by a step in a specific role. Reified so that         input variables may be qualified/contextualized.
    hasInputVariable: URIRef  # Relates a step to a variable it consumes. This is the unqualified         dependency edge used for topological ordering. For multi-input operations it is         recommended to use plan:qualifiedInput, so a step need only assert qualified inputs.
    hasOutputVariable: URIRef  # Relates a step to the variable it produces. A variable has exactly one         producer and an operation has one primary output.
    isStepOfPlan: URIRef  # Relates a step to its associated plan
    isVariableOfPlan: URIRef  # Relates a variable to its associated plan
    operationType: URIRef  # The operation to run, as a value pointing at a tamper:Operation         subclass (OWL punning: the class is used as an individual here). Modelled as an         object property, NOT rdf:type, so naming the operation does not retype the         parameter bundle and trip the disjointness between operations.
    parameters: URIRef  # Binds a step to the operation (and parameters) it executes.
    qualifiedInput: (
        URIRef  # Relates a step to a role-bearing use of one of its input variables.
    )
    variable: URIRef  # The variable consumed by a usage.
