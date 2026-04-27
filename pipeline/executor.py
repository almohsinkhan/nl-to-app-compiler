from __future__ import annotations

from typing import Dict, List, Tuple

from sqlalchemy import Boolean, Column, Float, Integer, MetaData, String, Table, Text, create_engine
from sqlalchemy.exc import SQLAlchemyError

from pipeline.types import ApplicationBlueprint


SQLALCHEMY_TYPE_MAP = {
    "integer": Integer,
    "int": Integer,
    "float": Float,
    "string": String,
    "text": Text,
    "boolean": Boolean,
}


class BlueprintExecutor:
    def simulate(self, blueprint: ApplicationBlueprint) -> Tuple[bool, List[str]]:
        issues: List[str] = []
        if not self._validate_database(blueprint, issues):
            return False, issues

        self._validate_endpoints(blueprint, issues)
        return len(issues) == 0, issues

    def _validate_database(self, blueprint: ApplicationBlueprint, issues: List[str]) -> bool:
        metadata = MetaData()
        tables: Dict[str, Table] = {}

        try:
            for table_spec in blueprint.database.tables:
                columns: List[Column] = []
                for field in table_spec.fields:
                    sqlalchemy_type = SQLALCHEMY_TYPE_MAP.get(field.type, String)
                    kwargs = {
                        "nullable": not field.required,
                        "unique": field.unique,
                    }
                    if field.name == table_spec.primary_key:
                        kwargs["primary_key"] = True
                        kwargs["nullable"] = False
                    columns.append(Column(field.name, sqlalchemy_type, **kwargs))

                tables[table_spec.name] = Table(table_spec.name, metadata, *columns)

            for table_spec in blueprint.database.tables:
                current_table = tables[table_spec.name]
                existing_columns = {column.name for column in current_table.columns}
                for fk in table_spec.foreign_keys:
                    if fk.field not in existing_columns:
                        issues.append(
                            f"Foreign key field '{fk.field}' missing in table '{table_spec.name}'"
                        )

            engine = create_engine("sqlite:///:memory:")
            metadata.create_all(engine)
            return True
        except SQLAlchemyError as exc:
            issues.append(f"SQLAlchemy schema simulation failed: {exc}")
            return False

    def _validate_endpoints(self, blueprint: ApplicationBlueprint, issues: List[str]) -> None:
        table_names = {table.name for table in blueprint.database.tables}
        seen = set()

        for endpoint in blueprint.api.endpoints:
            identity = (endpoint.method, endpoint.path)
            if identity in seen:
                issues.append(f"Duplicate endpoint signature: {endpoint.method} {endpoint.path}")
            seen.add(identity)

            if endpoint.source_table and endpoint.source_table not in table_names:
                issues.append(
                    f"Endpoint '{endpoint.name}' references missing table '{endpoint.source_table}'"
                )

            if not endpoint.path.startswith("/"):
                issues.append(f"Endpoint '{endpoint.name}' path must start with '/'")
