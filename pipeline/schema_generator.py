from __future__ import annotations

from typing import Dict, List, Optional

from pipeline.llm_client import LLMClient
from pipeline.types import (
    ApiSchema,
    AuthSchema,
    BusinessRule,
    ComponentSpec,
    DatabaseSchema,
    EndpointSpec,
    FieldSpec,
    ForeignKeySpec,
    LogicSchema,
    PageSpec,
    RelationSpec,
    RoleSpec,
    SystemDesignModel,
    TableSpec,
    UiSchema,
)


DB_TYPE_MAP = {
    "int": "integer",
    "float": "float",
    "string": "string",
    "text": "text",
    "bool": "boolean",
    "datetime": "datetime",
}

PUBLIC_AUTH_ENDPOINTS = {"register_user", "login_user"}
ADMIN_ONLY_ENDPOINTS = {"list_users", "delete_user"}


class SchemaGenerator:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    def generate_database(self, design: SystemDesignModel) -> DatabaseSchema:
        tables: List[TableSpec] = []
        relations: List[RelationSpec] = []
        entity_table_names = {_table_name(entity.name) for entity in design.entities}

        for entity in design.entities:
            table_name = _table_name(entity.name)
            fields: List[FieldSpec] = []
            foreign_keys: List[ForeignKeySpec] = []

            for attr in entity.attributes:
                field_type = DB_TYPE_MAP.get(attr.type, "string")
                fields.append(
                    FieldSpec(
                        name=attr.name,
                        type=field_type,
                        required=attr.required,
                        unique=attr.name in {"email", "username"},
                    )
                )
                if attr.name.endswith("_id") and attr.name != "id":
                    ref_table = _resolve_reference_table(attr.name, entity_table_names)
                    foreign_keys.append(
                        ForeignKeySpec(
                            field=attr.name,
                            references_table=ref_table,
                            references_field="id",
                        )
                    )
                    relations.append(
                        RelationSpec(
                            from_table=table_name,
                            from_field=attr.name,
                            to_table=ref_table,
                            to_field="id",
                            relation_type="one_to_many",
                        )
                    )

            if not any(field.name == "id" for field in fields):
                fields.insert(0, FieldSpec(name="id", type="integer", required=True, unique=True))

            fields = _harden_table_fields(table_name, fields)

            if table_name == "contacts" and any(field.name == "owner_id" for field in fields):
                references_table = (
                    "users" if "users" in entity_table_names else _resolve_reference_table("owner_id", entity_table_names)
                )
                if not any(fk.field == "owner_id" for fk in foreign_keys):
                    foreign_keys.append(
                        ForeignKeySpec(
                            field="owner_id",
                            references_table=references_table,
                            references_field="id",
                        )
                    )
                if not any(
                    rel.from_table == "contacts" and rel.from_field == "owner_id" and rel.to_table == references_table
                    for rel in relations
                ):
                    relations.append(
                        RelationSpec(
                            from_table="contacts",
                            from_field="owner_id",
                            to_table=references_table,
                            to_field="id",
                            relation_type="one_to_many",
                        )
                    )

            tables.append(
                TableSpec(
                    name=table_name,
                    fields=fields,
                    primary_key="id",
                    foreign_keys=foreign_keys,
                )
            )

        return DatabaseSchema(tables=_sorted_by_name(tables), relations=_dedupe_and_sort_relations(relations))

    def generate_api(self, database: DatabaseSchema) -> ApiSchema:
        endpoints: List[EndpointSpec] = []
        table_map = {table.name: table for table in database.tables}

        if "users" in table_map:
            user_fields = _fields_dict(table_map["users"].fields)
            user_read_fields = _public_user_fields(user_fields)
            register_response = {
                key: value
                for key, value in user_read_fields.items()
                if key in {"id", "email", "role", "created_at"}
            }
            if not register_response:
                register_response = {
                    "id": "integer",
                    "email": "string",
                    "role": "string",
                }

            endpoints.extend(
                [
                    EndpointSpec(
                        name="register_user",
                        path="/auth/register",
                        method="POST",
                        request={"email": "string", "password": "string"},
                        response=register_response,
                        source_table=None,
                    ),
                    EndpointSpec(
                        name="login_user",
                        path="/auth/login",
                        method="POST",
                        request={"email": "string", "password": "string"},
                        response={
                            "access_token": "string",
                            "token_type": "string",
                            "expires_in": "integer",
                        },
                        source_table=None,
                    ),
                    EndpointSpec(
                        name="get_current_user",
                        path="/auth/me",
                        method="GET",
                        request={},
                        response=user_read_fields,
                        source_table=None,
                    ),
                ]
            )

        for table in database.tables:
            base_path = f"/{table.name}"
            fields = _fields_dict(table.fields)
            read_fields = _read_fields_for_table(table.name, fields)
            write_fields = _write_fields_for_table(table.name, fields)
            singular = _singular(table.name)

            if table.name == "users":
                endpoints.extend(
                    [
                        EndpointSpec(
                            name="list_users",
                            path=base_path,
                            method="GET",
                            request={},
                            response=read_fields,
                            source_table=table.name,
                        ),
                        EndpointSpec(
                            name="delete_user",
                            path=f"{base_path}/{{id}}",
                            method="DELETE",
                            request={},
                            response={"deleted": "boolean"},
                            source_table=table.name,
                        ),
                    ]
                )
                continue

            endpoints.extend(
                [
                    EndpointSpec(
                        name=f"list_{table.name}",
                        path=base_path,
                        method="GET",
                        request={},
                        response=fields,
                        source_table=table.name,
                    ),
                    EndpointSpec(
                        name=f"create_{singular}",
                        path=base_path,
                        method="POST",
                        request=write_fields,
                        response=read_fields,
                        source_table=table.name,
                    ),
                    EndpointSpec(
                        name=f"update_{singular}",
                        path=f"{base_path}/{{id}}",
                        method="PUT",
                        request=write_fields,
                        response=read_fields,
                        source_table=table.name,
                    ),
                    EndpointSpec(
                        name=f"delete_{singular}",
                        path=f"{base_path}/{{id}}",
                        method="DELETE",
                        request={},
                        response={"deleted": "boolean"},
                        source_table=table.name,
                    ),
                ]
            )

        return ApiSchema(endpoints=_sorted_by_name(endpoints))

    def generate_ui(self, api: ApiSchema) -> UiSchema:
        pages: List[PageSpec] = []
        endpoints_by_name = {endpoint.name: endpoint for endpoint in api.endpoints}

        if "login_user" in endpoints_by_name:
            login_endpoint = endpoints_by_name["login_user"]
            pages.append(
                PageSpec(
                    name="Login",
                    route="/login",
                    components=[
                        ComponentSpec(
                            id="login_form",
                            type="form",
                            binds_to_endpoint=login_endpoint.name,
                            fields=sorted(login_endpoint.request.keys()),
                        )
                    ],
                )
            )

        if "register_user" in endpoints_by_name:
            register_endpoint = endpoints_by_name["register_user"]
            pages.append(
                PageSpec(
                    name="Register",
                    route="/register",
                    components=[
                        ComponentSpec(
                            id="register_form",
                            type="form",
                            binds_to_endpoint=register_endpoint.name,
                            fields=sorted(register_endpoint.request.keys()),
                        )
                    ],
                )
            )

        dashboard_components: List[ComponentSpec] = []
        if "list_contacts" in endpoints_by_name:
            dashboard_components.append(
                ComponentSpec(
                    id="dashboard_total_contacts",
                    type="kpi_tile",
                    binds_to_endpoint="list_contacts",
                    fields=["id"],
                )
            )
        elif api.endpoints:
            first_list = next((ep for ep in api.endpoints if ep.method == "GET"), api.endpoints[0])
            dashboard_components.append(
                ComponentSpec(
                    id="dashboard_summary",
                    type="kpi_grid",
                    binds_to_endpoint=first_list.name,
                    fields=sorted(first_list.response.keys())[:1],
                )
            )

        if "get_current_user" in endpoints_by_name:
            me_endpoint = endpoints_by_name["get_current_user"]
            user_fields = [field for field in ("id", "email", "role", "created_at") if field in me_endpoint.response]
            dashboard_components.append(
                ComponentSpec(
                    id="dashboard_user_info",
                    type="profile_card",
                    binds_to_endpoint=me_endpoint.name,
                    fields=user_fields or sorted(me_endpoint.response.keys()),
                )
            )

        pages.append(
            PageSpec(
                name="Dashboard",
                route="/dashboard",
                components=dashboard_components,
            )
        )

        if "list_contacts" in endpoints_by_name:
            list_contacts = endpoints_by_name["list_contacts"]
            create_contact = endpoints_by_name.get("create_contact")
            pages.append(
                PageSpec(
                    name="Contacts",
                    route="/contacts",
                    components=[
                        ComponentSpec(
                            id="contacts_table",
                            type="data_table",
                            binds_to_endpoint=list_contacts.name,
                            fields=sorted(list_contacts.response.keys()),
                        ),
                        ComponentSpec(
                            id="contacts_form",
                            type="form",
                            binds_to_endpoint=(create_contact.name if create_contact else list_contacts.name),
                            fields=(
                                sorted(create_contact.request.keys())
                                if create_contact
                                else [field for field in sorted(list_contacts.response.keys()) if field != "id"]
                            ),
                        ),
                    ],
                )
            )

        if "list_users" in endpoints_by_name:
            users_endpoint = endpoints_by_name["list_users"]
            analytics_bind = "list_contacts" if "list_contacts" in endpoints_by_name else users_endpoint.name
            pages.append(
                PageSpec(
                    name="Admin Panel",
                    route="/admin",
                    components=[
                        ComponentSpec(
                            id="admin_users_table",
                            type="data_table",
                            binds_to_endpoint=users_endpoint.name,
                            fields=sorted(users_endpoint.response.keys()),
                        ),
                        ComponentSpec(
                            id="admin_analytics",
                            type="kpi_grid",
                            binds_to_endpoint=analytics_bind,
                            fields=["id"],
                        ),
                    ],
                )
            )

        for endpoint in api.endpoints:
            if endpoint.method != "GET":
                continue
            if endpoint.source_table in {None, "users", "contacts"}:
                continue
            source_table = endpoint.source_table
            create_endpoint = next(
                (
                    item
                    for item in api.endpoints
                    if item.source_table == source_table and item.method == "POST"
                ),
                endpoint,
            )
            merged_fields = sorted(set(endpoint.response.keys()) | set(create_endpoint.request.keys()))
            pages.append(
                PageSpec(
                    name=f"{source_table.title()} Management",
                    route=f"/{source_table}",
                    components=[
                        ComponentSpec(
                            id=f"{source_table}_table",
                            type="data_table",
                            binds_to_endpoint=endpoint.name,
                            fields=merged_fields,
                        ),
                        ComponentSpec(
                            id=f"{source_table}_form",
                            type="form",
                            binds_to_endpoint=create_endpoint.name,
                            fields=[field for field in merged_fields if field != "id"],
                        ),
                    ],
                )
            )

        return UiSchema(pages=_sorted_pages(pages))

    def generate_auth(self, design: SystemDesignModel, api: ApiSchema) -> AuthSchema:
        endpoints_by_name = {endpoint.name: endpoint for endpoint in api.endpoints}
        endpoint_names = set(endpoints_by_name.keys())
        protected_endpoints = endpoint_names - PUBLIC_AUTH_ENDPOINTS
        roles: List[RoleSpec] = []
        role_names = sorted(set((design.roles or []) + ["admin", "user"]))

        for role in role_names:
            permissions: List[str]
            if role == "admin":
                permissions = sorted(protected_endpoints)
            elif role in {"manager", "agent", "staff"}:
                permissions = sorted(
                    [
                        name
                        for name in protected_endpoints
                        if not name.startswith("delete_") and name != "list_users"
                    ]
                )
            else:
                permissions = sorted(
                    [
                        endpoint.name
                        for endpoint in api.endpoints
                        if endpoint.name in protected_endpoints
                        and (
                            endpoint.name == "get_current_user"
                            or endpoint.source_table == "contacts"
                            or (
                                endpoint.method == "GET"
                                and endpoint.source_table not in {None, "users"}
                            )
                        )
                    ]
                )
            roles.append(RoleSpec(role=role, permissions=permissions))

        return AuthSchema(roles=roles)

    def generate_logic(self, design: SystemDesignModel, api: ApiSchema) -> LogicSchema:
        _ = design
        endpoints = {endpoint.name: endpoint for endpoint in api.endpoints}
        protected_endpoints = sorted(name for name in endpoints if name not in PUBLIC_AUTH_ENDPOINTS)
        write_endpoints = sorted(
            [
                endpoint.name
                for endpoint in api.endpoints
                if endpoint.method in {"POST", "PUT", "PATCH", "DELETE"}
                and endpoint.name not in PUBLIC_AUTH_ENDPOINTS
            ]
        )
        contact_endpoints = sorted(
            [endpoint.name for endpoint in api.endpoints if endpoint.source_table == "contacts"]
        )
        admin_endpoints = sorted([name for name in ADMIN_ONLY_ENDPOINTS if name in endpoints])

        rules: List[BusinessRule] = []

        if "register_user" in endpoints:
            rules.append(
                BusinessRule(
                    id="rule_password_hashing",
                    description="Passwords must be salted and hashed before persisting user credentials.",
                    applies_to=["register_user"],
                )
            )

        if "login_user" in endpoints:
            rules.append(
                BusinessRule(
                    id="rule_jwt_issue",
                    description="Successful login must issue a signed JWT token with expiration metadata.",
                    applies_to=["login_user"],
                )
            )

        if protected_endpoints:
            rules.append(
                BusinessRule(
                    id="rule_token_required",
                    description="Protected endpoints require a valid bearer token and active session.",
                    applies_to=protected_endpoints,
                )
            )

        if write_endpoints:
            rules.append(
                BusinessRule(
                    id="rule_write_requires_auth",
                    description="All write operations require authentication and must be auditable.",
                    applies_to=write_endpoints,
                )
            )

        if contact_endpoints:
            rules.append(
                BusinessRule(
                    id="rule_contact_ownership_scope",
                    description=(
                        "Non-admin users can only access contacts they own; contact ownership is "
                        "derived from the authenticated user."
                    ),
                    applies_to=contact_endpoints,
                )
            )

        if admin_endpoints:
            rules.append(
                BusinessRule(
                    id="rule_admin_only_endpoints",
                    description="User-management endpoints are restricted to admin role.",
                    applies_to=admin_endpoints,
                )
            )

        if "get_current_user" in endpoints:
            rules.append(
                BusinessRule(
                    id="rule_session_identity",
                    description="Current user endpoint resolves identity from JWT claims.",
                    applies_to=["get_current_user"],
                )
            )

        return LogicSchema(rules=_sorted_by_name(rules))


