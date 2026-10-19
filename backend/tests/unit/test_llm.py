import json

import httpx
import pytest
from google.genai import errors as genai_errors

from app.core.errors import ModelOutputError, ModelUnavailableError
from app.services.llm import REPLY_SCHEMA, GeminiClient, parse_reply


class TestParseReply:
    def test_valid_sql_reply(self):
        reply = parse_reply(json.dumps({
            "kind": "sql", "sql": "SELECT 1", "explanation": "One.",
            "assumptions": ["x"], "clarification_question": "", "options": [],
        }))
        assert reply.kind == "sql" and reply.sql == "SELECT 1" and reply.assumptions == ["x"]

    def test_tolerates_a_markdown_fence(self):
        raw = '```json\n{"kind": "unsupported", "explanation": "No weather data."}\n```'
        assert parse_reply(raw).kind == "unsupported"

    @pytest.mark.parametrize("raw", [
        "", "not json", "[]", '{"kind": "delete"}', '{"sql": "SELECT 1"}',
        '{"kind": "sql", "sql": "   "}',
    ])
    def test_rejects_malformed_replies(self, raw):
        with pytest.raises(ModelOutputError):
            parse_reply(raw)

    def test_clarification_without_question_falls_back_to_explanation(self):
        reply = parse_reply('{"kind": "clarification", "explanation": "Top by what?"}')
        assert reply.clarification_question == "Top by what?"

    def test_trims_options_and_assumptions(self):
        reply = parse_reply(json.dumps({
            "kind": "clarification", "clarification_question": "Which?",
            "options": ["a", " ", "b", "c", "d", "e"], "assumptions": [],
        }))
        assert reply.options == ["a", "b", "c", "d"]


class StubModels:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class StubResponse:
    def __init__(self, text, candidates=None):
        self.text = text
        self.candidates = candidates


def client_with(models: StubModels) -> GeminiClient:
    client = GeminiClient(api_key="k", model="gemini-test", timeout_seconds=5)
    client._client = type("C", (), {"models": models})()
    return client


class TestGeminiClient:
    def test_requests_json_matching_the_schema(self):
        models = StubModels(StubResponse('{"kind": "unsupported"}'))
        assert client_with(models).generate("system", "user") == '{"kind": "unsupported"}'

        call = models.calls[0]
        assert call["model"] == "gemini-test"
        assert call["contents"] == "user"
        assert call["config"].system_instruction == "system"
        assert call["config"].response_mime_type == "application/json"
        assert call["config"].response_json_schema == REPLY_SCHEMA

    def test_quota_errors_get_a_specific_message(self):
        error = genai_errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
        with pytest.raises(ModelUnavailableError, match="quota"):
            client_with(StubModels(error=error)).generate("s", "u")

    def test_server_errors_become_model_unavailable(self):
        error = genai_errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}})
        with pytest.raises(ModelUnavailableError, match="not available"):
            client_with(StubModels(error=error)).generate("s", "u")

    def test_timeouts_become_model_unavailable(self):
        with pytest.raises(ModelUnavailableError, match="in time"):
            client_with(StubModels(error=httpx.ReadTimeout("slow"))).generate("s", "u")

    def test_empty_reply_is_an_output_error(self):
        with pytest.raises(ModelOutputError):
            client_with(StubModels(StubResponse(None))).generate("s", "u")


class TestGeminiWireFormat:
    """Runs the real SDK against a mock HTTP transport: no network, no cost."""

    def client(self, responses):
        self.requests = []

        def handler(request: httpx.Request):
            self.requests.append(request)
            status, body = responses.pop(0)
            return httpx.Response(status, json=body)

        transport = httpx.Client(transport=httpx.MockTransport(handler))
        return GeminiClient("key", "gemini-test", timeout_seconds=5, httpx_client=transport)

    def test_request_body_and_reply_text(self):
        reply = '{"kind": "unsupported", "explanation": "No weather data."}'
        ok = {"candidates": [{"content": {"role": "model", "parts": [{"text": reply}]},
                              "finishReason": "STOP"}]}
        assert self.client([(200, ok)]).generate("system", "question") == reply

        request = self.requests[0]
        assert request.url.path.endswith("/models/gemini-test:generateContent")
        body = json.loads(request.content)
        assert body["systemInstruction"]["parts"][0]["text"] == "system"
        assert body["contents"][0]["parts"][0]["text"] == "question"
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["generationConfig"]["responseJsonSchema"] == REPLY_SCHEMA

    def test_bad_request_is_not_retried(self):
        error = {"error": {"code": 400, "message": "API key not valid", "status": "INVALID_ARGUMENT"}}
        with pytest.raises(ModelUnavailableError):
            self.client([(400, error)]).generate("s", "u")
        assert len(self.requests) == 1

    def test_rate_limit_is_retried_once_then_reported(self):
        error = {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
        with pytest.raises(ModelUnavailableError, match="quota"):
            self.client([(429, error), (429, error)]).generate("s", "u")
        assert len(self.requests) == 2
