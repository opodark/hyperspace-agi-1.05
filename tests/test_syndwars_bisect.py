# SPDX-License-Identifier: Apache-2.0
import pytest

from scripts.syndwars_bisect import EvalError, find_culprits, parse_result


def make(bad_single=(), bad_pairs=()):
    calls = []

    def is_bad(subset):
        calls.append(tuple(subset))
        return any(b in subset for b in bad_single) or any(set(p) <= set(subset) for p in bad_pairs)

    return is_bad, calls


def test_finds_single_culprits_and_stops_when_clean():
    funcs = [f"f{i}" for i in range(16)]
    is_bad, calls = make(bad_single=("f3", "f11"))
    culprits, interactions = find_culprits(funcs, is_bad, log=lambda m: None)
    assert sorted(culprits) == ["f11", "f3"] and interactions == []
    assert len(calls) < 25


def test_clean_set_needs_one_evaluation():
    is_bad, calls = make()
    assert find_culprits(["a", "b", "c"], is_bad, log=lambda m: None) == ([], [])
    assert len(calls) == 1


def test_pair_that_diverges_only_together_is_reported_as_interaction():
    is_bad, _ = make(bad_pairs=(("a", "d"),))
    culprits, interactions = find_culprits(["a", "b", "c", "d"], is_bad, log=lambda m: None)
    assert culprits == [] and interactions and set(interactions[0]) >= {"a", "d"}


def test_parse_result_takes_last_line_for_name():
    out = "x\nRISULTATO b001 DIVERSO things=3\nRISULTATO b002 IDENTICO sthings=0\n"
    assert parse_result(out, "b001") == ("DIVERSO", "things=3")
    with pytest.raises(EvalError):
        parse_result(out, "b009")
