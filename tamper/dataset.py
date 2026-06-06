from datetime import datetime
from typing import Generic, TypeVar, overload

from rdflib import DCAT, DCTERMS, RDF, XSD, Graph, Literal, Node, URIRef
from rdflib.resource import Resource


T = TypeVar("T")


class MappedProperty(Generic[T]):
    def __init__(self, predicate: URIRef, datatype: URIRef | None = None):
        self.predicate = predicate
        self.datatype = datatype

    @overload
    def __get__(self, instance: None, owner: type) -> MappedProperty[T]: ...
    @overload
    def __get__(self, instance: Resource, owner: type) -> T | None: ...

    def __get__(self, instance: Resource | None, owner: type):
        if instance is None:
            return None
        value = instance.value(self.predicate)
        if value is None:
            return None
        if isinstance(value, Literal):
            return value.toPython()
        if isinstance(value, Resource):
            return value.identifier
        return value

    def __set__(self, instance: Resource, value: T):
        if isinstance(value, Node):
            instance[self.predicate] = value
        else:
            instance[self.predicate] = Literal(value, datatype=self.datatype)


class Dataset(Resource):
    """A dataset is an RDF graph describing media assets"""

    title: MappedProperty[str] = MappedProperty(DCTERMS.title, XSD.string)
    description: MappedProperty[str] = MappedProperty(DCTERMS.description, XSD.string)
    created: MappedProperty[datetime] = MappedProperty(DCTERMS.created, XSD.dateTime)
    modified: MappedProperty[datetime] = MappedProperty(DCTERMS.modified, XSD.dateTime)
    creator: MappedProperty[str | URIRef] = MappedProperty(DCTERMS.creator, XSD.string)
    publisher: MappedProperty[str | URIRef] = MappedProperty(
        DCTERMS.publisher, XSD.string
    )
    license: MappedProperty[str | URIRef] = MappedProperty(DCTERMS.license, XSD.string)
    rights: MappedProperty[str | URIRef] = MappedProperty(DCTERMS.rights, XSD.string)
    language: MappedProperty[str | URIRef] = MappedProperty(
        DCTERMS.language, XSD.string
    )

    @classmethod
    def new(cls, graph: Graph, identifier: URIRef):
        instance = cls(graph, identifier)
        instance[RDF.type] = DCAT.Dataset
        return instance


class Catalog(Resource):
    """A catalog is a record/collection of datasets"""

    title: MappedProperty[str] = MappedProperty(DCTERMS.title, XSD.string)
    description: MappedProperty[str] = MappedProperty(DCTERMS.description, XSD.string)
    created: MappedProperty[datetime] = MappedProperty(DCTERMS.created, XSD.dateTime)
    modified: MappedProperty[datetime] = MappedProperty(DCTERMS.modified, XSD.dateTime)

    def add_dataset(self, identifier: URIRef):
        self.add(DCAT.dataset, identifier)

    def datasets(self) -> list[Dataset]:
        datasets = []
        for ds in self.objects(DCAT.dataset):
            datasets.append(Dataset(self.graph, ds.identifier))
        return datasets

    @classmethod
    def new(cls, graph: Graph, identifier: URIRef):
        instance = cls(graph, identifier)
        instance[RDF.type] = DCAT.Catalog
        return instance
