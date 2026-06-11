"""Behavioral tests for plan materialization and the thread pool executor."""

from graphlib import CycleError
from pathlib import Path

import pytest
from rdflib import PROV, RDF, Graph, URIRef

from tamper.core import OperationPlan, load_asset_from_file
from tamper.errors import GraphValidationError
from tamper.plans.thread_executor import ThreadPoolPlanExecutor, materialize_operations
from tamper.vocabularies import TAMPER

JPG = Path(__file__).parent / "test-media" / "images" / "file_example_JPG_100kB.jpg"

PREFIXES = """
@prefix plan:   <https://example.org/tamper/plan#> .
@prefix tamper: <https://example.org/tamper/core#> .
"""

# v0 --CompressJPEG--> v1 --AddGaussianNoise--> v2
CHAINED_PLAN = (
    PREFIXES
    + """
<trn:plan:test> a plan:OperationPlan .

<trn:plan:test:v0> a plan:Variable ; plan:isVariableOfPlan <trn:plan:test> .
<trn:plan:test:v1> a plan:Variable ; plan:isVariableOfPlan <trn:plan:test> .
<trn:plan:test:v2> a plan:Variable ; plan:isVariableOfPlan <trn:plan:test> .

<trn:plan:test:s1> a plan:Step ;
    plan:isStepOfPlan <trn:plan:test> ;
    plan:hasInputVariable <trn:plan:test:v0> ;
    plan:hasOutputVariable <trn:plan:test:v1> ;
    plan:operationType tamper:CompressJPEG ;
    plan:parameters [ tamper:qualityFactor 80 ] .

<trn:plan:test:s2> a plan:Step ;
    plan:isStepOfPlan <trn:plan:test> ;
    plan:hasInputVariable <trn:plan:test:v1> ;
    plan:hasOutputVariable <trn:plan:test:v2> ;
    plan:operationType tamper:AddGaussianNoise ;
    plan:parameters [
        tamper:gaussianMean 0.0 ;
        tamper:gaussianStd 10.0 ;
        tamper:gaussianSeed 7
    ] .
"""
)


def _plan(ttl: str, uri: str = "trn:plan:test") -> OperationPlan:
    g = Graph()
    g.parse(data=ttl, format="turtle")
    return OperationPlan(g, URIRef(uri))


class TestMaterializeOperations:
    def test_creates_one_operation_per_step(self):
        plan = _plan(CHAINED_PLAN)
        graph, step_to_op = materialize_operations(plan)

        assert set(step_to_op) == {
            URIRef("trn:plan:test:s1"),
            URIRef("trn:plan:test:s2"),
        }
        ops = set(graph.subjects(RDF.type, None))
        assert set(step_to_op.values()) == ops

    def test_operations_typed_from_step_operation_type(self):
        plan = _plan(CHAINED_PLAN)
        graph, step_to_op = materialize_operations(plan)

        s1_op = step_to_op[URIRef("trn:plan:test:s1")]
        s2_op = step_to_op[URIRef("trn:plan:test:s2")]
        assert (s1_op, RDF.type, TAMPER.CompressJPEG) in graph
        assert (s2_op, RDF.type, TAMPER.AddGaussianNoise) in graph

    def test_parameters_copied_to_operation(self):
        plan = _plan(CHAINED_PLAN)
        graph, step_to_op = materialize_operations(plan)

        s1_op = step_to_op[URIRef("trn:plan:test:s1")]
        s2_op = step_to_op[URIRef("trn:plan:test:s2")]
        assert graph.value(s1_op, TAMPER.qualityFactor).toPython() == 80
        assert graph.value(s2_op, TAMPER.gaussianStd).toPython() == 10.0
        assert graph.value(s2_op, TAMPER.gaussianSeed).toPython() == 7

    def test_unknown_operation_type_raises(self):
        ttl = (
            PREFIXES
            + """
<trn:plan:test> a plan:OperationPlan .
<trn:plan:test:v0> a plan:Variable ; plan:isVariableOfPlan <trn:plan:test> .
<trn:plan:test:v1> a plan:Variable ; plan:isVariableOfPlan <trn:plan:test> .
<trn:plan:test:s1> a plan:Step ;
    plan:isStepOfPlan <trn:plan:test> ;
    plan:hasInputVariable <trn:plan:test:v0> ;
    plan:hasOutputVariable <trn:plan:test:v1> ;
    plan:operationType tamper:DoesNotExist ;
    plan:parameters [ tamper:qualityFactor 80 ] .
"""
        )
        with pytest.raises(ValueError):
            materialize_operations(_plan(ttl))

    def test_invalid_parameters_raise(self):
        ttl = CHAINED_PLAN.replace(
            "tamper:qualityFactor 80", "tamper:qualityFactor 999"
        )
        with pytest.raises(GraphValidationError):
            materialize_operations(_plan(ttl))


