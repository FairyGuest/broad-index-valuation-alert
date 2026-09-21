"""数据源注册表:配置中 source 字段 → 适配器实例。"""
from __future__ import annotations

from .base import DataError, DataSource
from .danjuan import DanjuanSource
from .multpl import MultplSource
from .nasdaq import NasdaqSource

SOURCES: dict[str, type[DataSource]] = {
    "danjuan": DanjuanSource,
    "multpl": MultplSource,
    "nasdaq": NasdaqSource,
}


def build_source(source_name: str, **kwargs) -> DataSource:
    try:
        return SOURCES[source_name](**kwargs)
    except KeyError:
        raise DataError(f"未知数据源:{source_name},可选:{list(SOURCES)}") from None


__all__ = ["DataError", "DataSource", "build_source", "DanjuanSource", "MultplSource", "NasdaqSource"]
