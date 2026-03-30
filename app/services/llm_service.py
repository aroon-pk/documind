import logging
import os
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_huggingface import HuggingFacePipeline
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from transformers import pipeline


logger = logging.getLogger("documind.llm")


class QuestionPlan(BaseModel):
    """Structured planning schema used by the LangChain planner."""

    intent: str = Field(description="One of: summary, compare, key_points, document_locator, fact_lookup")
    strategy: str = Field(description="Short name for the retrieval strategy")
    primary_query: str = Field(description="The main retrieval query to run first")
    fallback_query: str | None = Field(default=None, description="An optional refinement query if the first retrieval pass is weak")
    answer_instructions: str = Field(description="Instructions for the final answer style")


class LLMService:
    """Uses LangChain model wrappers for planning and answer generation."""

    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.huggingface_model = os.getenv("HUGGINGFACE_MODEL", "google/flan-t5-base")

        self.chat_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a careful document assistant. Use only the provided context to answer. "
                    "If the answer is not in the context, say you could not find it in the uploaded PDF.",
                ),
                (
                    "human",
                    "Guidance:\n{guidance}\n\nContext:\n{context}\n\nQuestion: {question}\nAnswer:",
                ),
            ]
        )
        self.planner_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are the planner for a PDF question-answering agent. "
                    "Choose exactly one intent from summary, compare, key_points, document_locator, or fact_lookup. "
                    "Return retrieval-friendly queries and answer instructions that keep the final answer grounded in sources.",
                ),
                (
                    "human",
                    "Question: {question}\n"
                    "Document scope: {scope_hint}\n"
                    "If the user asks which document contains the answer and the scope is multi-document, prefer document_locator."
                    " If the user asks for takeaways or highlights, prefer key_points."
                    " If the user asks for similarities or differences, prefer compare."
                    " If the user asks for an overview or summary, prefer summary."
                    " Otherwise prefer fact_lookup.",
                ),
            ]
        )
        self.text_prompt = PromptTemplate.from_template(
            "You are a careful document assistant. Use only the provided context to answer. "
            "If the answer is not in the context, say you could not find it in the uploaded PDF.\n\n"
            "Guidance:\n{guidance}\n\n"
            "Context:\n{context}\n\n"
            "Question: {question}\n"
            "Answer:"
        )

        if self.openai_api_key:
            self.provider_name = f"OpenAI ({self.openai_model})"
            self.chat_model = ChatOpenAI(
                model=self.openai_model,
                api_key=self.openai_api_key,
                temperature=0,
            )
            self.answer_chain = self.chat_prompt | self.chat_model
            self.planner_chain = self.planner_prompt | self.chat_model.with_structured_output(QuestionPlan)
            self.text_model = None
            logger.info("Using LangChain ChatOpenAI for planning and answer generation")
        else:
            self.provider_name = f"HuggingFace ({self.huggingface_model})"
            self.chat_model = None
            self.answer_chain = None
            self.planner_chain = None
            logger.info("Using LangChain HuggingFace fallback model: %s", self.huggingface_model)
            generation_pipeline = pipeline(
                "text2text-generation",
                model=self.huggingface_model,
            )
            self.text_model = HuggingFacePipeline(pipeline=generation_pipeline)

    def plan_question(self, question: str, has_document_scope: bool) -> dict[str, Any] | None:
        if not self.planner_chain:
            return None

        try:
            plan = self.planner_chain.invoke(
                {
                    "question": question,
                    "scope_hint": "single_document" if has_document_scope else "multi_document",
                }
            )
            return plan.model_dump()
        except Exception:
            logger.warning("LLM planner failed; falling back to heuristic planning", exc_info=True)
            return None

    def answer_question(self, question: str, context: str, instructions: str | None = None) -> str:
        trimmed_context = self._trim_context(context)
        guidance = instructions or (
            "Answer directly and clearly. Use only the provided context, and cite evidence inline using labels like [Source 1]."
        )

        if self.answer_chain:
            response = self.answer_chain.invoke(
                {
                    "question": question,
                    "context": trimmed_context,
                    "guidance": guidance,
                }
            )
            return self._normalize_content(response.content)

        prompt = self.text_prompt.format(
            question=question,
            context=trimmed_context,
            guidance=guidance,
        )
        response = self.text_model.invoke(prompt)
        return self._normalize_content(response)

    @staticmethod
    def _normalize_content(content: Any) -> str:
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item.strip())
                    continue
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content") or ""
                    if text:
                        parts.append(str(text).strip())
            return "\n".join(part for part in parts if part).strip()

        return str(content).strip()

    @staticmethod
    def _trim_context(context: str, max_characters: int = 12000) -> str:
        if len(context) <= max_characters:
            return context
        return context[:max_characters]
