from __future__ import annotations

import re
from typing import List, Optional, Tuple

from pipeline.llm_client import LLMClient, LLMError
from pipeline.prompts import INTENT_SCHEMA_DESCRIPTION
from pipeline.types import IntentModel


FEATURE_KEYWORDS = {
    "login": ["login", "auth", "authentication", "sign in"],
    "dashboard": ["dashboard", "analytics", "overview"],
    "rbac": ["role", "permission", "rbac", "access control"],
    "contacts": ["contact", "lead", "customer"],
    "notifications": ["notification", "email", "sms"],
    "reporting": ["report", "export", "insight"],
}

ENTITY_KEYWORDS = {
    "user": ["user", "member", "account"],
    "contact": ["contact", "lead", "customer"],
    "task": ["task", "todo", "activity"],
    "invoice": ["invoice", "billing", "payment"],
    "project": ["project", "milestone"],
}

ROLE_KEYWORDS = ["admin", "manager", "agent", "staff", "viewer", "customer", "user"]


class IntentExtractor:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    def extract(self, prompt: str) -> Tuple[IntentModel, List[str], List[str]]:
        normalized = _normalize(prompt)
        clarification_questions = self._clarification_questions(normalized)

        if self.llm_client:
            try:
                data = self.llm_client.generate_json(
                    system_prompt=(
                        "You are an intent extractor for software app requests. "
                        "Return strict JSON only. " + INTENT_SCHEMA_DESCRIPTION
                    ),
                    user_prompt=f"User request: {prompt}",
                )
                intent = IntentModel.model_validate(data)
                return intent, clarification_questions, self._derive_assumptions(intent, normalized)
            except (LLMError, ValueError):
                pass

        intent = self._fallback_extract(normalized)
        return intent, clarification_questions, self._derive_assumptions(intent, normalized)

    def _fallback_extract(self, normalized_prompt: str) -> IntentModel:
        app_name = self._extract_app_name(normalized_prompt)
        app_type = self._extract_app_type(normalized_prompt)
        features = _extract_by_keywords(normalized_prompt, FEATURE_KEYWORDS)
        entities = _extract_by_keywords(normalized_prompt, ENTITY_KEYWORDS)
        roles = [role for role in ROLE_KEYWORDS if role in normalized_prompt]

        constraints: List[str] = []
        if "mobile" in normalized_prompt:
            constraints.append("must support mobile-friendly UI")
        if "multi tenant" in normalized_prompt or "multi-tenant" in normalized_prompt:
            constraints.append("must support tenant isolation")

        unknowns: List[str] = []
        if not roles:
            unknowns.append("No explicit user roles provided")
        if not entities:
            unknowns.append("No clear domain entities provided")
        if not features:
            unknowns.append("No explicit application features provided")

        return IntentModel(
            app_name=app_name,
            app_type=app_type,
            features=features,
            user_roles=roles,
            domain_entities=entities,
            constraints=constraints,
            unknowns=unknowns,
        )

    def _extract_app_name(self, normalized_prompt: str) -> str:
        match = re.search(r"(?:build|create|make)\s+(?:an?\s+)?([a-z0-9\s-]{3,40})", normalized_prompt)
        if match:
            candidate = match.group(1).strip().split(" with ")[0]
            return candidate.title()
        return "Generated Application"

    def _extract_app_type(self, normalized_prompt: str) -> str:
        if "crm" in normalized_prompt:
            return "crm"
        if "ecommerce" in normalized_prompt or "store" in normalized_prompt:
            return "ecommerce"
        if "erp" in normalized_prompt:
            return "erp"
        if "saas" in normalized_prompt:
            return "saas"
        return "web_application"

    def _clarification_questions(self, normalized_prompt: str) -> List[str]:
        questions: List[str] = []
        token_count = len(normalized_prompt.split())
        if token_count < 5:
            questions.append("What is the primary app domain and target users?")
        if not any(role in normalized_prompt for role in ROLE_KEYWORDS):
            questions.append("Which user roles should exist (e.g., admin, manager, viewer)?")
        if not any(key in normalized_prompt for key in ("api", "dashboard", "login", "auth", "report")):
            questions.append("What are the top 3 core features you want first?")
        return questions

    def _derive_assumptions(self, intent: IntentModel, normalized_prompt: str) -> List[str]:
        assumptions: List[str] = []
        if not intent.user_roles:
            assumptions.append("Default roles assumed: admin, user")
        if "login" not in normalized_prompt and "auth" not in normalized_prompt:
            assumptions.append("Authentication is required by default for non-public pages")
        if not intent.domain_entities:
            assumptions.append("Generic core entities assumed: user, record")
        return assumptions


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _extract_by_keywords(text: str, mapping: dict[str, list[str]]) -> List[str]:
    found: List[str] = []
    for key, variants in mapping.items():
        if any(variant in text for variant in variants):
            found.append(key)
    return sorted(set(found))