class TestThreadPoolPlanExecutor:
    def test_executes_chained_plan(self, tmp_path):
        seed = Graph()
        asset = load_asset_from_file(seed, JPG)
        executor = ThreadPoolPlanExecutor(tmp_path, max_workers=2)

        result = executor.execute(
            _plan(CHAINED_PLAN), seed, {URIRef("trn:plan:test:v0"): asset.identifier}
        )

        compress_op = result.value(predicate=RDF.type, object=TAMPER.CompressJPEG)
        noise_op = result.value(predicate=RDF.type, object=TAMPER.AddGaussianNoise)
        compressed = result.value(predicate=PROV.wasGeneratedBy, object=compress_op)
        noisy = result.value(predicate=PROV.wasGeneratedBy, object=noise_op)

        # derivation chain: original -> compress -> compressed -> noise -> noisy
        assert (compress_op, PROV.used, asset.identifier) in result
        assert (noise_op, PROV.used, compressed) in result
        assert noisy is not None
        assert len({asset.identifier, compressed, noisy}) == 3

    def test_generated_assets_written_to_out_dir(self, tmp_path):
        seed = Graph()
        asset = load_asset_from_file(seed, JPG)
        executor = ThreadPoolPlanExecutor(tmp_path, max_workers=2)

        result = executor.execute(
            _plan(CHAINED_PLAN), seed, {URIRef("trn:plan:test:v0"): asset.identifier}
        )

        generated = set(result.subjects(PROV.wasGeneratedBy, None))
        assert len(generated) == 2
        for asset_uri in generated:
            file_path = Path(str(result.value(asset_uri, TAMPER.filePath)))
            assert file_path.exists()
            assert file_path.parent == tmp_path

    def test_records_operation_timestamps(self, tmp_path):
        seed = Graph()
        asset = load_asset_from_file(seed, JPG)
        executor = ThreadPoolPlanExecutor(tmp_path)

        result = executor.execute(
            _plan(CHAINED_PLAN), seed, {URIRef("trn:plan:test:v0"): asset.identifier}
        )

        for op in result.subjects(RDF.type, TAMPER.CompressJPEG):
            started = result.value(op, PROV.startedAtTime)
            ended = result.value(op, PROV.endedAtTime)
            assert started is not None
            assert ended is not None
            assert started.toPython() <= ended.toPython()

    def test_cyclic_plan_raises(self, tmp_path):
        ttl = (
            PREFIXES
            + """
<trn:plan:test> a plan:OperationPlan .
<trn:plan:test:v0> a plan:Variable ; plan:isVariableOfPlan <trn:plan:test> .
<trn:plan:test:v1> a plan:Variable ; plan:isVariableOfPlan <trn:plan:test> .
<trn:plan:test:s1> a plan:Step ;
    plan:isStepOfPlan <trn:plan:test> ;
    plan:hasInputVariable <trn:plan:test:v0> ;
    plan:hasOutputVariable <trn:plan:test:v1> ;
    plan:operationType tamper:CompressJPEG ;
    plan:parameters [ tamper:qualityFactor 80 ] .
<trn:plan:test:s2> a plan:Step ;
    plan:isStepOfPlan <trn:plan:test> ;
    plan:hasInputVariable <trn:plan:test:v1> ;
    plan:hasOutputVariable <trn:plan:test:v0> ;
    plan:operationType tamper:CompressJPEG ;
    plan:parameters [ tamper:qualityFactor 80 ] .
"""
        )
        executor = ThreadPoolPlanExecutor(tmp_path)
        with pytest.raises(CycleError):
            executor.execute(_plan(ttl), Graph(), {})
