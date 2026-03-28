import logging
import os

from openai import OpenAI
from transformers import pipeline


logger = logging.getLogger("documind.llm")


class LLMService:
    """Uses OpenAI when available, otherwise falls back to a local Hugging Face model."""

    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.huggingface_model = os.getenv("HUGGINGFACE_MODEL", "google/flan-t5-base")

        if self.openai_api_key:
            self.provider_name = f"OpenAI ({self.openai_model})"
            self.client = OpenAI(api_key=self.openai_api_key)
            self.generator = None
            logger.info("Using OpenAI for answer generation")
        else:
            self.provider_name = f"HuggingFace ({self.huggingface_model})"
            self.client = None
            logger.info("Using Hugging Face fallback model: %s", self.huggingface_model)
            self.generator = pipeline(
                "text2text-generation",
                model=self.huggingface_model,
            )

    def answer_question(self, question: str, context: str) -> str:
        trimmed_context = self._trim_context(context)

        if self.client:
            return self._answer_with_openai(question=question, context=trimmed_context)
        return self._answer_with_huggingface(question=question, context=trimmed_context)

    def _answer_with_openai(self, question: str, context: str) -> str:
        prompt = self._build_prompt(question, context)
        response = self.client.responses.create(
            model=self.openai_model,
            input=prompt,
        )
        return response.output_text.strip()

    def _answer_with_huggingface(self, question: str, context: str) -> str:
        prompt = self._build_prompt(question, context)
        result = self.generator(
            prompt,
            max_new_tokens=180,
            do_sample=False,
        )
        return result[0]["generated_text"].strip()

    @staticmethod
    def _build_prompt(question: str, context: str) -> str:
        return (
            "You are a careful document assistant. Use only the provided context to answer. "
            "If the answer is not in the context, say you could not find it in the uploaded PDF.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}\n"
            "Answer:"
        )

    @staticmethod
    def _trim_context(context: str, max_characters: int = 12000) -> str:
        if len(context) <= max_characters:
            return context
        return context[:max_characters]
