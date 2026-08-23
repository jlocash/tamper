from datetime import datetime

from rdflib import DCTERMS, PROV, RDF, URIRef

from tamper.app.api.schemas import CreateDataset
from tamper.app.kg import KnowledgeGraph
from tamper.app.services.errors import ResourceAlreadyExistsError
from tamper.core import Dataset
from tamper.vocabularies import TAMPER


class DatasetNotFoundError(Exception):
    def __init__(self, dataset_uri: URIRef):
        super().__init__(f"Dataset {dataset_uri.n3()} not found")


def dataset_exists(kg: KnowledgeGraph, dataset_uri: URIRef) -> bool:
    result = kg.query(f"ASK {{ {dataset_uri.n3()} a {TAMPER.Dataset.n3()} }}")
    return result.askAnswer


def _get_dataset_query(dataset_uri: URIRef | None):
    dataset_var = "?dataset"
    if dataset_uri:
        dataset_var = dataset_uri.n3()
    return f"""
    CONSTRUCT {{
        {dataset_var} a {TAMPER.Dataset.n3()} ;
            {DCTERMS.title.n3()} ?title ;
            {DCTERMS.description.n3()} ?desc ;
            {DCTERMS.created.n3()} ?created ;
            {DCTERMS.modified.n3()} ?modified ;
            {DCTERMS.creator.n3()} ?creator ;
            {DCTERMS.publisher.n3()} ?publisher ;
            {DCTERMS.license.n3()} ?license ;
            {DCTERMS.rights.n3()} ?rights ;
            {DCTERMS.language.n3()} ?language ;
            {PROV.hadMember.n3()} ?member .
    }}
    WHERE {{
        {dataset_var} a {TAMPER.Dataset.n3()} ;
            {DCTERMS.title.n3()} ?title ;
            {DCTERMS.description.n3()} ?desc ;
            {DCTERMS.created.n3()} ?created .

        OPTIONAL {{ {dataset_var} {DCTERMS.modified.n3()} ?modified . }}
        OPTIONAL {{ {dataset_var} {DCTERMS.creator.n3()} ?creator . }}
        OPTIONAL {{ {dataset_var} {DCTERMS.publisher.n3()} ?publisher . }}
        OPTIONAL {{ {dataset_var} {DCTERMS.license.n3()} ?license . }}
        OPTIONAL {{ {dataset_var} {DCTERMS.rights.n3()} ?rights . }}
        OPTIONAL {{ {dataset_var} {DCTERMS.language.n3()} ?language . }}
        OPTIONAL {{ {dataset_var} {PROV.hadMember.n3()} ?member . }}
    }}
    """


def get_dataset(kg: KnowledgeGraph, dataset_uri: URIRef) -> Dataset:
    query = _get_dataset_query(dataset_uri)
    query_result = kg.query(query)
    return Dataset(query_result.graph, dataset_uri)


def list_datasets(kg: KnowledgeGraph) -> list[Dataset]:
    query = _get_dataset_query(None)
    query_result = kg.query(query)
    graph = query_result.graph

    result = []
    for subject in graph.subjects(RDF.type, TAMPER.Dataset):
        result.append(Dataset(graph, subject))
    return result


def create_dataset(kg: KnowledgeGraph, dataset: CreateDataset) -> Dataset:
    # TODO: consider input validation
    with kg.tx():
        model = dataset.as_model()
        model.created = datetime.now()

        if dataset_exists(kg, model.identifier):
            raise ResourceAlreadyExistsError(model.identifier)

        kg.insert_statements_default(model.graph)
    return model
