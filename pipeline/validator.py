from __future__ import annotations

from typing import Dict, List, Optional, Set

from pydantic import ValidationError

from pipeline.types import ApplicationBlueprint, ValidationIssue, ValidationResult


class BlueprintValidator:
    def validate(self, candidate: dict | ApplicationBlueprint) -> ValidationResult:
        issues: List[ValidationIssue] = []

        blueprint: Optional[ApplicationBlueprint] = None
        if isinstance(candidate, ApplicationBlueprint):
            blueprint = candidate
        else:
            try:
                blueprint = ApplicationBlueprint.model_validate(candidate)
            except ValidationError as exc:
                for error in exc.errors():
                    issues.append(
                        ValidationIssue(
                            code="STRUCTURE_INVALID",
                            message=error["msg"],
                            location=".".join(str(part) for part in error["loc"]),
                        )
                    )
                return ValidationResult(valid=False, issues=issues)

        issues.extend(self._validate_relations(blueprint))
        issues.extend(self._validate_api_db_mapping(blueprint))
        issues.extend(self._validate_ui_api_mapping(blueprint))
        issues.extend(self._validate_auth_permissions(blueprint))
        issues.extend(self._validate_security_contracts(blueprint))
        issues.extend(self._validate_logic_endpoint_binding(blueprint))

        return ValidationResult(valid=len(issues) == 0, issues=issues)

    def _validate_relations(self, blueprint: ApplicationBlueprint) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        table_map = {table.name: {field.name for field in table.fields} for table in blueprint.database.tables}

        for relation in blueprint.database.relations:
            if relation.from_table not in table_map:
                issues.append(
                    ValidationIssue(
                        code="INVALID_RELATION",
                        message=f"from_table '{relation.from_table}' does not exist",
                        location="database.relations",
                    )
                )
                continue
            if relation.to_table not in table_map:
                issues.append(
                    ValidationIssue(
                        code="INVALID_RELATION",
                        message=f"to_table '{relation.to_table}' does not exist",
                        location="database.relations",
                    )
                )
                continue
            if relation.from_field not in table_map[relation.from_table]:
                issues.append(
                    ValidationIssue(
                        code="INVALID_RELATION",
                        message=f"from_field '{relation.from_field}' is missing in '{relation.from_table}'",
                        location="database.relations",
                    )
                )
            if relation.to_field not in table_map[relation.to_table]:
                issues.append(
                    ValidationIssue(
                        code="INVALID_RELATION",
                        message=f"to_field '{relation.to_field}' is missing in '{relation.to_table}'",
                        location="database.relations",
                    )
                )

        return issues

    def _validate_api_db_mapping(self, blueprint: ApplicationBlueprint) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        table_map = {table.name: {field.name for field in table.fields} for table in blueprint.database.tables}

        for endpoint in blueprint.api.endpoints:
            source_table = endpoint.source_table
            is_auth_endpoint = endpoint.path.startswith("/auth/")
            if is_auth_endpoint:
                continue
            if not source_table:
                issues.append(
                    ValidationIssue(
                        code="API_SOURCE_TABLE_MISSING",
                        message=f"Endpoint '{endpoint.name}' has no source_table",
                        location=f"api.endpoints.{endpoint.name}",
                    )
                )
                continue
            if source_table not in table_map:
                issues.append(
                    ValidationIssue(
                        code="API_SOURCE_TABLE_MISSING",
                        message=f"source_table '{source_table}' for endpoint '{endpoint.name}' is unknown",
                        location=f"api.endpoints.{endpoint.name}",
                    )
                )
                continue

            allowed = table_map[source_table]
            for field in endpoint.request.keys():
                if field not in allowed:
                    issues.append(
                        ValidationIssue(
                            code="API_FIELD_MISMATCH",
                            message=f"Request field '{field}' not found in table '{source_table}'",
                            location=f"api.endpoints.{endpoint.name}.request",
                        )
                    )
            for field in endpoint.response.keys():
                if field not in allowed and field != "deleted":
                    issues.append(
                        ValidationIssue(
                            code="API_FIELD_MISMATCH",
                            message=f"Response field '{field}' not found in table '{source_table}'",
                            location=f"api.endpoints.{endpoint.name}.response",
                        )
                    )

        return issues

    def _validate_ui_api_mapping(self, blueprint: ApplicationBlueprint) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        endpoint_map: Dict[str, Set[str]] = {}

        for endpoint in blueprint.api.endpoints:
            endpoint_map[endpoint.name] = set(endpoint.request.keys()) | set(endpoint.response.keys())

        for page in blueprint.ui.pages:
            for component in page.components:
                if component.binds_to_endpoint is None:
                    issues.append(
                        ValidationIssue(
                            code="UI_ENDPOINT_MISSING",
                            message=f"Component '{component.id}' is not bound to any endpoint",
                            location=f"ui.pages.{page.name}.{component.id}",
                        )
                    )
                    continue
                if component.binds_to_endpoint not in endpoint_map:
                    issues.append(
                        ValidationIssue(
                            code="UI_ENDPOINT_MISSING",
                            message=f"Component '{component.id}' binds unknown endpoint '{component.binds_to_endpoint}'",
                            location=f"ui.pages.{page.name}.{component.id}",
                        )
                    )
                    continue

                allowed_fields = endpoint_map[component.binds_to_endpoint]
                for field in component.fields:
                    if field not in allowed_fields:
                        issues.append(
                            ValidationIssue(
                                code="UI_FIELD_MISMATCH",
                                message=f"Field '{field}' in '{component.id}' is not exposed by endpoint '{component.binds_to_endpoint}'",
                                location=f"ui.pages.{page.name}.{component.id}.fields",
                            )
                        )

        return issues

    def _validate_auth_permissions(self, blueprint: ApplicationBlueprint) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        known_permissions = {endpoint.name for endpoint in blueprint.api.endpoints}

        for role in blueprint.auth.roles:
            for permission in role.permissions:
                if permission not in known_permissions:
                    issues.append(
                        ValidationIssue(
                            code="AUTH_PERMISSION_UNKNOWN",
                            message=f"Role '{role.role}' has unknown permission '{permission}'",
                            location=f"auth.roles.{role.role}",
                        )
                    )

        return issues

    def _validate_security_contracts(self, blueprint: ApplicationBlueprint) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        table_fields = {
            table.name: {field.name for field in table.fields}
            for table in blueprint.database.tables
        }
        endpoint_names = {endpoint.name for endpoint in blueprint.api.endpoints}

        if "users" in table_fields:
            required_user_fields = {"email", "password_hash", "role", "created_at"}
            missing_fields = sorted(required_user_fields - table_fields["users"])
            for field_name in missing_fields:
                issues.append(
                    ValidationIssue(
                        code="SECURITY_FIELD_MISSING",
                        message=f"users table is missing required security field '{field_name}'",
                        location="database.tables.users",
                    )
                )

            required_auth_endpoints = {"register_user", "login_user", "get_current_user"}
            missing_endpoints = sorted(required_auth_endpoints - endpoint_names)
            for endpoint_name in missing_endpoints:
                issues.append(
                    ValidationIssue(
                        code="AUTH_FLOW_MISSING",
                        message=f"Required auth endpoint '{endpoint_name}' is missing",
                        location="api.endpoints",
                    )
                )

            roles = {role.role: set(role.permissions) for role in blueprint.auth.roles}
            for required_role in {"admin", "user"}:
                if required_role not in roles:
                    issues.append(
                        ValidationIssue(
                            code="RBAC_WEAK_ENFORCEMENT",
                            message=f"Required role '{required_role}' is missing",
                            location="auth.roles",
                        )
                    )

            if "user" in roles:
                disallowed_for_user = {"list_users", "delete_user"}
                leaked_permissions = sorted(roles["user"].intersection(disallowed_for_user))
                for permission in leaked_permissions:
                    issues.append(
                        ValidationIssue(
                            code="RBAC_WEAK_ENFORCEMENT",
                            message=f"user role must not include admin-only permission '{permission}'",
                            location="auth.roles.user",
                        )
                    )

        return issues

    def _validate_logic_endpoint_binding(self, blueprint: ApplicationBlueprint) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        endpoint_names = {endpoint.name for endpoint in blueprint.api.endpoints}
        covered_endpoints: Set[str] = set()

        for rule in blueprint.logic.rules:
            covered_endpoints.update([target for target in rule.applies_to if target in endpoint_names])

        uncovered = sorted(endpoint_names - covered_endpoints)
        for endpoint_name in uncovered:
            issues.append(
                ValidationIssue(
                    code="LOGIC_ENDPOINT_UNCOVERED",
                    message=f"Endpoint '{endpoint_name}' is not referenced by any logic rule",
                    location="logic.rules",
                )
            )

        return issues
