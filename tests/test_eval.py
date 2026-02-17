from darwincode.eval.runner import _parse_test_score


def test_parse_pytest_passed_and_failed():
    output = "======= 8 passed, 2 failed ======="
    assert _parse_test_score(output) == 0.8


def test_parse_pytest_all_passed():
    output = "======= 10 passed ======="
    assert _parse_test_score(output) == 1.0


def test_parse_no_match():
    output = "some random output"
    assert _parse_test_score(output) == 0.0


def test_parse_pytest_complex_output():
    output = """
FAILED tests/test_foo.py::test_bar - AssertionError
FAILED tests/test_foo.py::test_baz - TypeError
======= 3 passed, 2 failed in 1.23s =======
"""
    assert _parse_test_score(output) == 0.6
