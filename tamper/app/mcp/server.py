import os
import re
from contextlib import asynccontextmanager
from graphlib import CycleError
from os import PathLike
from pathlib import Path

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from rdflib import Graph, URIRef, RDF, RDFS
from rdflib.plugins.parsers.notation3 import BadSyntax

from tamper.app.kg.knowledge_graph import KnowledgeGraph
from tamper.plans import (
    validate_plan_graph,
    GraphValidationError,
)
from tamper.app.kg.local import LocalKnowledgeGraph
from tamper.assets import load_asset_from_file
from tamper.plans.async_plan_queue import AsyncPlanQueue
from tamper.plans.operation_plan import OperationPlan
from tamper.plans.thread_executor import ThreadPoolPlanExecutor
from tamper.vocabularies import (
    TAMPER,
    PLAN,
    load_prov_ontology,
    load_core_ontology,
    load_plan_ontology,
)
from tamper.utils.make_tarball import make_tarball

TAMPER_HOME_DIR = Path(os.environ["TAMPER_HOME"])
TAMPER_PLANS_DIR = TAMPER_HOME_DIR / "plans"
TAMPER_MEDIA_DIR = TAMPER_HOME_DIR / "media"


@asynccontextmanager
async def lifespan(server: FastMCP):
    if not TAMPER_HOME_DIR.exists():
        print(f"Initializing Tamper home directory at {TAMPER_HOME_DIR}")
        TAMPER_HOME_DIR.mkdir(parents=True, exist_ok=True)
    if not TAMPER_PLANS_DIR.exists():
        print(f"Initializing Tamper plans directory at {TAMPER_PLANS_DIR}")
        TAMPER_PLANS_DIR.mkdir(parents=True, exist_ok=True)
    if not TAMPER_MEDIA_DIR.exists():
        print(f"Initializing Tamper media directory at {TAMPER_MEDIA_DIR}")
        TAMPER_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    tamper_dataset_file = TAMPER_HOME_DIR / "dataset.trig"
    print(f"Using dataset file at {tamper_dataset_file}")

    kg = LocalKnowledgeGraph(tamper_dataset_file)

    executor = ThreadPoolPlanExecutor(
        TAMPER_HOME_DIR / "media", max_workers=4, max_in_flight=32
    )
    plan_queue = AsyncPlanQueue(executor)
    await plan_queue.start()

    yield {
        "kg": kg,
        "plan_queue": plan_queue,
    }


def get_kg(ctx: Context) -> KnowledgeGraph:
    # Read via ctx.lifespan_context (server._lifespan_result) rather than
    # ctx.request_context: background tasks run outside the request, so
    # request_context is None there.
    return ctx.lifespan_context["kg"]


def get_plan_queue(ctx: Context) -> AsyncPlanQueue:
    return ctx.lifespan_context["plan_queue"]


mcp = FastMCP("Tamper", lifespan=lifespan)


@mcp.tool("TrackMediaAsset")
async def track_media_asset(file_path: PathLike[str], ctx: Context) -> str:
    """
    Tracks a media asset in the knowledge graph.
    :param file_path: The file path of the media asset.
    :return: The serialized media asset graph in Turtle format.
    """
    kg = get_kg(ctx)
    g = Graph()
    load_asset_from_file(g, file_path)
    kg.insert_statements_default(g)
    kg.commit()
    return g.serialize(format="turtle")


@mcp.tool("ListPlans")
async def list_plans():
    """
    Lists the available operation plans.

    :return: A list of available operation plans.
    """

    plans = []
    for plan_file in TAMPER_PLANS_DIR.glob("*.ttl"):
        plan_graph = Graph()
        plan_graph.parse(plan_file, format="turtle")

        plan_uri = plan_graph.value(predicate=RDF.type, object=PLAN.OperationPlan)
        label = plan_graph.value(plan_uri, RDFS.label)
        comment = plan_graph.value(plan_uri, RDFS.comment)

        plans.append(
            {
                "name": plan_file.stem,
                "uri": plan_uri,
                "num_steps": len(set(plan_graph.subjects(RDF.type, PLAN.Step))),
                "label": label,
                "description": comment,
            }
        )

    return {"plans": plans}


