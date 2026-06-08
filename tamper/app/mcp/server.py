from datetime import datetime
import os
from contextlib import asynccontextmanager
from graphlib import CycleError
from os import PathLike
from pathlib import Path
import re

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from rdflib import DCAT, DCTERMS, PROV, Graph, URIRef, RDF, RDFS
from rdflib.plugins.parsers.notation3 import BadSyntax

from tamper.app.kg.knowledge_graph import GraphNotFoundError, KnowledgeGraph
from tamper.dataset import Catalog, Dataset as TamperDataset
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

CATALOG_URI = URIRef("tamper://catalog")


def serialize_ttl(g: Graph):
    """
    Serializes the given graph in Turtle format with bindings
    for the common Tamper namespaces
    """
    g.bind("tamper", TAMPER)
    g.bind("plan", PLAN)
    g.bind("prov", PROV)
    g.bind("dcterms", DCTERMS)
    g.bind("dcat", DCAT)
    return g.serialize(format="turtle")


def test_slug(slug: str):
    # Matches alphanumeric strings joined by single hyphens
    pattern = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    if not bool(re.match(pattern, slug)):
        raise ValueError(f"plan name is not valid (must satisfy {pattern})")


def init_catalog(kg: KnowledgeGraph):
    cat = Catalog.new(Graph(), CATALOG_URI)
    cat.title = "Tamper dataset catalog"
    cat.description = "A simple catalog of the datasets available to Tamper"
    cat.created = datetime.now()
    with kg.commit_or_rollback():
        kg.insert_statements_default(cat.graph)


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

    tamper_catalog_file = TAMPER_HOME_DIR / "catalog.trig"
    print(f"Using catalog file at {tamper_catalog_file}")
    kg = LocalKnowledgeGraph(tamper_catalog_file)

    if not tamper_catalog_file.exists():
        print("Initializing Tamper catalog")
        init_catalog(kg)

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
    """Helper to retrieve the active knowledge graph object from the FastMCP context"""
    return ctx.lifespan_context["kg"]


def get_plan_queue(ctx: Context) -> AsyncPlanQueue:
    """Helper to retrieve the active operation plan queue from the FastMCP context"""
    return ctx.lifespan_context["plan_queue"]


mcp = FastMCP("Tamper", lifespan=lifespan)


@mcp.tool("InspectCatalog")
async def inspect_catalog(ctx: Context) -> str:
    """
    Returns the catalog graph, detailing the available datasets

    :return: An RDF graph of the dataset catalog, serialized in Turtle format
    """
    kg = get_kg(ctx)
    default_graph = kg.get_default_graph()
    return serialize_ttl(default_graph)


@mcp.tool("CreateDataset")
async def create_dataset(slug: str, title: str, description: str, ctx: Context) -> str:
    """
    Creates a new dataset

    :param slug: The valid URI slug used to mint a new URI for the dataset
    :param title: A human-readable display name for the dataset
    :param description: A human-readable description of the dataset

    :return: An RDF description of the new dataset, in Turtle format
    """
    try:
        test_slug(slug)
    except ValueError as e:
        raise ToolError(str(e)) from e

    ds_uri = URIRef(f"dataset://{slug}")
    kg = get_kg(ctx)
    if kg.any((ds_uri, None, None, None)):
        raise ToolError(f"Identifier {ds_uri} already in use")

    subgraph = Graph()

    dataset = TamperDataset.new(subgraph, ds_uri)
    dataset.title = title
    dataset.description = description
    dataset.created = datetime.now()

    catalog = Catalog(subgraph, CATALOG_URI)
    catalog.add_dataset(dataset.identifier)
    with kg.commit_or_rollback():
        kg.insert_statements_default(subgraph)

    return serialize_ttl(subgraph)


@mcp.tool("DescribeDataset")
async def describe_dataset(identifier: str, ctx: Context) -> str:
    """
    Retrieves the top-level information about the dataset, excluding its contents.

    :param identifier: The identifier of the dataset to retrieve
    :returns: An RDF description of the dataset, serialized in Turtle format
    """
    identifier = URIRef(identifier)
    kg = get_kg(ctx)
    description = kg.describe(identifier)

    if len(description) == 0 or (identifier, RDF.type, DCAT.Dataset) not in description:
        raise ToolError(f"Dataset {identifier} not found")

    return serialize_ttl(description)


@mcp.tool("GetDatasetGraph")
async def get_dataset_graph(identifier: str, ctx: Context) -> str:
    """
    Returns a graph containing the contents of the dataset.
    NOTE: These graphs can get quite large, so prefer querying the dataset's graph
        instead of fetching it in its entirety whenever possible

    :param identifier: The identifier of the dataset to retrieve the contents of
    :return: A graph containing the contents of the dataset, serialized in Turtle format
    :raises ToolError: When the dataset is empty, i.e when no media assets or
        operations have been added to it
    """
    identifier = URIRef(identifier)
    kg = get_kg(ctx)
    if not kg.any((identifier, RDF.type, DCAT.Dataset)):
        raise ToolError(f"Identifier {identifier} is not associated a dataset")

    try:
        dataset_graph = kg.get_named_graph(identifier)
    except GraphNotFoundError as e:
        raise ToolError(f"Dataset {identifier} is empty") from e

    return serialize_ttl(dataset_graph)


