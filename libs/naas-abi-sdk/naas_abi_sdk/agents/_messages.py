"""Message helpers shared verbatim with naas_abi_core's Agent.

Copied, not reimplemented: tests/agent_parity holds both agents to the same
behaviour, so change these together with naas_abi_core/services/agent/Agent.py.
Office (slides/documents) specific branches of the core error mapping are left
out: those turns are a Nexus concern that never runs in an SDK module.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, ClassVar, cast

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    ToolCall,
    ToolMessage,
)

logger = logging.getLogger("naas_abi_sdk.agents")


def validate_name(name: str) -> str:
    """Graph-node-safe name, same rule as core ``Agent.validate_name``."""
    pattern = r"^[a-zA-Z0-9_-]+$"
    if not re.match(pattern, name):
        valid_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        return valid_name.replace("__", "_")
    return name


def friendly_model_invoke_error(exc: BaseException) -> str:
    """One-line human error. Never dump raw provider JSON into the chat bubble."""
    text = str(exc or "").strip()
    lowered = text.lower()
    if "recursion limit" in lowered:
        return (
            "The agent hit its step limit before finishing. "
            "Try a smaller request, or continue from what already landed."
        )
    if (
        "429" in text
        or "rate-limited" in lowered
        or "rate limited" in lowered
        or "temporarily rate-limited" in lowered
    ):
        return "This model is rate limited. Pick another model in the agent menu and try again."
    if (
        "contextwindowexceeded" in lowered.replace(" ", "")
        or "context window" in lowered
        or "maximum context length" in lowered
    ):
        return (
            "This request exceeded the model's context window. "
            "Do not load whole files with embedded images, then try again."
        )
    if "timed out" in lowered or "timeouterror" in lowered.replace(" ", ""):
        return "The model timed out. Try a smaller request."
    if (
        "error code:" in lowered
        or "provider returned error" in lowered
        or (len(text) > 160 and ("{" in text or "'error'" in text or '"error"' in text))
    ):
        return "The model provider failed. Pick another model and try again."
    return text or "The model provider failed. Pick another model and try again."


_MAX_TOOL_RESULT_CHARS = 8_000
_OLD_TOOL_RESULT_STUB = (
    "[Old tool result cleared. Call the tool again if you need the full content.]"
)


def _tool_message_name(message: ToolMessage) -> str:
    name = getattr(message, "name", None)
    return name if isinstance(name, str) else ""


def _tool_content_chars(content: Any) -> int:
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content)
    if isinstance(content, (list, tuple)):
        return sum(_tool_content_chars(part) for part in content)
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return len(text)
        return len(json.dumps(content, default=str))
    return len(str(content))


def _truncate_tool_content(content: Any, max_chars: int) -> Any:
    if isinstance(content, str):
        if len(content) <= max_chars:
            return content
        return content[:max_chars] + "\n...[truncated]..."
    if _tool_content_chars(content) <= max_chars:
        return content
    return _OLD_TOOL_RESULT_STUB


def _copy_tool_message(message: ToolMessage, content: Any) -> ToolMessage:
    kwargs: dict[str, Any] = {
        "content": content,
        "tool_call_id": message.tool_call_id,
    }
    name = getattr(message, "name", None)
    if name is not None:
        kwargs["name"] = name
    mid = getattr(message, "id", None)
    if mid is not None:
        kwargs["id"] = mid
    extra = getattr(message, "additional_kwargs", None)
    if extra:
        kwargs["additional_kwargs"] = dict(extra)
    return ToolMessage(**kwargs)


def compact_old_tool_messages(messages: list[AnyMessage]) -> list[AnyMessage]:
    """Stub prior-turn ToolMessages; keep last list + last write; cap current-turn size.

    ``transfer_to_*`` results stay as-is (handoff pairing). The last ``list_*``
    and last ``write_*`` / ``replace_in_*`` stay so the model still sees the
    current outline and the last successful write. Those two, and any current-
    turn result, are truncated if they exceed ``_MAX_TOOL_RESULT_CHARS``.
    """
    if not messages:
        return messages

    last_human = -1
    last_list = -1
    last_write = -1
    for i, message in enumerate(messages):
        if isinstance(message, HumanMessage):
            last_human = i
        elif isinstance(message, ToolMessage):
            name = _tool_message_name(message)
            if name.startswith("transfer_to_"):
                continue
            if name.startswith("list_"):
                last_list = i
            elif name.startswith(("write_", "replace_in_")):
                last_write = i

    changed = False
    out: list[AnyMessage] = []
    for i, message in enumerate(messages):
        if not isinstance(message, ToolMessage):
            out.append(message)
            continue
        name = _tool_message_name(message)
        if name.startswith("transfer_to_"):
            out.append(message)
            continue
        keep_identity = i == last_list or i == last_write
        current_turn = i > last_human
        chars = _tool_content_chars(message.content)
        if keep_identity or current_turn:
            if chars <= _MAX_TOOL_RESULT_CHARS:
                out.append(message)
                continue
            out.append(
                _copy_tool_message(
                    message,
                    _truncate_tool_content(message.content, _MAX_TOOL_RESULT_CHARS),
                )
            )
            changed = True
            continue
        if chars == 0 or message.content == _OLD_TOOL_RESULT_STUB:
            out.append(message)
            continue
        out.append(_copy_tool_message(message, _OLD_TOOL_RESULT_STUB))
        changed = True
    return out if changed else messages


class ToolCallRepair:
    """Content helpers and tool-call repair, from core ``Agent`` static methods."""

    @staticmethod
    def _content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        parts.append(text)
                        continue
                    reasoning = item.get("reasoning_content")
                    if isinstance(reasoning, dict):
                        reasoning_text = reasoning.get("text")
                        if isinstance(reasoning_text, str) and reasoning_text:
                            continue
                    content_text = item.get("content")
                    if isinstance(content_text, str) and content_text:
                        parts.append(content_text)
                        continue
                elif isinstance(item, str) and item:
                    parts.append(item)
            if parts:
                return "\n".join(parts)
            return ""
        return str(content)

    @staticmethod
    def _ai_content_effectively_empty(content: Any) -> bool:
        """True when an assistant reply has no user-visible text."""
        if not content:
            return True
        if isinstance(content, str):
            return not content.strip()
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type")
                    if btype == "text" and (block.get("text") or "").strip():
                        return False
                    if btype == "tool_use":
                        return False
                elif isinstance(block, str) and block.strip():
                    return False
            return True
        return False

    @staticmethod
    def _has_tool_calls(message: AnyMessage) -> bool:
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            return True
        return bool(
            (getattr(message, "additional_kwargs", None) or {}).get("tool_calls")
        )

    @staticmethod
    def _drop_empty_tool_arg_keys(args: dict[str, Any]) -> dict[str, Any]:
        """Drop empty-string keys that Amazon Bedrock Document types reject.

        ``gpt-oss`` models on Bedrock emit ``{"": {}}`` for zero-argument tools.
        That is still a JSON object, so a type-only check lets it through, but
        Converse then raises ValidationException on ``toolUse.input``. Return the
        same dict when nothing is dropped so callers can detect no-op by identity.
        """
        if "" not in args:
            return args
        logger.warning(
            "Dropping empty-string key(s) from tool-call args; Bedrock rejects them"
        )
        return {k: v for k, v in args.items() if k != ""}

    @staticmethod
    def _coerce_tool_args_to_object(args: Any) -> dict[str, Any]:
        """Ensure tool-call args are a JSON object (``dict``).

        Providers such as Amazon Bedrock Converse reject ``toolUse.input`` unless
        it is a JSON object. Some models (notably OpenAI OSS models on Bedrock)
        emit empty lists, empty strings, ``None``, JSON-encoded strings, or
        ``{"": {}}`` for zero-argument tools. Coerce those shapes so any default
        chat model can safely continue a tool-calling turn.
        """
        if args is None:
            return {}
        if isinstance(args, dict):
            return ToolCallRepair._drop_empty_tool_arg_keys(args)
        if isinstance(args, str):
            text = args.strip()
            if not text:
                return {}
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                logger.warning(
                    "Discarding non-JSON tool-call args string; coercing to {}"
                )
                return {}
            if isinstance(parsed, dict):
                return ToolCallRepair._drop_empty_tool_arg_keys(parsed)
            logger.warning(
                "Tool-call args JSON is not an object (%s); coercing to {}",
                type(parsed).__name__,
            )
            return {}
        if isinstance(args, (list, tuple)):
            # boto3 Document decoding historically turns ``{}`` into ``[]``.
            if len(args) == 0:
                return {}
            if len(args) == 1 and isinstance(args[0], dict):
                return ToolCallRepair._drop_empty_tool_arg_keys(args[0])
            # A multi-element list (or a single non-dict element) cannot be a JSON
            # object; there is no lossless coercion, so surface the drop.
            logger.warning(
                "Discarding non-object tool-call args list of length %d; coercing to {}",
                len(args),
            )
            return {}
        logger.warning(
            "Discarding unsupported tool-call args of type %s; coercing to {}",
            type(args).__name__,
        )
        return {}

    @staticmethod
    def _is_json_object_string(text: str) -> bool:
        """Return True when ``text`` already encodes a JSON object (``dict``)."""
        stripped = text.strip()
        if not stripped:
            return False
        try:
            return isinstance(json.loads(stripped), dict)
        except json.JSONDecodeError:
            return False

    @classmethod
    def _coerce_object_at_key(
        cls, container: dict[str, Any], key: str
    ) -> tuple[dict[str, Any], bool]:
        """Coerce ``container[key]`` to a JSON object, returning ``(new, changed)``.

        Shared primitive for every tool-input shape (LangChain ``tool_calls``,
        ``tool_use``/``toolUse`` content blocks, and raw ``args``). When ``key`` is
        absent the container is returned unchanged — we never inject a key the
        provider omitted. When present but already an object the same object is
        returned so callers can detect "no change" by identity.
        """
        if key not in container:
            return container, False
        current = container[key]
        coerced = cls._coerce_tool_args_to_object(current)
        if coerced is current:
            return container, False
        return {**container, key: coerced}, True

    _TEXT_TOOL_NAME_ALIASES: ClassVar[dict[str, str]] = {
        "documents_agent": "transfer_to_Documents",
        "documentsagent": "transfer_to_Documents",
        "documents": "transfer_to_Documents",
        "slides_agent": "transfer_to_Slides",
        "slidesagent": "transfer_to_Slides",
        "slides": "transfer_to_Slides",
    }

    @staticmethod
    def _resolve_text_tool_name(tag_name: str | None, json_name: str | None) -> str:
        """Pick the executable tool name from Qwen/Hermes markup.

        Qwen often writes ``[tool_call: transfer_to_Documents]`` and then a JSON
        body whose ``name`` is a hallucinated id such as ``documents_agent``.
        The tag is the one that matches a bound handoff tool.
        """
        raw = (tag_name or "").strip() or (json_name or "").strip()
        if not raw:
            return ""
        if raw.startswith("transfer_to_"):
            return validate_name(raw)
        key = raw.lower().replace("-", "_").replace(" ", "_")
        alias = ToolCallRepair._TEXT_TOOL_NAME_ALIASES.get(key)
        if alias:
            return alias
        return validate_name(raw)

    @classmethod
    def _payload_to_tool_call(
        cls, tag_name: str | None, payload: dict[str, Any], call_id: str
    ) -> ToolCall | None:
        json_name = payload.get("name")
        if isinstance(json_name, dict):
            json_name = json_name.get("name")
        if not isinstance(json_name, str):
            json_name = None
        name = cls._resolve_text_tool_name(tag_name, json_name)
        if not name:
            return None
        if "arguments" in payload:
            args = payload.get("arguments")
        elif "args" in payload:
            args = payload.get("args")
        elif "parameters" in payload:
            args = payload.get("parameters")
        else:
            args = {k: v for k, v in payload.items() if k not in {"name", "function"}}
        return {
            "name": name,
            "args": cls._coerce_tool_args_to_object(args),
            "id": call_id,
            "type": "tool_call",
        }

    @staticmethod
    def _read_json_object_at(
        text: str, start: int
    ) -> tuple[dict[str, Any] | None, int]:
        index = start
        length = len(text)
        while index < length and text[index].isspace():
            index += 1
        if index >= length or text[index] != "{":
            return None, start
        try:
            parsed, end = json.JSONDecoder().raw_decode(text, index)
        except json.JSONDecodeError:
            return None, start
        if not isinstance(parsed, dict):
            return None, start
        return parsed, end

    @classmethod
    def _extract_text_tool_calls(cls, text: str) -> tuple[list[ToolCall], str]:
        """Lift ``[tool_call:]`` / ``<tool_call>`` markup into LangChain tool_calls.

        Qwen-3.x via an OpenAI-compatible gateway often keeps native tool
        calling for a default tool, then writes the real handoff as chat text.
        Without this, the markup is stored as the assistant paragraph and the
        transfer never runs.
        """
        if not text or (
            "[tool_call" not in text.lower() and "<tool_call" not in text.lower()
        ):
            return [], text

        extracted: list[ToolCall] = []
        spans: list[tuple[int, int]] = []
        lower = text.lower()
        cursor = 0
        while cursor < len(text):
            tag_name: str | None = None
            bracket = lower.find("[tool_call:", cursor)
            xml = lower.find("<tool_call>", cursor)
            if bracket == -1 and xml == -1:
                break
            if xml == -1 or (bracket != -1 and bracket < xml):
                name_start = bracket + len("[tool_call:")
                name_end = text.find("]", name_start)
                if name_end == -1:
                    break
                tag_name = text[name_start:name_end].strip()
                payload, payload_end = cls._read_json_object_at(text, name_end + 1)
                close = lower.find("[/tool_call]", payload_end)
                if payload is None or close == -1:
                    cursor = name_end + 1
                    continue
                call = cls._payload_to_tool_call(
                    tag_name, payload, f"call_{uuid.uuid4().hex[:12]}"
                )
                if call is not None:
                    extracted.append(call)
                    spans.append((bracket, close + len("[/tool_call]")))
                cursor = close + len("[/tool_call]")
                continue

            body_start = xml + len("<tool_call>")
            payload, payload_end = cls._read_json_object_at(text, body_start)
            if payload is None:
                line_end = text.find("\n", body_start)
                close_early = lower.find("</tool_call>", body_start)
                token_end = line_end if line_end != -1 else close_early
                if token_end != -1:
                    maybe_name = text[body_start:token_end].strip()
                    if maybe_name and "{" not in maybe_name:
                        tag_name = maybe_name
                        payload, payload_end = cls._read_json_object_at(
                            text, token_end + 1
                        )
            close = lower.find("</tool_call>", payload_end)
            if payload is None or close == -1:
                cursor = body_start
                continue
            call = cls._payload_to_tool_call(
                tag_name, payload, f"call_{uuid.uuid4().hex[:12]}"
            )
            if call is not None:
                extracted.append(call)
                spans.append((xml, close + len("</tool_call>")))
            cursor = close + len("</tool_call>")

        if not extracted:
            return [], text

        cleaned = text
        for start, end in reversed(spans):
            cleaned = cleaned[:start] + cleaned[end:]
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return extracted, cleaned

    @classmethod
    def _strip_text_tool_markup_from_content(
        cls, content: Any, cleaned_text: str
    ) -> Any:
        if isinstance(content, str):
            return cleaned_text
        if not isinstance(content, list):
            return content
        new_blocks: list[Any] = []
        for block in content:
            if isinstance(block, str):
                stripped = cls._extract_text_tool_calls(block)[1]
                if stripped.strip():
                    new_blocks.append(stripped)
                continue
            if isinstance(block, dict) and block.get("type") == "text":
                raw = block.get("text")
                if isinstance(raw, str):
                    stripped = cls._extract_text_tool_calls(raw)[1]
                    if stripped.strip():
                        new_blocks.append({**block, "text": stripped})
                    continue
            new_blocks.append(block)
        return new_blocks if new_blocks else ""

    @classmethod
    def _promote_text_tool_calls(cls, message: AIMessage) -> AIMessage:
        """Turn Qwen/Hermes tool markup in content into ``tool_calls``."""
        text = cls._content_to_text(message.content)
        extracted, cleaned = cls._extract_text_tool_calls(text)
        if not extracted and cleaned == text:
            return message

        existing = list(getattr(message, "tool_calls", None) or [])
        seen: set[tuple[str, str]] = set()
        merged: list[ToolCall] = []
        for call in existing:
            if not isinstance(call, dict):
                merged.append(cast(ToolCall, call))
                continue
            key = (
                str(call.get("name") or ""),
                json.dumps(call.get("args") or {}, sort_keys=True, default=str),
            )
            seen.add(key)
            merged.append(cast(ToolCall, call))
        for call in extracted:
            key = (
                str(call.get("name") or ""),
                json.dumps(call.get("args") or {}, sort_keys=True, default=str),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(call)

        content_changed = cleaned != text
        content = (
            cls._strip_text_tool_markup_from_content(message.content, cleaned)
            if content_changed
            else message.content
        )
        if merged == existing and content is message.content:
            return message
        return AIMessage(
            content=content,
            tool_calls=merged,
            invalid_tool_calls=list(getattr(message, "invalid_tool_calls", None) or []),
            id=message.id,
            additional_kwargs=dict(getattr(message, "additional_kwargs", None) or {}),
            response_metadata=dict(getattr(message, "response_metadata", None) or {}),
            usage_metadata=getattr(message, "usage_metadata", None),
            name=getattr(message, "name", None),
            example=getattr(message, "example", False),
        )

    @classmethod
    def _normalize_ai_message_tool_inputs(cls, message: AIMessage) -> AIMessage:
        """Rewrite an AIMessage so every tool input is a dict object."""
        message = cls._promote_text_tool_calls(message)
        tool_calls = list(getattr(message, "tool_calls", None) or [])
        normalized_calls: list[ToolCall] = []
        calls_changed = False
        for call in tool_calls:
            if not isinstance(call, dict):
                normalized_calls.append(cast(ToolCall, call))
                continue
            new_call, changed = cls._coerce_object_at_key(call, "args")
            calls_changed = calls_changed or changed
            normalized_calls.append(cast(ToolCall, new_call))

        content = message.content
        content_changed = False
        if isinstance(content, list):
            new_blocks: list[Any] = []
            for block in content:
                if not isinstance(block, dict):
                    new_blocks.append(block)
                    continue
                # LangChain uses type=tool_use; Bedrock wire form uses toolUse.
                if block.get("type") == "tool_use":
                    new_block, changed = cls._coerce_object_at_key(block, "input")
                    content_changed = content_changed or changed
                    new_blocks.append(new_block)
                elif isinstance(block.get("toolUse"), dict):
                    new_tool_use, changed = cls._coerce_object_at_key(
                        block["toolUse"], "input"
                    )
                    if changed:
                        content_changed = True
                        new_blocks.append({**block, "toolUse": new_tool_use})
                    else:
                        new_blocks.append(block)
                else:
                    new_blocks.append(block)
            if content_changed:
                content = new_blocks

        additional_kwargs = dict(getattr(message, "additional_kwargs", None) or {})
        kwargs_changed = False
        raw_tool_calls = additional_kwargs.get("tool_calls")
        if isinstance(raw_tool_calls, list):
            new_raw: list[Any] = []
            for call in raw_tool_calls:
                if not isinstance(call, dict):
                    new_raw.append(call)
                    continue
                # OpenAI-style nested function.arguments is a JSON *string*, so it
                # needs string (re)serialization rather than the dict-valued path.
                function = call.get("function")
                if isinstance(function, dict) and "arguments" in function:
                    arguments = function["arguments"]
                    # Leave a valid object untouched: a dict, or a string
                    # encoding one. Re-encoding a valid object would only
                    # reformat it and spuriously flag the message as changed.
                    # Still rewrite objects that contain empty-string keys —
                    # Bedrock Document types reject those.
                    if isinstance(arguments, dict):
                        coerced = cls._coerce_tool_args_to_object(arguments)
                        if coerced is arguments:
                            new_raw.append(call)
                        else:
                            kwargs_changed = True
                            new_raw.append(
                                {
                                    **call,
                                    "function": {**function, "arguments": coerced},
                                }
                            )
                    elif isinstance(arguments, str) and cls._is_json_object_string(
                        arguments
                    ):
                        parsed = json.loads(arguments)
                        coerced = cls._coerce_tool_args_to_object(parsed)
                        if coerced is parsed:
                            new_raw.append(call)
                        else:
                            kwargs_changed = True
                            new_raw.append(
                                {
                                    **call,
                                    "function": {
                                        **function,
                                        "arguments": json.dumps(coerced),
                                    },
                                }
                            )
                    else:
                        kwargs_changed = True
                        new_raw.append(
                            {
                                **call,
                                "function": {
                                    **function,
                                    "arguments": json.dumps(
                                        cls._coerce_tool_args_to_object(arguments)
                                    ),
                                },
                            }
                        )
                elif "args" in call:
                    new_call, changed = cls._coerce_object_at_key(call, "args")
                    kwargs_changed = kwargs_changed or changed
                    new_raw.append(new_call)
                else:
                    new_raw.append(call)
            if kwargs_changed:
                additional_kwargs["tool_calls"] = new_raw

        if not (calls_changed or content_changed or kwargs_changed):
            return message

        return AIMessage(
            content=content,
            tool_calls=normalized_calls,
            invalid_tool_calls=list(getattr(message, "invalid_tool_calls", None) or []),
            id=message.id,
            additional_kwargs=additional_kwargs,
            response_metadata=dict(getattr(message, "response_metadata", None) or {}),
            usage_metadata=getattr(message, "usage_metadata", None),
            name=getattr(message, "name", None),
            example=getattr(message, "example", False),
        )

    @classmethod
    def _normalize_tool_inputs_in_messages(
        cls, messages: list[AnyMessage]
    ) -> list[AnyMessage]:
        """Normalize tool inputs across a message history before model invoke."""
        normalized: list[AnyMessage] = []
        changed = False
        for message in messages:
            if isinstance(message, AIMessage):
                new_message = cls._normalize_ai_message_tool_inputs(message)
                if new_message is not message:
                    changed = True
                normalized.append(new_message)
            else:
                normalized.append(message)
        return normalized if changed else messages
