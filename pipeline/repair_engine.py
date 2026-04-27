from __future__ import annotations

from typing import List, Tuple

from pipeline.refiner import BlueprintRefiner
from pipeline.schema_generator import SchemaGenerator
from pipeline.types import ApplicationBlueprint, SystemDesignModel, ValidationIssue

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def validate_blueprint(blueprint: ApplicationBlueprint) -> List[str]:
    issues: List[str] = []
    table_fields = {
        table.name: {field.name for field in table.fields}
        for table in blueprint.database.tables
    }
    endpoint_names = {endpoint.name for endpoint in blueprint.api.endpoints}

    for endpoint in blueprint.api.endpoints:
        source_table = endpoint.source_table
        if source_table and source_table in table_fields:
            allowed = table_fields[source_table]
            for field_name in endpoint.request.keys():
                if field_name not in allowed:
                    issues.append(
                        f"API field '{field_name}' in request of endpoint '{endpoint.name}' "
                        f"is missing in DB table '{source_table}'."
                    )
            for field_name in endpoint.response.keys():
                if field_name != "deleted" and field_name not in allowed:
                    issues.append(
                        f"API field '{field_name}' in response of endpoint '{endpoint.name}' "
                        f"is missing in DB table '{source_table}'."
                    )

        if endpoint.method in WRITE_METHODS and not endpoint.path.startswith("/auth/"):
            if not endpoint.auth_required:
                issues.append(f"Missing auth in write endpoint '{endpoint.name}'.")

    for page in blueprint.ui.pages:
        for component in page.components:
            bound = component.binds_to_endpoint
            if bound and bound not in endpoint_names:
                issues.append(
                    f"UI component '{component.id}' on page '{page.name}' "
                    f"references missing endpoint '{bound}'."
                )

    return sorted(set(issues))


def repair_blueprint(blueprint: ApplicationBlueprint, issues: List[str]) -> Tuple[ApplicationBlueprint, List[str]]:
    if not issues:
        return blueprint, []

    repaired: List[str] = []
    working = blueprint.model_copy(deep=True)

    table_fields = {
        table.name: {field.name for field in table.fields}
        for table in working.database.tables
    }

    for endpoint in working.api.endpoints:
        source_table = endpoint.source_table
        if source_table and source_table in table_fields:
            allowed = table_fields[source_table]

            invalid_request_fields = [name for name in endpoint.request.keys() if name not in allowed]
            for field_name in invalid_request_fields:
                endpoint.request.pop(field_name, None)
                repaired.append(
                    f"Removed invalid API request field '{field_name}' from endpoint '{endpoint.name}'."
                )

            invalid_response_fields = [
                name
                for name in endpoint.response.keys()
                if name not in allowed and name != "deleted"
            ]
            for field_name in invalid_response_fields:
                endpoint.response.pop(field_name, None)
                repaired.append(
                    f"Removed invalid API response field '{field_name}' from endpoint '{endpoint.name}'."
                )

        if endpoint.method in WRITE_METHODS and not endpoint.path.startswith("/auth/"):
            if not endpoint.auth_required:
                endpoint.auth_required = True
                repaired.append(f"Added auth_required=true to endpoint '{endpoint.name}'.")

    endpoint_names = {endpoint.name for endpoint in working.api.endpoints}
    for page in working.ui.pages:
        for component in page.components:
            bound = component.binds_to_endpoint
            if bound and bound not in endpoint_names:
                component.binds_to_endpoint = None
                component.fields = []
                repaired.append(
                    f"Removed invalid UI endpoint reference '{bound}' from component '{component.id}'."
                )

    return working, sorted(set(repaired))


class RepairEngine:
    def __init__(self, schema_generator: SchemaGenerator, refiner: BlueprintRefiner):
        self.schema_generator = schema_generator
        self.refiner = refiner

    def repair(
        self,
        blueprint: ApplicationBlueprint,
        design: SystemDesignModel,
        issues: list[ValidationIssue],
    ) -> Tuple[ApplicationBlueprint, int, List[str]]:
        issue_codes = {issue.code for issue in issues}
        retries = 0
        repaired_actions: List[str] = []

        database = blueprint.database
        api = blueprint.api
        ui = blueprint.ui
        auth = blueprint.auth
        logic = blueprint.logic

        database_refreshed = False
        api_refreshed = False

        if issue_codes.intersection({"INVALID_RELATION", "SECURITY_FIELD_MISSING"}):
            database = self.schema_generator.generate_database(design)
            retries += 1
            database_refreshed = True
            repaired_actions.append("Rebuilt database schema to restore missing relations/security fields.")

        if database_refreshed or issue_codes.intersection(
            {"API_SOURCE_TABLE_MISSING", "API_FIELD_MISMATCH", "AUTH_FLOW_MISSING"}
        ):
            api = self.schema_generator.generate_api(database)
            retries += 1
            api_refreshed = True
            if "AUTH_FLOW_MISSING" in issue_codes:
                repaired_actions.append("Added missing auth flow endpoints for protected access.")
            else:
                repaired_actions.append("Regenerated API mappings to align endpoints with database schema.")

        if api_refreshed or issue_codes.intersection({"UI_ENDPOINT_MISSING", "UI_FIELD_MISMATCH"}):
            ui = self.schema_generator.generate_ui(api)
            retries += 1
            repaired_actions.append("Rebound UI components to valid API endpoints and fields.")

        if api_refreshed or issue_codes.intersection({"AUTH_PERMISSION_UNKNOWN", "RBAC_WEAK_ENFORCEMENT"}):
            auth = self.schema_generator.generate_auth(design, api)
            retries += 1
            repaired_actions.append("Strengthened role permissions for protected and admin-only endpoints.")

        if api_refreshed or issue_codes.intersection({"LOGIC_ENDPOINT_UNCOVERED"}):
            logic = self.schema_generator.generate_logic(design, api)
            retries += 1
            repaired_actions.append("Linked business logic rules to every API endpoint.")

        repaired_blueprint = ApplicationBlueprint(
            database=database,
            api=api,
            ui=ui,
            auth=auth,
            logic=logic,
            assumptions=blueprint.assumptions,
        )
        repaired_blueprint = self.refiner.refine(repaired_blueprint)
        return repaired_blueprint, retries, sorted(set(repaired_actions))
