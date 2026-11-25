"""
executor.py – executes steps of a workflow instance using LLM capabilities.

Key fixes vs previous version:
- LLM is now lazy-loaded (property) instead of eager __init__ init, so importing
  this module does NOT trigger provider/credential checks at startup.
- Empty contract_text input is explicitly validated and fails the step cleanly.
- Missing output key after step logic now FAILS the step (was: silent warning,
  causing downstream steps to silently receive empty context strings).
- All LLM prompts are now jurisdiction-aware (Indian law primary).
"""
from __future__ import annotations

import logging
from typing import Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage
from llm.providers.factory import get_llm_provider
from .state import WorkflowInstance, WorkflowStep

logger = logging.getLogger(__name__)

# Shared Indian law system prefix injected into every executor prompt
_INDIAN_LAW_PREFIX = (
    "You are Harvey, an elite Indian legal AI assistant. "
    "Apply Indian law as your primary framework: Constitution of India, "
    "IPC / Bharatiya Nyaya Sanhita (BNS), CrPC / BNSS, CPC, Indian Evidence Act, "
    "Contract Act 1872, Companies Act 2013, SEBI Regulations, GST laws, IT Act 2000, "
    "Consumer Protection Act, Transfer of Property Act, and relevant Supreme Court of India "
    "and High Court judgments. Use Indian legal terminology throughout.\n\n"
)


