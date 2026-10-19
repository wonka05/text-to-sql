"""Talking to the language model.

The rest of the app depends only on the small `LLMClient` protocol, so the
tests use a scripted fake and never call a paid API, and swapping providers
means writing one class.

The model must answer with JSON matching REPLY_SCHEMA. Gemini enforces the
schema on its side (structured output), and `parse_reply` validates it again
here because a model reply is untrusted input like any other.
"""
import json
import logging
import re
from typing import Literal, Protocol

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from app.core.errors import ModelOutputError, ModelUnavailableError

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    model_name: str

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return the model's raw reply text."""
        ...


class ModelReply(BaseModel):
    kind: Literal["sql", "clarification", "unsupported"]
    sql: str = ""
    explanation: str = ""
    assumptions: list[str] = Field(default_factory=list)
    clarification_question: str = ""
    options: list[str] = Field(default_factory=list)


# Every field is required so the model always states each one explicitly;
# unused ones are empty. Field order is the order the model writes them in.
REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["sql", "clarification", "unsupported"],
            "description": "sql: answerable with one SELECT. clarification: too "
            "ambiguous to answer. unsupported: the data cannot answer it, or it "
            "asks to change data.",
        },
        "sql": {
            "type": "string",
            "description": "One MySQL 8 SELECT statement when kind is sql, else empty.",
        },
        "explanation": {
            "type": "string",
            "description": "One or two plain sentences: what the query computes, or "
            "why the question is unsupported.",
        },
        "assumptions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Interpretations you chose, e.g. how 'top' or a date range "
            "was defined. Empty if none.",
        },
        "clarification_question": {
            "type": "string",
            "description": "The question to ask the user when kind is clarification, else empty.",
        },
        "options": {
            "type": "array",
            "items": {"type": "string"},
            "description": "When kind is clarification: 2-4 complete rephrased "
            "questions the user could pick. Else empty.",
        },
    },
    "required": [
        "kind", "sql", "explanation", "assumptions", "clarification_question", "options",
    ],
}

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def parse_reply(raw: str) -> ModelReply:
    """Validate the model's reply, tolerating a markdown code fence around it."""
    text = (raw or "").strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        reply = ModelReply.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ModelOutputError("The AI model returned a reply in an unexpected format.") from exc

    if reply.kind == "sql" and not reply.sql.strip():
        raise ModelOutputError("The AI model said it wrote a query but returned none.")
    if reply.kind == "clarification" and not reply.clarification_question.strip():
        # Fall back to the explanation rather than showing an empty question
        reply.clarification_question = reply.explanation or "Could you be more specific?"
    reply.options = [o.strip() for o in reply.options if o.strip()][:4]
    reply.assumptions = [a.strip() for a in reply.assumptions if a.strip()][:5]
    return reply


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        httpx_client: httpx.Client | None = None,  # tests pass a mock transport
    ):
        self.model_name = model
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout_seconds * 1000),
                # One retry for rate limits (429) and server errors (5xx)
                retry_options=types.HttpRetryOptions(attempts=2, initial_delay=1.0, max_delay=4.0),
                httpx_client=httpx_client,
            ),
        )

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_json_schema=REPLY_SCHEMA,
            # No tools are passed, so the SDK's function-calling loop has nothing to do
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=config,
            )
        except genai_errors.APIError as exc:
            logger.error("Gemini API error %s: %s", exc.code, exc.message)
            if exc.code == 429:
                raise ModelUnavailableError(
                    "The AI model's rate limit or quota was reached. Try again in a minute."
                ) from exc
            raise ModelUnavailableError("The AI model is not available right now.") from exc
        except httpx.HTTPError as exc:
            logger.error("Gemini request failed: %r", exc)
            raise ModelUnavailableError("The AI model did not respond in time.") from exc

        text = response.text
        if not text:
            reason = None
            if response.candidates:
                reason = response.candidates[0].finish_reason
            logger.error("Gemini returned no text (finish reason: %s)", reason)
            raise ModelOutputError("The AI model returned an empty reply.")
        return text
