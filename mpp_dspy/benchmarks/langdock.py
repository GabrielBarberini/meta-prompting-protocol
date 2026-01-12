from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dspy.clients.base_lm import BaseLM

LANGDOCK_BASE_URL = "https://api.langdock.com/assistant/v1"
MAX_ASSISTANT_INSTRUCTIONS = 16384
RETRYABLE_STATUS_CODES = {408, 409, 429}


class LangdockAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LangdockForbiddenError(LangdockAPIError):
    pass


def _langdock_api_key() -> str:
    api_key = os.environ.get("LANGDOCK_API_KEY", "").strip()
    if not api_key:
        _load_dotenv(Path(".env"))
        api_key = os.environ.get("LANGDOCK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("LANGDOCK_API_KEY is not set.")
    return api_key


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ[key] = value


def _post(
    path: str,
    payload: dict[str, Any],
    *,
    retries: int = 3,
    base_delay: float = 1.0,
    timeout: float = 60.0,
) -> dict[str, Any]:
    url = f"{LANGDOCK_BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Authorization", f"Bearer {_langdock_api_key()}")
    request.add_header("Content-Type", "application/json")

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 403:
                raise LangdockForbiddenError(
                    f"HTTP {exc.code}: {detail}", status_code=exc.code
                ) from exc
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            if attempt < retries and (
                exc.code in RETRYABLE_STATUS_CODES or exc.code >= 500
            ):
                delay = base_delay * (2**attempt)
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        pass
                time.sleep(delay)
                continue
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < retries:
                time.sleep(base_delay * (2**attempt))
                continue
            raise RuntimeError(f"Network error: {exc}") from exc


def create_chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str,
    assistant_name: str,
    assistant_instructions: str,
    temperature: float | None = None,
    timeout: float | None = None,
    retries: int | None = None,
    base_delay: float | None = None,
    fallback_models: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "assistant": {
            "name": assistant_name,
            "instructions": assistant_instructions,
            "model": model,
        },
        "messages": messages,
    }
    if temperature is not None:
        payload["assistant"]["temperature"] = temperature
    models_to_try = _unique_models(model, fallback_models)
    last_error: LangdockForbiddenError | None = None
    for candidate in models_to_try:
        payload["assistant"]["model"] = candidate
        try:
            return _post(
                "/chat/completions",
                payload,
                retries=retries if retries is not None else 3,
                base_delay=base_delay if base_delay is not None else 1.0,
                timeout=timeout if timeout is not None else 60.0,
            )
        except LangdockForbiddenError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise LangdockAPIError("No models configured for request.")


@dataclass
class _LangdockMessage:
    content: str


@dataclass
class _LangdockChoice:
    message: _LangdockMessage
    logprobs: Any = None


@dataclass
class _LangdockResponse:
    choices: list[_LangdockChoice]
    model: str
    usage: dict[str, int]
    _hidden_params: dict[str, Any] = field(default_factory=dict)