class WorkflowExecutor:
    """
    Executes individual steps of a running legal workflow.
    """

    def __init__(self, provider_name: str | None = None) -> None:
        self.provider_name = provider_name
        self._model = None  # Lazy-loaded — NOT initialised in __init__

    @property
    def model(self):
        """Lazily initialise the LLM on first use (not at import/startup time)."""
        if self._model is None:
            self._model = get_llm_provider(self.provider_name).get_model()
        return self._model

    def execute_step(self, instance: WorkflowInstance, step: WorkflowStep) -> None:
        """
        Executes the logic for the given step using context variables,
        updates the step outputs, and saves them to the instance global_context.

        If a required input key is missing OR the step logic does not return an
        expected output key, the step is marked FAILED and the workflow aborts.
        Previously, a missing output key only logged a warning — causing silent
        empty-string context to flow into the next step.
        """
        logger.info(
            "Executing step '%s' (%s) for workflow %s",
            step.id, step.name, instance.workflow_id,
        )
        step.status = "running"
        instance.touch()

        # ── Gather inputs ─────────────────────────────────────────────────────
        inputs = {}
        for key in step.input_keys:
            if key in instance.global_context:
                inputs[key] = instance.global_context[key]
            else:
                step.status = "failed"
                step.error = f"Missing required input key: '{key}'"
                logger.error("Step '%s' failed: %s", step.id, step.error)
                instance.touch()
                return

        # ── Validate non-empty contract_text for the first step ───────────────
        if step.id == "extract_clauses":
            contract = inputs.get("contract_text", "")
            if not contract or not str(contract).strip():
                step.status = "failed"
                step.error = (
                    "Input 'contract_text' is empty. Please provide the contract text "
                    "before starting the workflow."
                )
                logger.error("Step '%s' failed: %s", step.id, step.error)
                instance.touch()
                return

        try:
            # ── Run step logic ─────────────────────────────────────────────────
            outputs = self._run_step_logic(step.id, inputs)

            # ── Propagate outputs — FAIL on missing key (not just warn) ────────
            step.outputs = outputs
            missing_keys = [k for k in step.output_keys if k not in outputs]
            if missing_keys:
                step.status = "failed"
                step.error = (
                    f"Step logic did not return expected output key(s): {missing_keys}. "
                    "Downstream steps would receive empty context."
                )
                logger.error("Step '%s' failed: %s", step.id, step.error)
                instance.touch()
                return

            step.status = "completed"
            for out_key in step.output_keys:
                instance.global_context[out_key] = outputs[out_key]
            logger.info("Step '%s' completed successfully.", step.id)

        except Exception as exc:
            step.status = "failed"
            step.error = str(exc)
            logger.error("Execution failed for step '%s': %s", step.id, step.error, exc_info=True)

        instance.touch()

    def _run_step_logic(self, step_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes LLM prompts based on step ID.
        All prompts are India-jurisdiction-aware.
        """
        if step_id == "extract_clauses":
            contract = inputs.get("contract_text", "")
            prompt = (
                _INDIAN_LAW_PREFIX
                + "Extract the main legal clauses from the following contract text. "
                "Focus on: Limitation of Liability, Indemnity, Governing Law, "
                "Jurisdiction (especially which Indian court has jurisdiction), "
                "Arbitration clause (under Arbitration and Conciliation Act 1996), "
                "Termination, Force Majeure, and Confidentiality. "
                "Provide a bulleted list with clause names and brief verbatim text snippets."
            )
            res = self._call_llm(prompt, contract)
            return {"extracted_clauses": res}

        elif step_id == "review_clauses":
            clauses = inputs.get("extracted_clauses", "")
            prompt = (
                _INDIAN_LAW_PREFIX
                + "Review the following extracted contract clauses under Indian law. "
                "Assess whether they favour one party over the other, violate mandatory "
                "provisions of Indian statutes (e.g., Contract Act 1872, Consumer Protection "
                "Act, SEBI Regulations), or deviate from standard Indian corporate legal norms. "
                "Highlight any clauses that would be unenforceable under Indian law."
            )
            res = self._call_llm(prompt, clauses)
            return {"clause_reviews": res}

        elif step_id == "find_risks":
            reviews = inputs.get("clause_reviews", "")
            prompt = (
                _INDIAN_LAW_PREFIX
                + "Based on the clause reviews below, identify all potential legal, financial, "
                "and operational risks under Indian law. "
                "Group them by severity (High, Medium, Low) and cite specific Indian statutes "
                "or Supreme Court/High Court precedents where relevant."
            )
            res = self._call_llm(prompt, reviews)
            return {"identified_risks": res}

        elif step_id == "draft_suggestions":
            risks = inputs.get("identified_risks", "")
            prompt = (
                _INDIAN_LAW_PREFIX
                + "Draft clear mitigation suggestions, redlines, or alternative clauses to address "
                "the legal risks identified below. Ensure suggestions comply with Indian statutes "
                "(Contract Act 1872, Companies Act 2013, Arbitration and Conciliation Act 1996, etc.). "
                "Use standard Indian contract drafting conventions."
            )
            res = self._call_llm(prompt, risks)
            return {"mitigation_suggestions": res}

        elif step_id == "generate_report":
            clauses = inputs.get("extracted_clauses", "")
            risks = inputs.get("identified_risks", "")
            suggestions = inputs.get("mitigation_suggestions", "")
            prompt = (
                _INDIAN_LAW_PREFIX
                + "Generate a consolidated Legal Risk & Mitigation Report under Indian law "
                "using the following information. Use professional legal formatting in markdown. "
                "Include: Executive Summary, Key Clauses, Identified Risks (with Indian law citations), "
                "Mitigation Suggestions, and Next Steps."
            )
            context = (
                f"--- EXTRACTED CLAUSES ---\n{clauses}\n\n"
                f"--- IDENTIFIED RISKS ---\n{risks}\n\n"
                f"--- SUGGESTIONS ---\n{suggestions}\n"
            )
            res = self._call_llm(prompt, context)
            return {"final_report": res}

        # ── Legal Research template steps ──────────────────────────────────────
        elif step_id == "define_research_questions":
            topic = inputs.get("research_topic", "")
            prompt = (
                _INDIAN_LAW_PREFIX
                + "You are given a legal research topic under Indian law. "
                "Break it down into 3–5 precise research questions that a legal researcher "
                "must answer, referencing specific Indian statutes, landmark Supreme Court cases, "
                "or regulatory frameworks where relevant."
            )
            res = self._call_llm(prompt, topic)
            return {"research_questions": res}

        elif step_id == "gather_sources":
            questions = inputs.get("research_questions", "")
            prompt = (
                _INDIAN_LAW_PREFIX
                + "For each research question below, identify the key Indian legal sources: "
                "statutes, central/state regulations, Supreme Court or High Court judgments, "
                "and authoritative commentary. List them with brief descriptions."
            )
            res = self._call_llm(prompt, questions)
            return {"gathered_sources": res}

        elif step_id == "synthesise_findings":
            sources = inputs.get("gathered_sources", "")
            questions = inputs.get("research_questions", "")
            prompt = (
                _INDIAN_LAW_PREFIX
                + "Synthesise the gathered legal sources into a coherent analysis that answers "
                "each research question. Cite Indian statutes and cases precisely."
            )
            context = f"Research Questions:\n{questions}\n\nSources:\n{sources}"
            res = self._call_llm(prompt, context)
            return {"synthesis": res}

        elif step_id == "generate_research_memo":
            synthesis = inputs.get("synthesis", "")
            topic = inputs.get("research_topic", "")
            prompt = (
                _INDIAN_LAW_PREFIX
                + "Format the following legal analysis as a professional Legal Research Memorandum "
                "in markdown. Include: Issue, Short Answer, Discussion (with Indian statute and case "
                "citations), and Conclusion. Follow standard Indian legal memo conventions."
            )
            context = f"Topic: {topic}\n\nAnalysis:\n{synthesis}"
            res = self._call_llm(prompt, context)
            return {"research_memo": res}

        # ── Compliance Check template steps ────────────────────────────────────
        elif step_id == "identify_applicable_laws":
            policy = inputs.get("policy_text", "")
            prompt = (
                _INDIAN_LAW_PREFIX
                + "Review the following policy or document and identify all Indian laws, "
                "regulations, and regulatory bodies that apply to it "
                "(e.g., SEBI, RBI, MCA, IT Act, DPDP Act 2023, GST Act, Labour Codes)."
            )
            res = self._call_llm(prompt, policy)
            return {"applicable_laws": res}

        elif step_id == "check_compliance":
            policy = inputs.get("policy_text", "")
            laws = inputs.get("applicable_laws", "")
            prompt = (
                _INDIAN_LAW_PREFIX
                + "For each applicable Indian law identified below, check whether the provided "
                "policy/document is compliant. List specific non-compliant clauses and the "
                "exact statutory provision they violate."
            )
            context = f"Policy:\n{policy}\n\nApplicable Laws:\n{laws}"
            res = self._call_llm(prompt, context)
            return {"compliance_gaps": res}

        elif step_id == "generate_compliance_report":
            gaps = inputs.get("compliance_gaps", "")
            laws = inputs.get("applicable_laws", "")
            prompt = (
                _INDIAN_LAW_PREFIX
                + "Generate a Compliance Gap Report in markdown format. "
                "For each gap, state: the violated Indian law/regulation, the specific clause, "
                "the risk severity (Critical/High/Medium/Low), and a recommended remediation action."
            )
            context = f"Applicable Laws:\n{laws}\n\nCompliance Gaps:\n{gaps}"
            res = self._call_llm(prompt, context)
            return {"compliance_report": res}

        else:
            raise ValueError(f"Unknown step ID: '{step_id}'")

    def _call_llm(self, system_instruction: str, user_content: str) -> str:
        messages = [
            SystemMessage(content=system_instruction),
            HumanMessage(content=user_content),
        ]
        return self.model.invoke(messages).content
