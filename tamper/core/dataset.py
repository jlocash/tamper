from datetime import datetime
from rdflib import DCAT, DCTERMS, XSD, URIRef
from ._common import MappedProperty, Resource, TamperURI


class DatasetURI(TamperURI):
    def __new__(cls, slug: str):
        return super().__new__(cls, "dataset", slug)


class Dataset(Resource):
    """A dataset is an RDF graph describing media assets"""

    __rdf_type__ = DCAT.Dataset

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
