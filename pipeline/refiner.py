from __future__ import annotations

from copy import deepcopy

from pipeline.types import ApplicationBlueprint


class BlueprintRefiner:
    def refine(self, blueprint: ApplicationBlueprint) -> ApplicationBlueprint:
        data = deepcopy(blueprint.model_dump())

        table_fields = {
            table["name"]: {field["name"] for field in table["fields"]}
            for table in data["database"]["tables"]
        }
        endpoint_names = {endpoint["name"] for endpoint in data["api"]["endpoints"]}

        for endpoint in data["api"]["endpoints"]:
            source_table = endpoint.get("source_table")
            if source_table and source_table in table_fields:
                allowed = table_fields[source_table]
                endpoint["request"] = {
                    key: value for key, value in endpoint["request"].items() if key in allowed
                }
                endpoint["response"] = {
                    key: value
                    for key, value in endpoint["response"].items()
                    if key in allowed or key in {"deleted"}
                }

        for page in data["ui"]["pages"]:
            for component in page["components"]:
                endpoint_name = component.get("binds_to_endpoint")
                if endpoint_name and endpoint_name not in endpoint_names:
                    component["binds_to_endpoint"] = next(iter(endpoint_names), None)

        for role in data["auth"]["roles"]:
            role["permissions"] = sorted([perm for perm in role["permissions"] if perm in endpoint_names])

        data["assumptions"] = sorted(set(data.get("assumptions", [])))

        return ApplicationBlueprint.model_validate(data)
