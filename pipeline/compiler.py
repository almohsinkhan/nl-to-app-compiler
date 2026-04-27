from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

from pipeline.config import load_config
from pipeline.executor import BlueprintExecutor
from pipeline.intent_extractor import IntentExtractor
from pipeline.llm_client import LLMClient
from pipeline.refiner import BlueprintRefiner
from pipeline.repair_engine import RepairEngine, repair_blueprint, validate_blueprint
from pipeline.schema_generator import SchemaGenerator
from pipeline.system_designer import SystemDesigner
from pipeline.types import (
    ApplicationBlueprint,
    CompileResponse,
    ValidationIssue,
)
from pipeline.validator import BlueprintValidator


class PipelineCompiler:
    def __init__(self):
        llm_client = None
        config = load_config()
        if config:
            llm_client = LLMClient(config)

        self.intent_extractor = IntentExtractor(llm_client)
        self.system_designer = SystemDesigner(llm_client)
        self.schema_generator = SchemaGenerator(llm_client)
        self.refiner = BlueprintRefiner()
        self.validator = BlueprintValidator()
        self.repair_engine = RepairEngine(self.schema_generator, self.refiner)
        self.executor = BlueprintExecutor()

    def compile(self, prompt: str) -> CompileResponse:
        started = time.perf_counter()
        retries = 0
        repaired_actions: list[str] = []
        detected_issues: Dict[Tuple[str, str, str], ValidationIssue] = {}

        def _collect_issues(items: list[ValidationIssue]) -> None:
            for issue in items:
                key = (issue.code, issue.location, issue.message)
                detected_issues[key] = issue

        intent, clarification_questions, assumptions = self.intent_extractor.extract(prompt)

        if clarification_questions and len(prompt.split()) < 5:
            return CompileResponse(
                valid=False,
                clarification_questions=clarification_questions,
                assumptions=assumptions,
                issues=[],
                issue_details=[],
                repaired=[],
                retries=0,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )

        design = self.system_designer.design(intent)
        database = self.schema_generator.generate_database(design)
        api = self.schema_generator.generate_api(database)
        ui = self.schema_generator.generate_ui(api)
        auth = self.schema_generator.generate_auth(design, api)
        logic = self.schema_generator.generate_logic(design, api)

        blueprint = ApplicationBlueprint(
            database=database,
            api=api,
            ui=ui,
            auth=auth,
            logic=logic,
            assumptions=sorted(set(assumptions + intent.unknowns)),
        )
        blueprint = self.refiner.refine(blueprint)

        simple_issues = validate_blueprint(blueprint)
        unresolved_simple_issues: list[str] = []
        if simple_issues:
            blueprint, simple_repairs = repair_blueprint(blueprint, simple_issues)
            if simple_repairs:
                repaired_actions.extend(simple_repairs)
                retries += 1
            unresolved_simple_issues = validate_blueprint(blueprint)
        else:
            simple_repairs = []

        validation = self.validator.validate(blueprint)
        _collect_issues(validation.issues)
        iteration = 0
        while not validation.valid and iteration < 2:
            blueprint, repair_retries, repair_notes = self.repair_engine.repair(
                blueprint,
                design,
                validation.issues,
            )
            retries += repair_retries
            repaired_actions.extend(repair_notes)
            validation = self.validator.validate(blueprint)
            _collect_issues(validation.issues)
            iteration += 1

        execution_ok, execution_issues = self.executor.simulate(blueprint)
        final_issues = list(validation.issues)
        for item in execution_issues:
            issue = ValidationIssue(
                code="EXECUTION_SIMULATION_FAILED",
                message=item,
                location="executor",
            )
            final_issues.append(issue)
            _collect_issues([issue])

        issue_messages = sorted({issue.message for issue in detected_issues.values()})
        all_issue_messages = sorted(set(simple_issues + unresolved_simple_issues + issue_messages))

        for message in unresolved_simple_issues:
            final_issues.append(
                ValidationIssue(
                    code="SIMPLE_VALIDATION_FAILED",
                    message=message,
                    location="simple_validator",
                )
            )

        return CompileResponse(
            valid=validation.valid and execution_ok and not unresolved_simple_issues,
            blueprint=blueprint,
            clarification_questions=[] if validation.valid else clarification_questions,
            assumptions=blueprint.assumptions,
            issues=all_issue_messages,
            issue_details=final_issues,
            repaired=sorted(set(repaired_actions)),
            retries=retries,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
