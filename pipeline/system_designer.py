from __future__ import annotations

from typing import Dict, List, Optional

from pipeline.intent_extractor import ROLE_KEYWORDS
from pipeline.llm_client import LLMClient, LLMError
from pipeline.prompts import SYSTEM_DESIGN_SCHEMA_DESCRIPTION
from pipeline.types import EntityAttribute, EntityDesign, FlowDesign, IntentModel, SystemDesignModel


ENTITY_ATTRIBUTE_LIBRARY: Dict[str, List[EntityAttribute]] = {
    "user": [
        EntityAttribute(name="id", type="int", required=True),
        EntityAttribute(name="email", type="string", required=True),
        EntityAttribute(name="password_hash", type="string", required=True),
        EntityAttribute(name="role", type="string", required=True),
        EntityAttribute(name="created_at", type="datetime", required=True),
    ],
    "contact": [
        EntityAttribute(name="id", type="int", required=True),
        EntityAttribute(name="first_name", type="string", required=True),
        EntityAttribute(name="last_name", type="string", required=True),
        EntityAttribute(name="email", type="string", required=False),
        EntityAttribute(name="owner_id", type="int", required=True),
    ],
    "task": [
        EntityAttribute(name="id", type="int", required=True),
        EntityAttribute(name="title", type="string", required=True),
        EntityAttribute(name="status", type="string", required=True),
        EntityAttribute(name="assignee_id", type="int", required=False),
    ],
    "invoice": [
        EntityAttribute(name="id", type="int", required=True),
        EntityAttribute(name="amount", type="float", required=True),
        EntityAttribute(name="status", type="string", required=True),
        EntityAttribute(name="customer_id", type="int", required=True),
    ],
    "project": [
        EntityAttribute(name="id", type="int", required=True),
        EntityAttribute(name="name", type="string", required=True),
        EntityAttribute(name="description", type="text", required=False),
        EntityAttribute(name="owner_id", type="int", required=False),
    ],
    "record": [
        EntityAttribute(name="id", type="int", required=True),
        EntityAttribute(name="title", type="string", required=True),
    ],
}


class SystemDesigner:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    def design(self, intent: IntentModel) -> SystemDesignModel:
        if self.llm_client:
            try:
                data = self.llm_client.generate_json(
                    system_prompt=(
                        "You are a software system designer. Return strict JSON only. "
                        + SYSTEM_DESIGN_SCHEMA_DESCRIPTION
                    ),
                    user_prompt=f"Intent JSON: {intent.model_dump_json(indent=2)}",
                )
                return SystemDesignModel.model_validate(data)
            except (LLMError, ValueError):
                pass
        return self._fallback_design(intent)

    def _fallback_design(self, intent: IntentModel) -> SystemDesignModel:
        entities: List[EntityDesign] = []
        selected_entities = intent.domain_entities or ["user", "record"]
        if "user" not in selected_entities:
            selected_entities = ["user", *selected_entities]

        for name in selected_entities:
            attributes = ENTITY_ATTRIBUTE_LIBRARY.get(name, ENTITY_ATTRIBUTE_LIBRARY["record"])
            entities.append(EntityDesign(name=name, attributes=attributes))

        roles = sorted(set((intent.user_roles or []) + ["admin", "user"]))
        roles = [role for role in roles if role in ROLE_KEYWORDS or role == "user"]

        flows = self._build_flows(intent, roles)
        relationships = self._infer_relationships(entities)

        return SystemDesignModel(
            entities=entities,
            roles=roles,
            flows=flows,
            relationships=relationships,
        )

    def _build_flows(self, intent: IntentModel, roles: List[str]) -> List[FlowDesign]:
        flows: List[FlowDesign] = []

        flows.append(
            FlowDesign(
                name="authentication",
                actors=roles,
                steps=[
                    "register account",
                    "hash password",
                    "submit credentials",
                    "issue jwt token",
                    "validate token on protected routes",
                ],
            )
        )

        for entity in intent.domain_entities:
            flows.append(
                FlowDesign(
                    name=f"manage_{entity}",
                    actors=roles,
                    steps=[f"list {entity}", f"create {entity}", f"update {entity}", f"delete {entity}"],
                )
            )

        if "dashboard" in intent.features:
            flows.append(
                FlowDesign(
                    name="view_dashboard",
                    actors=roles,
                    steps=["fetch summary data", "render KPIs", "drill into details"],
                )
            )

        return flows

    def _infer_relationships(self, entities: List[EntityDesign]) -> List[str]:
        relationships: List[str] = []
        entity_names = {entity.name for entity in entities}

        if "user" in entity_names:
            for entity in entities:
                if entity.name == "user":
                    continue
                has_owner = any(attr.name in {"owner_id", "assignee_id", "customer_id"} for attr in entity.attributes)
                if has_owner:
                    relationships.append(f"user one_to_many {entity.name}")

        return sorted(set(relationships))