@mcp.tool("CreatePlan")
async def create_plan(plan_graph_ttl: str, plan_name: str):
    """
    Creates an operation plan. An operation plan can be thought of as a blueprint for
        materializing branches of the knowledge graph. It takes the shape of a DAG and contains steps and variables,
        which correspond to media operations and assets. The plan is executed in topological order according to the
        shape of the graph and order of steps that can be executed. As soon as a step's input variables are ready, it
        is submitted and executed concurrently with all other ready steps.

    To see the vocabularies for tamper or the plan terms, please retrieve the `vocabulary://tamper/core` and
        `vocabulary://tamper/plan` MCP Resources.

    Example plan graph:

        ```turtle
    @prefix plan:   <https://example.org/tamper/plan#> .
    @prefix tamper: <https://example.org/tamper/core#> .
    @prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .

    <plan://example-plan> a plan:OperationPlan .

    # ---------
    # Variables (media assets)
    # ---------
    <plan://v0> a plan:Variable ;
        plan:isVariableOfPlan <plan://example-plan> ;
        rdfs:label "The original image" .

    <plan://v1> a plan:Variable ;
        plan:isVariableOfPlan <plan://example-plan> ;
        rdfs:label "The compressed image" .

    <plan://v2> a plan:Variable ;
        plan:isVariableOfPlan <plan://example-plan> ;
        rdfs:label "The noisy compressed image" .

    <plan://v3> a plan:Variable ;
        plan:isVariableOfPlan <plan://example-plan> ;
        rdfs:label "The re-compressed image" .

    # ---------
    # Steps (media operations). Each step points at a plan:OperationParameters
    # bundle that names the operation (plan:operationType) and carries its parameters.
    # ---------
    <plan://s1> a plan:Step ;
        plan:isStepOfPlan <plan://example-plan> ;
        plan:hasInputVariable <plan://v0> ;
        plan:hasOutputVariable <plan://v1> ;
        plan:operationParameters [
            a plan:OperationParameters ;
            plan:operationType tamper:CompressJPEG ;
            tamper:qualityFactor 90
        ] .

    <plan://s2> a plan:Step ;
        plan:isStepOfPlan <plan://example-plan> ;
        plan:hasInputVariable <plan://v1> ;
        plan:hasOutputVariable <plan://v2> ;
        plan:operationParameters [
            a plan:OperationParameters ;
            plan:operationType tamper:AddGaussianNoise ;
            tamper:gaussianMean 0.0 ;
            tamper:gaussianStd 1.0
        ] .

    <plan://s3> a plan:Step ;
        plan:isStepOfPlan <plan://example-plan> ;
        plan:hasInputVariable <plan://v1> ;
        plan:hasOutputVariable <plan://v3> ;
        plan:operationParameters [
            a plan:OperationParameters ;
            plan:operationType tamper:CompressJPEG ;
            tamper:qualityFactor 50
        ] .
    ```

    :param plan_graph_ttl: The operation plan graph in RDF Turtle format. The graph should follow the plan vocabulary
        (`vocabulary://tamper/plan`). In essence, every plan:Variable should correspond to a media asset, and each
        plan:Step should correspond to a media operation defined by its plan:operationParameters.
    :param plan_name: The name to be associated with the operation plan. This name may be used
        to retrieve the plan later
    """
    # Matches alphanumeric strings joined by single hyphens
    pattern = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    if not bool(re.match(pattern, plan_name)):
        raise ToolError(f"plan name is not valid (must satisfy {pattern})")

    try:
        plan_graph = Graph()
        plan_graph.parse(data=plan_graph_ttl, format="turtle")

        # Run graph validation
        validate_plan_graph(plan_graph)

        # Create plan file
        plan_file = TAMPER_PLANS_DIR / (plan_name + ".ttl")
        plan_graph.serialize(plan_file, format="turtle")
    except BadSyntax as e:
        raise ToolError(f"Graph contains syntax errors: {str(e)}") from e
    except GraphValidationError as e:
        raise ToolError(f"Graph failed shape validation: {str(e)}") from e


@mcp.tool("GetPlan")
async def get_plan(plan_name: str):
    """
    Retrieves the graph associated with the given plan name.

    :param plan_name: The name of the plan.
    :return: The graph associated with the given plan name, in RDF Turtle format.
    """
    plan_file = TAMPER_PLANS_DIR / (plan_name + ".ttl")
    if not plan_file.exists():
        raise ToolError(f"Plan with name {plan_file} does not exist")

    plan_graph_ttl = plan_file.read_text()
    return plan_graph_ttl


@mcp.tool("DeletePlan")
async def delete_plan(plan_name: str):
    """
    Deletes the graph associated with the given plan name.

    :param plan_name: The name of the plan.
    """
    plan_file = TAMPER_PLANS_DIR / (plan_name + ".ttl")
    if not plan_file.exists():
        raise ToolError(f"Plan with name {plan_file} does not exist")
    plan_file.unlink()