@mcp.tool("LoadMediaAsset")
async def load_media_asset(
    dataset_uri: str, file_path: PathLike[str], ctx: Context
) -> str:
    """
    Loads a media asset into the knowledge graph.

    :param dataset_uri: The identifier of the dataset to load the media asset into
    :param file_path: The file path of the media asset.
    :return: The serialized media asset graph in Turtle format.
    """
    dataset_uri = URIRef(dataset_uri)
    kg = get_kg(ctx)
    if not kg.any((dataset_uri, RDF.type, DCAT.Dataset)):
        raise ToolError(f"Identifier {dataset_uri} is not associated a dataset")

    kg = get_kg(ctx)
    subgraph = Graph()
    load_asset_from_file(subgraph, file_path)

    with kg.commit_or_rollback():
        kg.insert_statements(dataset_uri, subgraph)

        # update dataset modified time
        ds = TamperDataset(Graph(), dataset_uri)
        ds.modified = datetime.now()

        kg.insert_statements_default(ds.graph)

    return serialize_ttl(subgraph)


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
    try:
        test_slug(plan_name)
    except ValueError as e:
        raise ToolError(str(e)) from e

    try:
        plan_graph = Graph()
        plan_graph.parse(data=plan_graph_ttl, format="turtle")

        # Run graph validation
        validate_plan_graph(plan_graph)

        # Create plan file
        plan_file = TAMPER_PLANS_DIR / (plan_name + ".ttl")
        plan_graph_ttl = serialize_ttl(plan_graph)
        plan_file.write_text(plan_graph)
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
async def submit_plan(
    dataset_uri: str,
    plan_name: str,
    initial_variables: dict[str, str],
    ctx: Context,
):
    """
    Submits an operation plan for execution against the knowledge graph using the provided
    initial variables.

    This tool runs as a background task: the call returns a task ID immediately while the plan
    executes asynchronously, freeing the caller to do other work. Poll the task by its ID to
    retrieve the result graph once execution completes.

    Example initial_variables (assumes "asset://myimage" resolves to a
    valid asset in the knowledge graph): ``{ "plan://v0": "asset://myimage" }``

    :param dataset_uri: The identifier of the dataset to execute the plan on
    :param plan_name: The name of the operation plan to execute.
    :param initial_variables: A dictionary mapping plan:Variable URIs in the operation plan to asset URIs in the
        knowledge graph. These bindings should provide only the variables not produced by some step in the plan. For
        example, if a plan compresses an image and then adds noise to the compressed image, then the bindings should
        satisfy the original image being compressed. Without appropriate bindings, those variables remain ambiguous.
    """
    kg = get_kg(ctx)
    plan_queue = get_plan_queue(ctx)

    dataset_uri = URIRef(dataset_uri)
    dataset = TamperDataset(kg.describe(dataset_uri), dataset_uri)
    if len(dataset.graph) == 0:
        raise ToolError(f"Datasest {dataset_uri} does not exist")

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
    result = kg.query_named(dataset.identifier, f"DESCRIBE {asset_uris}")
    seed_graph = result.graph

    try:
        with kg.commit_or_rollback():
            result_graph = await plan_queue.put_plan(
                plan, seed_graph, initial_variables
            )
            kg.insert_statements(dataset.identifier, result_graph)
            dataset.modified = datetime.now()
            kg.insert_statements_default(dataset.graph)
        return serialize_ttl(result_graph)
    except CycleError as e:
        raise ToolError("Plan graph cannot contain cycles") from e


@mcp.tool("QuerySPARQL")
async def query_sparql(
    sparql_query_str: str, dataset_uris: list[str], default_graph: bool, ctx: Context
):
    """
    Executes a (read-only) SPARQL query against the knowledge graph. The vocabulary should ALWAYS be fetched prior to
    executing any queries. Available vocabularies are exposed via MCP resources at:
    - vocabulary://tamper/core (the Tamper core ontology)
    - vocabulary://prov-o (the PROV-O ontology)

    The query behavior can be modified by configuring ``dataset_uris`` and ``default_graph`` parameters.
    These parameters control which graphs form the union the query will be run on.

    :param sparql_query_str: The SPARQL query to execute. Must be one of the following: SELECT, ASK, CONSTRUCT, DESCRIBE.
    :param dataset_uris: A list of URIs of datasets to include in the queried union
    :param default_graph: If set to true, will include the default graph in the queried union
    :return: In the case of a CONSTRUCT query, the result is the graph serialized in Turtle format. Otherwise, the result is a JSON object containing the results of the query.
    """
    kg = get_kg(ctx)
    dataset_uris = list(map(URIRef, dataset_uris))
    result = kg.query(sparql_query_str, default_graph, dataset_uris)
    if result.graph:
        result.graph.bind("tamper", TAMPER)
        return serialize_ttl(result.graph)
    return result.serialize(format="json")


@mcp.tool("ExportCatalog", task=True)
async def export_catalog(output_filename: PathLike[str], ctx: Context) -> None:
    """
    Exports the entire Tamper catalog, with all datasets and all referenced media asset files
    to a tarball archive. The dataset is stored in TriG format in <archive root>/catalog.trig.
    Media assets are stored under <archive root>/assets and are renamed to <checksum>.<ext>.

    :param dataset_uri: the identifier of the dataset to export.
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
    return serialize_ttl(load_core_ontology())


@mcp.resource("vocabulary://prov-o")
def get_prov_ontology() -> str:
    """
    Retrieves the PROV-O ontology, which provides the set of terms used to relate media assets and operations.

    :return: The PROV-O ontology serialized in Turtle format.
    """
    return serialize_ttl(load_prov_ontology())


@mcp.resource("vocabulary://tamper/plan")
def get_plan_ontology() -> str:
    """
    Retrieves the Tamper Plan vocabulary, which provides a set of terms for creating blueprints of media operations.

    :return: The Tamper Plan ontology serialized in Turtle format.
    """
    return serialize_ttl(load_plan_ontology())


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