def _table_name(entity_name: str) -> str:
    normalized = entity_name.strip().lower().replace(" ", "_")
    if normalized.endswith("s"):
        return normalized
    return f"{normalized}s"


def _sorted_by_name(items: List) -> List:
    return sorted(items, key=lambda item: getattr(item, "name", getattr(item, "id", "")))


def _sort_relations(items: List[RelationSpec]) -> List[RelationSpec]:
    return sorted(items, key=lambda item: (item.from_table, item.from_field, item.to_table))


def _dedupe_and_sort_relations(items: List[RelationSpec]) -> List[RelationSpec]:
    deduped: Dict[tuple[str, str, str, str, str], RelationSpec] = {}
    for item in items:
        key = (
            item.from_table,
            item.from_field,
            item.to_table,
            item.to_field,
            item.relation_type,
        )
        deduped[key] = item
    return _sort_relations(list(deduped.values()))


def _sorted_pages(items: List[PageSpec]) -> List[PageSpec]:
    route_order = {
        "/login": 0,
        "/register": 1,
        "/dashboard": 2,
        "/contacts": 3,
        "/admin": 4,
    }
    return sorted(items, key=lambda page: (route_order.get(page.route, 99), page.name))


def _fields_dict(fields: List[FieldSpec]) -> Dict[str, str]:
    return {field.name: field.type for field in fields}