@mcp.tool("SubmitPlan", task=True)
async def submit_plan(plan_name: str, initial_variables: dict[str, str], ctx: Context):
    """
    Submits an operation plan for execution against the knowledge graph using the provided
    initial variables.

    This tool runs as a background task: the call returns a task ID immediately while the plan
    executes asynchronously, freeing the caller to do other work. Poll the task by its ID to
    retrieve the result graph once execution completes.

    Example initial_variables (assumes "asset://myimage" resolves to a
    valid asset in the knowledge graph): ``{ "plan://v0": "asset://myimage" }``

    :param plan_name: The name of the operation plan to execute.
    :param initial_variables: A dictionary mapping plan:Variable URIs in the operation plan to asset URIs in the
        knowledge graph. These bindings should provide only the variables not produced by some step in the plan. For
        example, if a plan compresses an image and then adds noise to the compressed image, then the bindings should
        satisfy the original image being compressed. Without appropriate bindings, those variables remain ambiguous.
    """

    kg = get_kg(ctx)
    plan_queue = get_plan_queue(ctx)

    plan_file = TAMPER_PLANS_DIR / (plan_name + ".ttl")
    if not plan_file.exists():
        raise ToolError(f"Plan with name {plan_file} does not exist")

    # parse plan graph
    plan_graph = Graph()
    plan_graph.parse(plan_file, format="turtle")
    plan_uri = plan_graph.value(predicate=RDF.type, object=PLAN.OperationPlan)
    plan = OperationPlan(plan_graph, plan_uri)

    # Create URIRefs of initial vars
    initial_variables = {URIRef(k): URIRef(v) for k, v in initial_variables.items()}

    # create a starting seed graph
    asset_uris = " ".join(uri.n3() for uri in initial_variables.values())
    result = kg.query("DESCRIBE " + asset_uris)
    seed_graph = result.graph

    try:
        result_graph = await plan_queue.put_plan(plan, seed_graph, initial_variables)
        kg.insert_statements_default(result_graph)
        kg.commit()
        return result_graph.serialize(format="turtle")
    except CycleError as e:
        raise ToolError("Plan graph cannot contain cycles") from e


@mcp.tool("QuerySPARQL")
async def query_sparql(sparql_query_str: str, ctx: Context):
    """
    Executes a (read-only) SPARQL query against the knowledge graph. The vocabulary should ALWAYS be fetched prior to
    executing any queries. Available vocabularies are exposed via MCP resources at:
    - vocabulary://tamper/core (the Tamper core ontology)
    - vocabulary://prov-o (the PROV-O ontology)

    :param sparql_query_str: The SPARQL query to execute. Must be one of the following: SELECT, ASK, CONSTRUCT, DESCRIBE.
    :return: In the case of a CONSTRUCT query, the result is the graph serialized in Turtle format. Otherwise, the result is a JSON object containing the results of the query.
    """
    kg = get_kg(ctx)
    result = kg.query(sparql_query_str)
    if result.graph:
        result.graph.bind("tamper", TAMPER)
        return result.graph.serialize(format="turtle")
    return result.serialize(format="json")


@mcp.tool("ExportDataset")
async def export_dataset(output_filename: PathLike[str], ctx: Context) -> None:
    """
    Exports the RDF dataset and all referenced media asset files to a tarball archive.
    The dataset is stored in TriG format in <archive root>/dataset.trig.
    Media assets are stored under <archive root>/assets and are renamed to <checksum>.<ext>.

    :param output_filename: The filename of the output tarball.
    """
    kg = get_kg(ctx)
    try:
        make_tarball(kg.dataset, output_filename)
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.resource("vocabulary://tamper/core")
def get_ontology() -> str:
    """
    Retrieves the Tamper Core ontology, which is the set of terms used to describe media assets and operations.
    :return: The Tamper Core ontology serialized in Turtle format.
    """
    return load_core_ontology().serialize(format="turtle")


@mcp.resource("vocabulary://prov-o")
def get_prov_ontology() -> str:
    """
    Retrieves the PROV-O ontology, which provides the set of terms used to relate media assets and operations.

    :return: The PROV-O ontology serialized in Turtle format.
    """
    return load_prov_ontology().serialize(format="turtle")


@mcp.resource("vocabulary://tamper/plan")
def get_plan_ontology() -> str:
    """
    Retrieves the Tamper Plan vocabulary, which provides a set of terms for creating blueprints of media operations.

    :return: The Tamper Plan ontology serialized in Turtle format.
    """
    return load_plan_ontology().serialize(format="turtle")


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
