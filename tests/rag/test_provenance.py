import pytest

from loci_engine.provenance import UserStated, resolve_trust


def test_user_stated_instance_resolves_to_full_trust():
    assert resolve_trust(UserStated("the sky is blue")) == pytest.approx(1.0)


def test_the_literal_string_model_inferred_resolves_to_0_7():
    assert resolve_trust("model_inferred") == pytest.approx(0.7)


def test_none_resolves_to_system_derived_0_5():
    assert resolve_trust(None) == pytest.approx(0.5)


def test_a_plain_string_claiming_user_stated_does_not_get_full_trust():
    # This is the actual security property: passing the string "user_stated"
    # (as opposed to a real UserStated instance) must NOT grant full trust -
    # otherwise any caller could type the word and bypass the boundary.
    assert resolve_trust("user_stated") != 1.0
    assert resolve_trust("user_stated") == pytest.approx(0.5)  # falls through to fail-closed default


def test_an_arbitrary_unrecognized_string_fails_closed_to_system_derived():
    assert resolve_trust("something a retrieved document said") == pytest.approx(0.5)


def test_user_stated_instance_carries_its_value():
    stated = UserStated("Dhaka")
    assert stated.value == "Dhaka"