def _public_user_fields(fields: Dict[str, str]) -> Dict[str, str]:
    return {
        key: value
        for key, value in fields.items()
        if key not in {"password_hash", "password"}
    }


def _read_fields_for_table(table_name: str, fields: Dict[str, str]) -> Dict[str, str]:
    if table_name == "users":
        return _public_user_fields(fields)
    return dict(fields)


def _write_fields_for_table(table_name: str, fields: Dict[str, str]) -> Dict[str, str]:
    excluded = {"id", "created_at"}
    if table_name == "contacts":
        excluded.add("owner_id")
    if table_name == "users":
        excluded.add("password_hash")
    return {key: value for key, value in fields.items() if key not in excluded}


def _harden_table_fields(table_name: str, fields: List[FieldSpec]) -> List[FieldSpec]:
    hardened = list(fields)

    if table_name == "users":
        for field in hardened:
            if field.name == "password":
                field.name = "password_hash"
                field.required = True
            if field.name == "email":
                field.required = True
                field.unique = True
        _ensure_field(hardened, name="email", field_type="string", required=True, unique=True)
        _ensure_field(hardened, name="password_hash", field_type="string", required=True, unique=False)
        _ensure_field(hardened, name="role", field_type="string", required=True, unique=False)
        _ensure_field(hardened, name="created_at", field_type="datetime", required=True, unique=False)

    if table_name == "contacts":
        _ensure_field(hardened, name="owner_id", field_type="integer", required=True, unique=False)

    return hardened


def _ensure_field(
    fields: List[FieldSpec],
    name: str,
    field_type: str,
    required: bool,
    unique: bool,
) -> None:
    existing = next((field for field in fields if field.name == name), None)
    if existing:
        existing.type = field_type
        existing.required = required
        existing.unique = unique
        return
    fields.append(
        FieldSpec(
            name=name,
            type=field_type,
            required=required,
            unique=unique,
        )
    )


def _singular(table_name: str) -> str:
    if table_name.endswith("ies"):
        return f"{table_name[:-3]}y"
    if table_name.endswith("s"):
        return table_name[:-1]
    return table_name


def _resolve_reference_table(field_name: str, known_tables: set[str]) -> str:
    stem = field_name.replace("_id", "")
    candidate = _table_name(stem)
    if candidate in known_tables:
        return candidate

    semantic_map = {
        "owner": "users",
        "assignee": "users",
        "customer": "contacts",
        "created_by": "users",
        "updated_by": "users",
    }
    mapped = semantic_map.get(stem)
    if mapped and mapped in known_tables:
        return mapped

    if "users" in known_tables:
        return "users"
    return next(iter(known_tables), candidate)
