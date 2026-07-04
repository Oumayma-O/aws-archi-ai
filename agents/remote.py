"""Remote orchestrator client — runs the agent workflow on AgentCore Runtime.

Drop-in replacement for OrchestratorAgent from the UI's perspective: same
async-generator ``run(user_message)`` yielding AgentEvents, same
``get_session()`` surface for grabbing the final report. Under the hood it
calls ``bedrock-agentcore:InvokeAgentRuntime`` and parses the SSE stream the
entrypoint (agentcore/app.py) emits.

Enable by setting AGENTCORE_RUNTIME_ARN (Terraform output). AGENTCORE_ENABLED
can force it off ("false") without unsetting the ARN.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, AsyncIterator

from agents.events import AgentEvent, AgentEventType
from models.report import ArchitectureReport

logger = logging.getLogger(__name__)


def agentcore_runtime_arn() -> str | None:
    """The configured runtime ARN, or None if remote execution is disabled."""
    if os.environ.get("AGENTCORE_ENABLED", "true").lower() in ("false", "0", "no"):
        return None
    return os.environ.get("AGENTCORE_RUNTIME_ARN") or None


class _RemoteSession:
    """Just enough of models.session.Session for the UI's COMPLETE handler."""

    def __init__(self) -> None:
        self.architecture_report: ArchitectureReport | None = None


class RemoteOrchestrator:
    """Streams workflow turns from an AgentCore Runtime session."""

    def __init__(self, session_id: str | None = None, model_id: str | None = None):
        import boto3

        self._arn = agentcore_runtime_arn()
        if not self._arn:
            raise RuntimeError("AGENTCORE_RUNTIME_ARN is not configured")
        self._model_id = model_id
        # AgentCore requires runtimeSessionId >= 33 chars; uuid4 is 36.
        self._session_id = session_id or str(uuid.uuid4())
        region = os.environ.get("AWS_REGION", "eu-west-1")
        self._client = boto3.client("bedrock-agentcore", region_name=region)
        self._session = _RemoteSession()

    def get_session(self) -> _RemoteSession:
        return self._session

    async def run(self, user_message: str) -> AsyncIterator[AgentEvent]:
        """Invoke the runtime for one turn and yield its streamed events."""
        import asyncio

        payload = json.dumps({"prompt": user_message, "model_id": self._model_id})

        response = await asyncio.to_thread(
            self._client.invoke_agent_runtime,
            agentRuntimeArn=self._arn,
            runtimeSessionId=self._session_id,
            payload=payload,
        )

        body = response.get("response")
        content_type = response.get("contentType", "")

        if "text/event-stream" in content_type:
            for line in await asyncio.to_thread(lambda: list(body.iter_lines())):
                decoded = line.decode("utf-8") if isinstance(line, bytes) else line
                if not decoded.startswith("data:"):
                    continue
                event = self._parse_event(decoded[len("data:"):].strip())
                if event is not None:
                    yield event
        else:
            # Non-streaming fallback: a JSON body (single event or a list).
            raw = await asyncio.to_thread(body.read)
            data = json.loads(raw)
            for item in data if isinstance(data, list) else [data]:
                event = self._parse_event(json.dumps(item) if isinstance(item, dict) else str(item))
                if event is not None:
                    yield event

    def _parse_event(self, raw: str) -> AgentEvent | None:
        try:
            obj = json.loads(raw)
            # SSE payloads may be double-encoded JSON strings
            if isinstance(obj, str):
                obj = json.loads(obj)
            event = AgentEvent.model_validate(obj)
        except Exception:
            logger.debug("Skipping non-event stream line: %.120s", raw)
            return None

        # Capture the final report so the UI's COMPLETE handler finds it
        # on get_session(), same as the local orchestrator.
        if event.type == AgentEventType.ARTIFACT and isinstance(event.data, dict):
            if event.data.get("type") == "architecture_report":
                try:
                    self._session.architecture_report = ArchitectureReport.model_validate(
                        event.data.get("content", {})
                    )
                except Exception as exc:
                    logger.warning("Could not parse remote architecture report: %s", exc)
        return event


def create_orchestrator(model_id: str | None = None) -> Any:
    """Factory the UI uses: AgentCore-backed when configured, local otherwise."""
    if agentcore_runtime_arn():
        try:
            remote = RemoteOrchestrator(model_id=model_id)
            logger.info("Using AgentCore Runtime: %s", remote._arn)
            return remote
        except Exception as exc:
            logger.warning("AgentCore unavailable (%s); using local orchestrator.", exc)

    from agents.orchestrator import OrchestratorAgent

    return OrchestratorAgent(model_id=model_id)
