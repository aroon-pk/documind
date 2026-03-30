import logging
import re
from dataclasses import dataclass
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


logger = logging.getLogger("documind.agent")
VALID_INTENTS = {"summary", "compare", "key_points", "document_locator", "fact_lookup"}


@dataclass
class AgentPlan:
    intent: str
    strategy: str
    primary_query: str
    fallback_query: str | None
    answer_instructions: str


class AgentState(TypedDict, total=False):
    question: str
    document_id: str | None
    plan: AgentPlan
    planner_mode: str
    steps: list[dict[str, str]]
    primary_sources: list[dict]
    refined_sources: list[dict]
    sources: list[dict]
    answer_result: dict


class AgentService:
    """LangGraph-powered planner-executor agent layered on top of the RAG pipeline."""

    def __init__(self, rag_service, llm_service=None):
        self.rag_service = rag_service
        self.llm_service = llm_service
        self.graph = self._build_graph()

    def ask(self, question: str, document_id: str | None = None) -> dict:
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("Question cannot be empty.")

        final_state = self.graph.invoke(
            {
                "question": clean_question,
                "document_id": document_id,
                "steps": [],
            }
        )
        plan = final_state["plan"]
        result = final_state["answer_result"]

        logger.info("LangGraph agent completed question using %s strategy", plan.strategy)
        return {
            **result,
            "agent": {
                "enabled": True,
                "intent": plan.intent,
                "strategy": plan.strategy,
                "planner_mode": final_state.get("planner_mode", "heuristic"),
                "steps": final_state.get("steps", []),
            },
        }

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("plan", self._plan_question)
        workflow.add_node("retrieve_primary", self._retrieve_primary)
        workflow.add_node("retrieve_refined", self._retrieve_refined)
        workflow.add_node("generate_answer", self._generate_answer)

        workflow.add_edge(START, "plan")
        workflow.add_edge("plan", "retrieve_primary")
        workflow.add_conditional_edges(
            "retrieve_primary",
            self._route_after_retrieval,
            {
                "retrieve_refined": "retrieve_refined",
                "generate_answer": "generate_answer",
            },
        )
        workflow.add_edge("retrieve_refined", "generate_answer")
        workflow.add_edge("generate_answer", END)
        return workflow.compile()

    def _plan_question(self, state: AgentState) -> AgentState:
        question = state["question"]
        document_id = state.get("document_id")
        llm_plan = None
        planner_mode = "heuristic"

        if self.llm_service:
            llm_plan = self.llm_service.plan_question(
                question=question,
                has_document_scope=bool(document_id),
            )

        if llm_plan:
            plan = self._coerce_plan(llm_plan, question, document_id)
            planner_mode = "langchain_structured"
        else:
            plan = self._build_heuristic_plan(question, document_id)

        steps = list(state.get("steps", []))
        steps.append(
            {
                "step": "Plan intent",
                "detail": (
                    f"Detected '{plan.intent}' intent and selected the '{plan.strategy}' strategy "
                    f"using the {planner_mode.replace('_', ' ')} planner."
                ),
            }
        )
        return {
            "plan": plan,
            "planner_mode": planner_mode,
            "steps": steps,
        }

    def _retrieve_primary(self, state: AgentState) -> AgentState:
        plan = state["plan"]
        document_id = state.get("document_id")
        sources = self.rag_service.retrieve_sources(
            question=plan.primary_query,
            document_id=document_id,
            limit=4,
        )
        if not sources:
            raise LookupError("No relevant content was found. Upload a PDF first.")

        steps = list(state.get("steps", []))
        steps.append(
            {
                "step": "Retrieve evidence",
                "detail": f"Ran the primary retrieval pass with the query: {plan.primary_query}",
            }
        )
        return {
            "primary_sources": sources,
            "sources": sources,
            "steps": steps,
        }

    def _route_after_retrieval(self, state: AgentState) -> Literal["retrieve_refined", "generate_answer"]:
        plan = state["plan"]
        primary_sources = state.get("primary_sources", [])
        if plan.fallback_query and self._should_refine(primary_sources, plan.intent):
            return "retrieve_refined"
        return "generate_answer"

    def _retrieve_refined(self, state: AgentState) -> AgentState:
        plan = state["plan"]
        document_id = state.get("document_id")
        primary_sources = state.get("primary_sources", [])
        refined_sources = self.rag_service.retrieve_sources(
            question=plan.fallback_query or state["question"],
            document_id=document_id,
            limit=4,
        )
        merged_sources = self.rag_service.merge_sources(primary_sources, refined_sources, limit=5)

        steps = list(state.get("steps", []))
        detail = (
            f"Ran a refinement pass with the fallback query: {plan.fallback_query}"
            if refined_sources
            else "Tried a refinement pass, but the secondary retrieval did not add stronger evidence."
        )
        steps.append(
            {
                "step": "Refine retrieval",
                "detail": detail,
            }
        )
        return {
            "refined_sources": refined_sources,
            "sources": merged_sources,
            "steps": steps,
        }

    def _generate_answer(self, state: AgentState) -> AgentState:
        plan = state["plan"]
        sources = state.get("sources") or state.get("primary_sources", [])
        result = self.rag_service.answer_with_sources(
            question=state["question"],
            sources=sources,
            answer_instructions=plan.answer_instructions,
        )

        steps = list(state.get("steps", []))
        steps.append(
            {
                "step": "Generate answer",
                "detail": "Produced a grounded answer from the merged evidence with inline source citations.",
            }
        )
        return {
            "answer_result": result,
            "steps": steps,
        }

    def _coerce_plan(self, llm_plan: dict, question: str, document_id: str | None) -> AgentPlan:
        fallback_plan = self._build_heuristic_plan(question, document_id)
        intent = str(llm_plan.get("intent") or fallback_plan.intent).strip().lower()
        if intent not in VALID_INTENTS:
            intent = fallback_plan.intent

        strategy = str(llm_plan.get("strategy") or fallback_plan.strategy).strip() or fallback_plan.strategy
        primary_query = str(llm_plan.get("primary_query") or question).strip() or question
        fallback_query = llm_plan.get("fallback_query")
        if fallback_query is not None:
            fallback_query = str(fallback_query).strip() or None
        answer_instructions = (
            str(llm_plan.get("answer_instructions") or fallback_plan.answer_instructions).strip()
            or fallback_plan.answer_instructions
        )

        return AgentPlan(
            intent=intent,
            strategy=strategy,
            primary_query=primary_query,
            fallback_query=fallback_query,
            answer_instructions=answer_instructions,
        )

    def _build_heuristic_plan(self, question: str, document_id: str | None) -> AgentPlan:
        lowered = question.lower()
        keywords = self._extract_keywords(question)
        keyword_phrase = " ".join(keywords[:8]) or question

        if any(term in lowered for term in ["compare", "difference", "different", "versus", "vs"]):
            return AgentPlan(
                intent="compare",
                strategy="comparison planner",
                primary_query=question,
                fallback_query=f"comparison similarities differences {keyword_phrase}",
                answer_instructions=(
                    "Answer as a comparison. Organize the response with clear comparison points, mention similarities or differences, "
                    "and cite supporting sources inline."
                ),
            )

        if any(term in lowered for term in ["summary", "summarize", "overview", "brief", "explain this"]):
            return AgentPlan(
                intent="summary",
                strategy="summarization planner",
                primary_query=question,
                fallback_query=f"summary overview main ideas {keyword_phrase}",
                answer_instructions=(
                    "Answer as a concise summary. Start with the main idea, then cover the most important supporting points, "
                    "using inline citations."
                ),
            )

        if any(term in lowered for term in ["key points", "main points", "takeaways", "highlights", "bullet"]):
            return AgentPlan(
                intent="key_points",
                strategy="takeaway extractor",
                primary_query=question,
                fallback_query=f"important points takeaways highlights {keyword_phrase}",
                answer_instructions=(
                    "Answer with short bullet points. Focus on the most important takeaways from the retrieved evidence and cite each point inline."
                ),
            )

        if document_id is None and any(term in lowered for term in ["which document", "which pdf", "where", "which file"]):
            return AgentPlan(
                intent="document_locator",
                strategy="document locator",
                primary_query=question,
                fallback_query=f"document file reference {keyword_phrase}",
                answer_instructions=(
                    "Answer by identifying which document or documents contain the relevant information, then explain the answer with citations."
                ),
            )

        return AgentPlan(
            intent="fact_lookup",
            strategy="targeted retrieval",
            primary_query=question,
            fallback_query=keyword_phrase if keyword_phrase.lower() != question.lower() else None,
            answer_instructions=(
                "Answer directly and accurately. Keep the answer concise, use only the retrieved evidence, and cite claims inline."
            ),
        )

    @staticmethod
    def _should_refine(sources: list[dict], intent: str) -> bool:
        if len(sources) < 2:
            return True

        top_distance = sources[0].get("distance", 0)
        if top_distance > 0.45:
            return True

        if intent == "compare":
            unique_documents = {source["document_id"] for source in sources}
            if len(unique_documents) < 2:
                return True

        return False

    @staticmethod
    def _extract_keywords(question: str) -> list[str]:
        stopwords = {
            "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "is", "it",
            "of", "on", "or", "the", "this", "to", "what", "which", "with", "about", "does",
        }
        tokens = re.findall(r"[a-zA-Z0-9]+", question.lower())
        keywords: list[str] = []
        for token in tokens:
            if token in stopwords or len(token) < 3:
                continue
            if token not in keywords:
                keywords.append(token)
        return keywords
