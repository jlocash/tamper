from typing import Generic, TypeVar, overload

from rdflib import RDF, Graph, IdentifiedNode, Literal, URIRef
from rdflib.resource import Resource as RDFResource

T = TypeVar("T")


class TamperURI(URIRef):
    def __new__(cls, *parts: str):
        base = "trn"
        value = ":".join([base, *parts])
        return super().__new__(cls, value)

    def __eq__(self, other):
        return URIRef(self) == other

    __hash__ = str.__hash__


class Resource(RDFResource):
    __rdf_type__: URIRef | None = None
    _property_map: "dict[URIRef, MappedProperty]" = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        prop_map: dict[URIRef, MappedProperty] = {}
        for klass in reversed(cls.__mro__):
            for val in vars(klass).values():
                if isinstance(val, MappedProperty):
                    prop_map[val.predicate] = val
        cls._property_map = prop_map

    @classmethod
    def new(cls, graph: Graph, identifier: IdentifiedNode):
        inst = cls(graph, identifier)
        if cls.__rdf_type__ is not None:
            inst[RDF.type] = cls.__rdf_type__
        return inst

    def __getitem__(self, item):
        if item in self._property_map:
            return self._property_map[item].__get__(self, type(self))
        return super().__getitem__(item)

    def __setitem__(self, item, value):
        if item in self._property_map:
            return self._property_map[item].__set__(self, value)
        return super().__setitem__(item, value)


class MappedProperty(Generic[T]):
    def __init__(
        self,
        predicate: URIRef,
        datatype: URIRef | None = None,
        inverse: bool = False,
        many: bool = False,
    ):
        self.predicate = predicate
        self.datatype = datatype
        self.inverse = inverse
        self.many = many

    @overload
    def __get__(self, instance: None, owner: type) -> MappedProperty[T]: ...
    @overload
    def __get__(self, instance: Resource, owner: type) -> T | None: ...

    def __get__(self, instance: Resource | None, owner: type):
        if instance is None:
            return self

        if self.inverse:
            value = instance.graph.subjects(self.predicate, instance.identifier)
        else:
            value = instance.graph.objects(instance.identifier, self.predicate)

        def _unwrap(v):
            if v is None:
                return None
            if isinstance(v, Literal):
                return v.toPython()
            if isinstance(v, Resource):
                return v.identifier
            return v

        if self.many:
            return list(map(_unwrap, value))
        return _unwrap(next(value, None))

    def __set__(self, instance: Resource, value: T):
        if isinstance(value, IdentifiedNode):
            node = value
        else:
            node = Literal(value, datatype=self.datatype)
        instance.graph.set((instance.identifier, self.predicate, node))
