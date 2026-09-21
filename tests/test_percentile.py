"""分位数计算测试。"""
import pytest

from valuation_alert.percentile import InsufficientSamples, percentile_of


def test_basic_uniform():
    assert percentile_of(50, list(range(1, 101)), min_samples=10) == 50.0


def test_extremes():
    assert percentile_of(0, [1, 2, 3], min_samples=1) == 0.0
    assert percentile_of(3, [1, 2, 3], min_samples=1) == 100.0


def test_ties_counted():
    # 经验分布含并列值:4 个 <= 2,共 5 个样本
    assert percentile_of(2, [1, 2, 2, 2, 3], min_samples=1) == 80.0


def test_rounding_one_decimal():
    assert percentile_of(3, [1, 2, 3, 4], min_samples=1) == 75.0
    assert percentile_of(1, [1, 2, 3, 4, 5, 6, 7], min_samples=1) == 14.3


def test_insufficient_samples():
    with pytest.raises(InsufficientSamples):
        percentile_of(1.0, [1.0, 2.0], min_samples=240)


def test_none_values_filtered():
    assert percentile_of(2, [1, None, 2, None, 3], min_samples=3) == 66.7
