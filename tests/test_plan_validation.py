"""Tests for tamper.plans.validation — SHACL plan graph validation."""

import pytest
from rdflib import Graph

from tamper.plans.validation import GraphValidationError, validate_plan_graph


# ---------------------------------------------------------------------------
# Helpers — minimal valid TTL fragments
# ---------------------------------------------------------------------------

_PREFIXES = """\
@prefix plan:   <https://example.org/tamper/plan#> .
@prefix tamper: <https://example.org/tamper/core#> .
@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
"""

# A plan with one step: v0 -> s1 -> v1 (CompressJPEG)
_MINIMAL_VALID_TTL = (
    _PREFIXES
    + """\
<plan://p1> a plan:OperationPlan .

<plan://v0> a plan:Variable ;
    plan:isVariableOfPlan <plan://p1> .

<plan://v1> a plan:Variable ;
    plan:isVariableOfPlan <plan://p1> .

<plan://s1> a plan:Step ;
    plan:isStepOfPlan <plan://p1> ;
    plan:hasInputVariable <plan://v0> ;
    plan:hasOutputVariable <plan://v1> ;
    plan:operationType tamper:CompressJPEG ;
    plan:parameters [
        tamper:qualityFactor 90
    ] .
"""
)


def _parse(ttl: str) -> Graph:
    g = Graph()
    g.parse(data=ttl, format="turtle")
    return g


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestValidPlanGraph:
    def test_minimal_valid_graph_does_not_raise(self):
        g = _parse(_MINIMAL_VALID_TTL)
        # should not raise
        validate_plan_graph(g)

    def test_multi_step_valid_graph_does_not_raise(self):
        ttl = (
            _PREFIXES
            + """\
<plan://p1> a plan:OperationPlan .

<plan://v0> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .
<plan://v1> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .
<plan://v2> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .

<plan://s1> a plan:Step ;
    plan:isStepOfPlan <plan://p1> ;
    plan:hasInputVariable <plan://v0> ;
    plan:hasOutputVariable <plan://v1> ;
    plan:operationType tamper:CompressJPEG ;
    plan:parameters [] .

<plan://s2> a plan:Step ;
    plan:isStepOfPlan <plan://p1> ;
    plan:hasInputVariable <plan://v1> ;
    plan:hasOutputVariable <plan://v2> ;
    plan:operationType tamper:AddGaussianNoise ;
    plan:parameters [] .
"""
        )
        validate_plan_graph(_parse(ttl))


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestMissingPlanDeclaration:
    def test_no_operation_plan_raises(self):
        ttl = (
            _PREFIXES
            + """\
<plan://v0> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .
<plan://v1> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .

<plan://s1> a plan:Step ;
    plan:isStepOfPlan <plan://p1> ;
    plan:hasInputVariable <plan://v0> ;
    plan:hasOutputVariable <plan://v1> ;
    plan:operationType tamper:CompressJPEG ;
    plan:parameters [] .
"""
        )
        with pytest.raises(GraphValidationError):
            validate_plan_graph(_parse(ttl))


class TestMissingStep:
    def test_no_step_raises(self):
        ttl = (
            _PREFIXES
            + """\
<plan://p1> a plan:OperationPlan .
"""
        )
        with pytest.raises(GraphValidationError):
            validate_plan_graph(_parse(ttl))


class TestStepMissingIsStepOfPlan:
    def test_step_without_plan_link_raises(self):
        ttl = (
            _PREFIXES
            + """\
<plan://p1> a plan:OperationPlan .
<plan://v0> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .
<plan://v1> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .

<plan://s1> a plan:Step ;
    plan:hasInputVariable <plan://v0> ;
    plan:hasOutputVariable <plan://v1> ;
    plan:operationType tamper:CompressJPEG ;
    plan:parameters [] .
"""
        )
        with pytest.raises(GraphValidationError):
            validate_plan_graph(_parse(ttl))


class TestStepMissingInputVariable:
    def test_step_without_input_raises(self):
        ttl = (
            _PREFIXES
            + """\
<plan://p1> a plan:OperationPlan .
<plan://v0> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .
<plan://v1> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .

<plan://s1> a plan:Step ;
    plan:isStepOfPlan <plan://p1> ;
    plan:hasOutputVariable <plan://v1> ;
    plan:operationType tamper:CompressJPEG ;
    plan:parameters [] .
"""
        )
        with pytest.raises(GraphValidationError):
            validate_plan_graph(_parse(ttl))


class TestStepMissingOutputVariable:
    def test_step_without_output_raises(self):
        ttl = (
            _PREFIXES
            + """\
<plan://p1> a plan:OperationPlan .
<plan://v0> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .

<plan://s1> a plan:Step ;
    plan:isStepOfPlan <plan://p1> ;
    plan:hasInputVariable <plan://v0> ;
    plan:operationType tamper:CompressJPEG ;
    plan:parameters [] .
"""
        )
        with pytest.raises(GraphValidationError):
            validate_plan_graph(_parse(ttl))


class TestStepMissingOperationParameters:
    def test_step_without_params_raises(self):
        ttl = (
            _PREFIXES
            + """\
<plan://p1> a plan:OperationPlan .
<plan://v0> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .
<plan://v1> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .

<plan://s1> a plan:Step ;
    plan:isStepOfPlan <plan://p1> ;
    plan:hasInputVariable <plan://v0> ;
    plan:hasOutputVariable <plan://v1> .
"""
        )
        with pytest.raises(GraphValidationError):
            validate_plan_graph(_parse(ttl))


class TestOperationParametersMissingOperationType:
    def test_params_without_operation_type_raises(self):
        ttl = (
            _PREFIXES
            + """\
<plan://p1> a plan:OperationPlan .
<plan://v0> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .
<plan://v1> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .

<plan://s1> a plan:Step ;
    plan:isStepOfPlan <plan://p1> ;
    plan:hasInputVariable <plan://v0> ;
    plan:hasOutputVariable <plan://v1> ;
    plan:parameters [] .
"""
        )
        with pytest.raises(GraphValidationError):
            validate_plan_graph(_parse(ttl))


class TestVariableMissingPlanLink:
    def test_variable_not_linked_to_plan_raises(self):
        ttl = (
            _PREFIXES
            + """\
<plan://p1> a plan:OperationPlan .
<plan://v0> a plan:Variable .
<plan://v1> a plan:Variable ; plan:isVariableOfPlan <plan://p1> .

<plan://s1> a plan:Step ;
    plan:isStepOfPlan <plan://p1> ;
    plan:hasInputVariable <plan://v0> ;
    plan:hasOutputVariable <plan://v1> ;
    plan:operationType tamper:CompressJPEG ;
    plan:parameters [] .
"""
        )
        with pytest.raises(GraphValidationError):
            validate_plan_graph(_parse(ttl))


class TestGraphValidationError:
    def test_error_carries_results_graph(self):
        ttl = (
            _PREFIXES
            + """\
<plan://p1> a plan:OperationPlan .
"""
        )
        g = _parse(ttl)
        with pytest.raises(GraphValidationError) as exc_info:
            validate_plan_graph(g)
        err = exc_info.value
        assert err.results_graph is not None
        assert isinstance(str(err), str)
        assert len(str(err)) > 0