class LangdockLM(BaseLM):
    def __init__(
        self,
        *,
        model: str,
        assistant_name: str = "mpp-benchmark",
        assistant_instructions: str = "You are a helpful assistant.",
        timeout: float | None = None,
        retries: int | None = None,
        base_delay: float | None = None,
        fallback_models: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model=model, model_type="chat", **kwargs)
        self.assistant_name = assistant_name
        self.assistant_instructions = assistant_instructions
        self.request_timeout = timeout
        self.request_retries = retries
        self.request_base_delay = base_delay
        self.fallback_models = [str(item) for item in (fallback_models or []) if item]

    def forward(
        self,
        prompt: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> _LangdockResponse:
        instructions = self.assistant_instructions
        if messages is None:
            prompt_text = prompt or ""
            messages = [{"role": "user", "content": prompt_text}]
        else:
            messages, instructions = _normalize_messages(messages, instructions)

        temperature = kwargs.get("temperature", getattr(self, "temperature", None))
        timeout = kwargs.get("timeout", self.request_timeout)
        retries = kwargs.get("retries", self.request_retries)
        base_delay = kwargs.get("base_delay", self.request_base_delay)
        response = create_chat_completion(
            messages,
            model=self.model,
            assistant_name=self.assistant_name,
            assistant_instructions=instructions,
            temperature=temperature,
            timeout=timeout,
            retries=retries,
            base_delay=base_delay,
            fallback_models=self.fallback_models,
        )
        content = _assistant_text(response)
        usage = response.get("usage", {}) if isinstance(response, dict) else {}
        if not isinstance(usage, dict):
            usage = {}
        usage.setdefault("prompt_tokens", 0)
        usage.setdefault("completion_tokens", 0)
        usage.setdefault("total_tokens", 0)
        model = (
            response.get("model", self.model)
            if isinstance(response, dict)
            else self.model
        )
        if isinstance(model, str) and model:
            self.model = model
        return _LangdockResponse(
            choices=[_LangdockChoice(message=_LangdockMessage(content=content))],
            model=model,
            usage=usage,
        )


def _assistant_text(response: Any) -> str:
    if isinstance(response, dict):
        if "choices" in response:
            choices = response.get("choices")
            if isinstance(choices, list) and choices:
                choice = choices[0]
                if isinstance(choice, dict):
                    message = choice.get("message")
                    if isinstance(message, dict) and "content" in message:
                        return _message_content_to_text(message["content"])
                    if "text" in choice:
                        return _message_content_to_text(choice["text"])
                else:
                    message = getattr(choice, "message", None)
                    if message is not None and hasattr(message, "content"):
                        return _message_content_to_text(message.content)
        if "data" in response:
            return _assistant_text(response.get("data"))
        if "result" in response:
            return _assistant_text(response.get("result"))
        message = response.get("message")
        if isinstance(message, dict) and "content" in message:
            return _message_content_to_text(message["content"])
        if "content" in response:
            return _message_content_to_text(response["content"])
    if isinstance(response, list) and response:
        return _assistant_text(response[0])
    raise ValueError(
        "Unexpected Langdock response shape; keys="
        f"{list(response.keys()) if isinstance(response, dict) else type(response)}"
    )


def _normalize_messages(
    messages: list[dict[str, Any]],
    assistant_instructions: str,
) -> tuple[list[dict[str, Any]], str]:
    normalized: list[dict[str, Any]] = []
    system_parts: list[str] = []

    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "")).strip()
        content = message.get("content")
        if role in {"system", "developer"} or role not in {"user", "assistant", "tool"}:
            system_parts.append(_message_content_to_text(content))
            continue
        if role == "tool":
            if isinstance(content, list):
                tool_content = content
            else:
                tool_content = [
                    {"type": "text", "text": _message_content_to_text(content)}
                ]
            normalized.append({"role": "tool", "content": tool_content})
        else:
            normalized.append(
                {"role": role, "content": _message_content_to_text(content)}
            )

    if system_parts:
        system_text = "\n".join(part for part in system_parts if part)
        if system_text:
            merged = (
                f"{assistant_instructions}\n\n{system_text}"
                if assistant_instructions
                else system_text
            )
            if len(merged) <= MAX_ASSISTANT_INSTRUCTIONS:
                assistant_instructions = merged
            else:
                if len(assistant_instructions) > MAX_ASSISTANT_INSTRUCTIONS:
                    assistant_instructions = assistant_instructions[
                        :MAX_ASSISTANT_INSTRUCTIONS
                    ]
                normalized.insert(
                    0,
                    {
                        "role": "user",
                        "content": f"System context:\n{system_text}",
                    },
                )

    return normalized, assistant_instructions


def _unique_models(primary: str, fallbacks: list[str] | None) -> list[str]:
    seen: set[str] = set()
    models: list[str] = []
    for item in [primary, *(fallbacks or [])]:
        if not item:
            continue
        candidate = str(item).strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        models.append(candidate)
    return models


def _message_content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and "text" in item:
                    parts.append(str(item["text"]))
                elif "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(json.dumps(item, ensure_ascii=True))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content)
