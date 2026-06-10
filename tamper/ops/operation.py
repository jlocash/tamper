from rdflib import Node


class PropertyMissingError(ValueError):
    def __init__(self, subject: Node, prop: Node):
        super().__init__(
            f"Graph missing property {prop.n3()} for subject {subject.n3()}"
        )
