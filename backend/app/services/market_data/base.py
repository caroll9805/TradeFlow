"""Connector interface for the Market Data Engine.

A connector only *collects raw records*. Validation, matching, normalization, duplicate
detection, quality scoring and storage are shared and live in pipeline.py — so adding a
source means adding one adapter class and registering it."""
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from app.models import DataConnector, DataSource

RawRecord = dict[str, Any]


class ConnectorError(Exception):
    pass


class SourceConnector(ABC):
    type_key: str = ""
    description: str = ""
    # JSON-schema-like description of config keys shown in the admin UI
    config_schema: dict[str, Any] = {}
    # True when collection requires the source's terms to be reviewed & permitted
    requires_terms_permission: bool = True

    def __init__(self, connector: DataConnector | None, source: DataSource):
        self.connector = connector
        self.source = source
        self.config: dict[str, Any] = (connector.config if connector else {}) or {}

    def preflight(self) -> None:
        if self.requires_terms_permission and self.source.terms_status != "permitted":
            raise ConnectorError(
                f"Source '{self.source.name}' terms_status is '{self.source.terms_status}'. Automated collection "
                "is blocked until an administrator records that the source's terms permit it."
            )

    @abstractmethod
    def collect(self, **kwargs: Any) -> Iterable[RawRecord]:
        ...


_REGISTRY: dict[str, type[SourceConnector]] = {}


def register(cls: type[SourceConnector]) -> type[SourceConnector]:
    _REGISTRY[cls.type_key] = cls
    return cls


def get_connector_class(type_key: str) -> type[SourceConnector]:
    if type_key not in _REGISTRY:
        raise ConnectorError(f"Unknown connector type '{type_key}'")
    return _REGISTRY[type_key]


def registry() -> dict[str, type[SourceConnector]]:
    return dict(_REGISTRY)
