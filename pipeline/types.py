from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntentModel(StrictBaseModel):
    app_name: str
    app_type: str
    features: List[str] = Field(default_factory=list)
    user_roles: List[str] = Field(default_factory=list)
    domain_entities: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)


class EntityAttribute(StrictBaseModel):
    name: str
    type: str
    required: bool = True


class EntityDesign(StrictBaseModel):
    name: str
    attributes: List[EntityAttribute] = Field(default_factory=list)


class FlowDesign(StrictBaseModel):
    name: str
    actors: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)


class SystemDesignModel(StrictBaseModel):
    entities: List[EntityDesign] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    flows: List[FlowDesign] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)


class FieldSpec(StrictBaseModel):
    name: str
    type: str
    required: bool = True
    unique: bool = False


class ForeignKeySpec(StrictBaseModel):
    field: str
    references_table: str
    references_field: str


class TableSpec(StrictBaseModel):
    name: str
    fields: List[FieldSpec]
    primary_key: str = "id"
    foreign_keys: List[ForeignKeySpec] = Field(default_factory=list)


class RelationSpec(StrictBaseModel):
    from_table: str
    from_field: str
    to_table: str
    to_field: str
    relation_type: Literal["one_to_one", "one_to_many", "many_to_many"]


class DatabaseSchema(StrictBaseModel):
    tables: List[TableSpec]
    relations: List[RelationSpec] = Field(default_factory=list)


class EndpointSpec(StrictBaseModel):
    name: str
    path: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    auth_required: bool = False
    request: Dict[str, str] = Field(default_factory=dict)
    response: Dict[str, str] = Field(default_factory=dict)
    source_table: Optional[str] = None


class ApiSchema(StrictBaseModel):
    endpoints: List[EndpointSpec]


class ComponentSpec(StrictBaseModel):
    id: str
    type: str
    binds_to_endpoint: Optional[str] = None
    fields: List[str] = Field(default_factory=list)


class PageSpec(StrictBaseModel):
    name: str
    route: str
    components: List[ComponentSpec] = Field(default_factory=list)


class UiSchema(StrictBaseModel):
    pages: List[PageSpec]


class RoleSpec(StrictBaseModel):
    role: str
    permissions: List[str] = Field(default_factory=list)


class AuthSchema(StrictBaseModel):
    roles: List[RoleSpec]


class BusinessRule(StrictBaseModel):
    id: str
    description: str
    applies_to: List[str] = Field(default_factory=list)


class LogicSchema(StrictBaseModel):
    rules: List[BusinessRule]


class ApplicationBlueprint(StrictBaseModel):
    database: DatabaseSchema
    api: ApiSchema
    ui: UiSchema
    auth: AuthSchema
    logic: LogicSchema
    assumptions: List[str] = Field(default_factory=list)


class ValidationIssue(StrictBaseModel):
    code: str
    message: str
    location: str
    severity: Literal["error", "warning"] = "error"


class ValidationResult(StrictBaseModel):
    valid: bool
    issues: List[ValidationIssue] = Field(default_factory=list)


class CompileResponse(StrictBaseModel):
    valid: bool
    blueprint: Optional[ApplicationBlueprint] = None
    clarification_questions: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    issue_details: List[ValidationIssue] = Field(default_factory=list)
    repaired: List[str] = Field(default_factory=list)
    retries: int = 0
    latency_ms: int = 0
