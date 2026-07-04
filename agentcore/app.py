"""AgentCore Runtime entrypoint for the architect agent workflow.

This is the payload AgentCore Runtime hosts: BedrockAgentCoreApp serves the
/invocations + /ping contract on port 8080, and the entrypoint streams the
OrchestratorAgent's AgentEvents back as SSE.

Session model: AgentCore gives each runtimeSessionId its own isolated
microVM whose process stays warm between invocations of the same session —
so a per-session OrchestratorAgent held in module state preserves the
Strands conversation memory across clarification rounds exactly like the
local path does. The Streamlit client passes its Session.session_id as the
runtimeSessionId (36 chars — satisfies the 33+ minimum).

Invocation payload:
    {"prompt": "<user message>", "model_id": "<optional Bedrock model id>"}

Each streamed line is one AgentEvent serialized to JSON
(type / data / phase / timestamp).
"""

from __future__ import annotations

import logging

from bedrock_agentcore import BedrockAgentCoreApp

from agents.orchestrator import OrchestratorAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# One orchestrator per runtime session. AgentCore isolates sessions into
# separate microVMs, so in practice this dict holds a single session's
# orchestrator — it is a dict only to be correct if the platform ever
# multiplexes.
_orchestrators: dict[str, OrchestratorAgent] = {}


@app.entrypoint
async def invoke(payload: dict, context):
    """Stream one workflow turn for the session."""
    session_id = getattr(context, "session_id", None) or "default"
    prompt = (payload or {}).get("prompt", "")
    model_id = (payload or {}).get("model_id")

    if not prompt:
        yield {"type": "error", "data": {"message": "Empty prompt."}, "phase": None, "timestamp": 0}
        return

    orchestrator = _orchestrators.get(session_id)
    if orchestrator is None:
        logger.info("Creating orchestrator for session %s", session_id)
        orchestrator = OrchestratorAgent(session_id=session_id, model_id=model_id)
        _orchestrators[session_id] = orchestrator

    async for event in orchestrator.run(prompt):
        yield event.model_dump(mode="json")


if __name__ == "__main__":
    app.run()
