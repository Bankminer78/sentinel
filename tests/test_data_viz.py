"""Tests for sentinel.data_viz."""
import pytest
from sentinel import data_viz as dv


def test_bar_chart_empty():
    assert dv.bar_chart({}) == "(no data)"


def test_bar_chart_single():
    result = dv.bar_chart({"a": 10})
    assert "a" in result
    assert "10" in result


def test_bar_chart_multiple():
    result = dv.bar_chart({"a": 10, "b": 5})
    assert "a" in result
    assert "b" in result


def test_bar_chart_sorted():
    result = dv.bar_chart({"low": 1, "high": 10})
    # "high" should come first due to descending sort
    assert result.index("high") < result.index("low")


def test_line_chart_empty():
    assert dv.line_chart([]) == "(no data)"


def test_line_chart_single():
    result = dv.line_chart([5, 5, 5])
    assert len(result) > 0


def test_line_chart_varied():
    result = dv.line_chart([1, 5, 2, 8, 3])
    assert "•" in result


def test_sparkline_empty():
    assert dv.sparkline([]) == ""


def test_sparkline_flat():
    result = dv.sparkline([5, 5, 5])
    assert len(result) == 3


def test_sparkline_varied():
    result = dv.sparkline([1, 3, 5, 7, 9])
    assert len(result) == 5


def test_heatmap_empty():
    assert dv.heatmap({}) == "(no data)"


def test_heatmap_with_data():
    result = dv.heatmap({"Mon": 1, "Tue": 5, "Wed": 10})
    assert len(result) > 0


def test_table_empty():
    assert dv.table([], ["a", "b"]) == "(empty)"


def test_table_basic():
    rows = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    result = dv.table(rows, ["name", "age"])
    assert "Alice" in result
    assert "Bob" in result


def test_progress_bar():
    result = dv.progress_bar(50, 100)
    assert "%" in result


def test_progress_bar_full():
    result = dv.progress_bar(100, 100)
    assert "100%" in result


def test_progress_bar_zero():
    result = dv.progress_bar(0, 100)
    assert "0%" in result


def test_stem_leaf_empty():
    assert dv.stem_leaf([]) == "(empty)"


def test_stem_leaf_basic():
    result = dv.stem_leaf([10, 12, 20, 25])
    assert "1" in result
    assert "2" in result
