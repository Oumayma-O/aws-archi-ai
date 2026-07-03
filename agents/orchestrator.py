"""Orchestrator Agent module.

Implements the top-level OrchestratorAgent that manages workflow phases and
delegates to specialized sub-agents (Clarification, Research, Design, Diagram)
using the Strands agents-as-tools pattern.

Responsibilities:
- Manage workflow phase transitions in strict order
- Pass accumulated context between phases
- Implement retry and degradation strategy
- Handle session persistence via SessionStore
- Enforce max 5 clarification rounds
- Stream AgentEvents to the UI layer
"""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime
from typing import Any, AsyncIterator

from agents.clarification import ClarificationAgent
from agents.design import DesignAgent
from agents.diagram import DiagramAgent
from agents.events import AgentEvent, AgentEventType
from agents.errors import PhaseFailureError, SessionPersistenceError
from agents.research import ResearchAgent
from agents.session_store import SessionStore
from models.session import ConversationMessage, Session, WorkflowPhase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CLARIFICATION_ROUNDS = 5

# Phases in strict execution order
PHASE_ORDER: list[WorkflowPhase] = [
    WorkflowPhase.REQUIREMENTS_ANALYSIS,
    WorkflowPhase.CLARIFICATION,
    WorkflowPhase.RESEARCH,
    WorkflowPhase.DESIGN,
    WorkflowPhase.DIAGRAM_GENERATION,
    WorkflowPhase.REVIEW,
    WorkflowPhase.FINAL_REPORT,
    WorkflowPhase.COMPLETE,
]

# Phases where user messages are queued (non-interactive)
NON_INTERACTIVE_PHASES: set[WorkflowPhase] = {
    WorkflowPhase.RESEARCH,
    WorkflowPhase.DESIGN,
    WorkflowPhase.DIAGRAM_GENERATION,
    WorkflowPhase.REVIEW,
}


# ---------------------------------------------------------------------------
# OrchestratorAgent
# ---------------------------------------------------------------------------


class OrchestratorAgent:
    """Top-level workflow orchestrator using agents-as-tools pattern.

    Manages the full architecture design workflow by delegating to specialized
    sub-agents in strict phase order. Handles session persistence, retry logic
    with graceful degradation, and message queuing during non-interactive phases.
    """

    def __init__(self, session_id: str | None = None):
        """Initialize with sub-agents registered as tools.

        Args:
            session_id: Optional existing session to resume. If provided,
                attempts to load from SessionStore.
        """
        # Initialize sub-agents (all support model=None for deterministic fallback)
        self._clarification_agent = ClarificationAgent(model=None)
        self._research_agent = ResearchAgent(model=None)
        self._design_agent = DesignAgent(model=None)
        self._diagram_agent = DiagramAgent(model=None)

        # Session store for persistence
        self._session_store = SessionStore()

        # Message queue for non-interactive phases
        self._message_queue: deque[str] = deque()

        # Initialize or load session
        self._session: Session
        if session_id is not None:
            self._session = self._load_session(session_id)
        else:
            self._session = Session()

    def _load_session(self, session_id: str) -> Session:
        """Attempt to load a session from the store.

        Falls back to creating a new session if load fails.

        Args:
            session_id: The session ID to load.

        Returns:
            Loaded Session or a new Session if loading fails.
        """
        try:
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                session = loop.run_until_complete(
                    self._session_store.load(session_id)
                )
            finally:
                loop.close()

            if session is not None:
                return session

            logger.warning(
                "Session %s not found; creating new session.", session_id
            )
            return Session()
        except (SessionPersistenceError, Exception) as exc:
            logger.warning(
                "Failed to load session %s: %s. Creating new session.",
                session_id,
                exc,
            )
            return Session()

    def get_session(self) -> Session:
        """Return the current session state."""
        return self._session

    async def run(self, user_message: str) -> AsyncIterator[AgentEvent]:
        """Process a user message and yield streaming events.

        Handles the message based on the current workflow phase:
        - During interactive phases (REQUIREMENTS_ANALYSIS, CLARIFICATION):
          processes immediately.
        - During non-interactive phases: queues the message.
        - For FINAL_REPORT/COMPLETE: delivers queued messages.

        Args:
            user_message: The user's input text.

        Yields:
            AgentEvent objects (text chunks, phase transitions, artifacts).
        """
        # Record user message in conversation history
        self._session.conversation_history.append(
            ConversationMessage(
                role="user",
                content=user_message,
                timestamp=datetime.utcnow(),
                phase=self._session.current_phase,
            )
        )

        current_phase = self._session.current_phase

        # If in a non-interactive phase, queue the message
        if current_phase in NON_INTERACTIVE_PHASES:
            self._message_queue.append(user_message)
            yield AgentEvent(
                type=AgentEventType.TEXT_CHUNK,
                data="Your message has been queued and will be delivered when the current phase completes.",
                phase=current_phase.value,
                timestamp=time.time(),
            )
            return

        # Handle based on current phase
        if current_phase == WorkflowPhase.REQUIREMENTS_ANALYSIS:
            async for event in self._handle_requirements_analysis(user_message):
                yield event

        elif current_phase == WorkflowPhase.CLARIFICATION:
            async for event in self._handle_clarification(user_message):
                yield event

        elif current_phase in (WorkflowPhase.FINAL_REPORT, WorkflowPhase.COMPLETE):
            # Workflow already complete, acknowledge
            yield AgentEvent(
                type=AgentEventType.TEXT_CHUNK,
                data="The architecture workflow is complete. You can review the final report above.",
                phase=current_phase.value,
                timestamp=time.time(),
            )

    async def _handle_requirements_analysis(
        self, user_message: str
    ) -> AsyncIterator[AgentEvent]:
        """Handle the initial requirements analysis phase.

        Passes the user's description to the ClarificationAgent to begin
        gathering requirements, then transitions to CLARIFICATION.
        """
        yield AgentEvent(
            type=AgentEventType.TEXT_CHUNK,
            data="Analyzing your system description...",
            phase=WorkflowPhase.REQUIREMENTS_ANALYSIS.value,
            timestamp=time.time(),
        )

        # Run clarification agent to generate initial questions
        result = self._clarification_agent.analyze_and_clarify(
            description=user_message,
            existing_profile=self._session.requirements_profile,
        )

        if result.is_complete and result.profile is not None:
            # User's description was comprehensive or they signaled skip
            self._session.requirements_profile = result.profile
            # Transition directly through clarification to research
            async for event in self._transition_to_phase(WorkflowPhase.CLARIFICATION):
                yield event
            async for event in self._run_non_interactive_phases():
                yield event
        else:
            # Transition to clarification and present questions
            async for event in self._transition_to_phase(WorkflowPhase.CLARIFICATION):
                yield event

            if result.questions:
                questions_text = "I have a few questions to help design the best architecture for you:\n\n"
                for i, q in enumerate(result.questions, 1):
                    questions_text += f"{i}. {q.question}"
                    if q.suggested_default:
                        questions_text += f" (default: {q.suggested_default})"
                    questions_text += "\n"

                self._session.conversation_history.append(
                    ConversationMessage(
                        role="assistant",
                        content=questions_text,
                        timestamp=datetime.utcnow(),
                        phase=WorkflowPhase.CLARIFICATION,
                    )
                )

                yield AgentEvent(
                    type=AgentEventType.TEXT_CHUNK,
                    data=questions_text,
                    phase=WorkflowPhase.CLARIFICATION.value,
                    timestamp=time.time(),
                )

            self._session.clarification_rounds = 1
            await self._persist_session()

    async def _handle_clarification(
        self, user_message: str
    ) -> AsyncIterator[AgentEvent]:
        """Handle a user response during the clarification phase.

        Passes answers to ClarificationAgent, either asks more questions
        or transitions to the non-interactive phases.
        """
        self._session.clarification_rounds += 1

        # Check if max rounds reached
        if self._session.clarification_rounds > MAX_CLARIFICATION_ROUNDS:
            yield AgentEvent(
                type=AgentEventType.TEXT_CHUNK,
                data="Maximum clarification rounds reached. Proceeding with gathered requirements.",
                phase=WorkflowPhase.CLARIFICATION.value,
                timestamp=time.time(),
            )
            # Force completion of profile
            result = self._clarification_agent.analyze_and_clarify(
                description=user_message,
                existing_profile=self._session.requirements_profile,
            )
            if result.profile is not None:
                self._session.requirements_profile = result.profile

            async for event in self._run_non_interactive_phases():
                yield event
            return

        # Run clarification with existing profile context
        result = self._clarification_agent.analyze_and_clarify(
            description=user_message,
            existing_profile=self._session.requirements_profile,
        )

        if result.is_complete and result.profile is not None:
            self._session.requirements_profile = result.profile

            yield AgentEvent(
                type=AgentEventType.TEXT_CHUNK,
                data="Requirements gathered. Starting research and design phases...",
                phase=WorkflowPhase.CLARIFICATION.value,
                timestamp=time.time(),
            )

            # Run the non-interactive pipeline
            async for event in self._run_non_interactive_phases():
                yield event
        else:
            # Update profile if partially available
            if result.profile is not None:
                self._session.requirements_profile = result.profile

            # Present more questions
            if result.questions:
                questions_text = "Thanks for the details. A few more questions:\n\n"
                for i, q in enumerate(result.questions, 1):
                    questions_text += f"{i}. {q.question}"
                    if q.suggested_default:
                        questions_text += f" (default: {q.suggested_default})"
                    questions_text += "\n"

                self._session.conversation_history.append(
                    ConversationMessage(
                        role="assistant",
                        content=questions_text,
                        timestamp=datetime.utcnow(),
                        phase=WorkflowPhase.CLARIFICATION,
                    )
                )

                yield AgentEvent(
                    type=AgentEventType.TEXT_CHUNK,
                    data=questions_text,
                    phase=WorkflowPhase.CLARIFICATION.value,
                    timestamp=time.time(),
                )

            await self._persist_session()

    async def _run_non_interactive_phases(self) -> AsyncIterator[AgentEvent]:
        """Run all non-interactive phases in sequence.

        Executes RESEARCH → DESIGN → DIAGRAM_GENERATION → REVIEW → FINAL_REPORT → COMPLETE.
        Each phase has retry-once + degradation strategy.
        """
        # --- RESEARCH ---
        async for event in self._transition_to_phase(WorkflowPhase.RESEARCH):
            yield event
        async for event in self._execute_phase_with_retry(
            WorkflowPhase.RESEARCH, self._run_research
        ):
            yield event

        # --- DESIGN ---
        async for event in self._transition_to_phase(WorkflowPhase.DESIGN):
            yield event
        async for event in self._execute_phase_with_retry(
            WorkflowPhase.DESIGN, self._run_design
        ):
            yield event

        # --- DIAGRAM_GENERATION ---
        async for event in self._transition_to_phase(WorkflowPhase.DIAGRAM_GENERATION):
            yield event
        async for event in self._execute_phase_with_retry(
            WorkflowPhase.DIAGRAM_GENERATION, self._run_diagram
        ):
            yield event

        # --- REVIEW ---
        async for event in self._transition_to_phase(WorkflowPhase.REVIEW):
            yield event
        async for event in self._execute_phase_with_retry(
            WorkflowPhase.REVIEW, self._run_review
        ):
            yield event

        # --- FINAL_REPORT ---
        async for event in self._transition_to_phase(WorkflowPhase.FINAL_REPORT):
            yield event
        async for event in self._run_final_report():
            yield event

        # --- COMPLETE ---
        async for event in self._transition_to_phase(WorkflowPhase.COMPLETE):
            yield event

        self._session.is_complete = True
        await self._persist_session()

        # Deliver any queued messages
        if self._message_queue:
            queued = list(self._message_queue)
            self._message_queue.clear()
            queued_text = (
                f"You sent {len(queued)} message(s) during processing. "
                "They have been noted for context:\n"
                + "\n".join(f"- {msg}" for msg in queued)
            )
            yield AgentEvent(
                type=AgentEventType.TEXT_CHUNK,
                data=queued_text,
                phase=WorkflowPhase.COMPLETE.value,
                timestamp=time.time(),
            )

        yield AgentEvent(
            type=AgentEventType.COMPLETE,
            data="Architecture workflow complete.",
            phase=WorkflowPhase.COMPLETE.value,
            timestamp=time.time(),
        )

    async def _execute_phase_with_retry(
        self,
        phase: WorkflowPhase,
        phase_fn: Any,
    ) -> AsyncIterator[AgentEvent]:
        """Execute a phase function with retry-once and degradation.

        If the first attempt fails, retries once. If the second attempt
        also fails, yields an error event and proceeds with degraded output.

        Args:
            phase: The workflow phase being executed.
            phase_fn: Async generator function to execute.
        """
        for attempt in range(2):
            try:
                async for event in phase_fn():
                    yield event
                return  # Success
            except Exception as exc:
                if attempt == 0:
                    logger.warning(
                        "Phase %s failed (attempt 1/2): %s. Retrying...",
                        phase.value,
                        exc,
                    )
                    yield AgentEvent(
                        type=AgentEventType.TEXT_CHUNK,
                        data=f"Retrying {phase.value} phase...",
                        phase=phase.value,
                        timestamp=time.time(),
                    )
                else:
                    # Second failure: proceed with degraded output
                    logger.error(
                        "Phase %s failed after 2 attempts: %s. Proceeding with degraded output.",
                        phase.value,
                        exc,
                    )
                    yield AgentEvent(
                        type=AgentEventType.ERROR,
                        data={
                            "phase": phase.value,
                            "error": str(exc),
                            "message": f"The {phase.value} phase encountered an issue. "
                            "Proceeding with limited results.",
                        },
                        phase=phase.value,
                        timestamp=time.time(),
                    )

    async def _run_research(self) -> AsyncIterator[AgentEvent]:
        """Execute the research phase."""
        profile = self._session.requirements_profile
        if profile is None:
            raise PhaseFailureError("research", 1, ValueError("No requirements profile available"))

        yield AgentEvent(
            type=AgentEventType.TEXT_CHUNK,
            data="Researching AWS best practices, reference architectures, and pricing...",
            phase=WorkflowPhase.RESEARCH.value,
            timestamp=time.time(),
        )

        research_summary = self._research_agent.research(profile)
        self._session.research_summary = research_summary

        yield AgentEvent(
            type=AgentEventType.TEXT_CHUNK,
            data=(
                f"Research complete. Found {len(research_summary.reference_architectures)} "
                f"reference architectures and {len(research_summary.service_recommendations)} "
                "service recommendations."
            ),
            phase=WorkflowPhase.RESEARCH.value,
            timestamp=time.time(),
        )

    async def _run_design(self) -> AsyncIterator[AgentEvent]:
        """Execute the design phase."""
        profile = self._session.requirements_profile
        research = self._session.research_summary

        if profile is None:
            raise PhaseFailureError("design", 1, ValueError("No requirements profile available"))

        if research is None:
            # Degraded: create minimal research summary
            from models.research import ResearchSummary

            research = ResearchSummary(
                data_sources_available=False,
                notes=["Research phase was skipped or failed; using defaults."],
            )
            self._session.research_summary = research

        yield AgentEvent(
            type=AgentEventType.TEXT_CHUNK,
            data="Designing architecture based on requirements and research findings...",
            phase=WorkflowPhase.DESIGN.value,
            timestamp=time.time(),
        )

        report = self._design_agent.design(profile, research)
        self._session.architecture_report = report

        yield AgentEvent(
            type=AgentEventType.TEXT_CHUNK,
            data=f"Architecture design complete: {report.title}",
            phase=WorkflowPhase.DESIGN.value,
            timestamp=time.time(),
        )

    async def _run_diagram(self) -> AsyncIterator[AgentEvent]:
        """Execute the diagram generation phase."""
        report = self._session.architecture_report
        if report is None:
            raise PhaseFailureError(
                "diagram_generation", 1, ValueError("No architecture report available")
            )

        yield AgentEvent(
            type=AgentEventType.TEXT_CHUNK,
            data="Generating architecture diagram...",
            phase=WorkflowPhase.DIAGRAM_GENERATION.value,
            timestamp=time.time(),
        )

        diagram_result = self._diagram_agent.generate(report)

        # Emit diagram as artifact
        yield AgentEvent(
            type=AgentEventType.ARTIFACT,
            data={
                "type": "diagram",
                "format": "drawio_xml",
                "content": diagram_result.drawio_xml,
                "has_png": diagram_result.png_bytes is not None,
            },
            phase=WorkflowPhase.DIAGRAM_GENERATION.value,
            timestamp=time.time(),
        )

        yield AgentEvent(
            type=AgentEventType.TEXT_CHUNK,
            data="Architecture diagram generated successfully.",
            phase=WorkflowPhase.DIAGRAM_GENERATION.value,
            timestamp=time.time(),
        )

    async def _run_review(self) -> AsyncIterator[AgentEvent]:
        """Execute the Well-Architected review phase."""
        report = self._session.architecture_report
        if report is None:
            raise PhaseFailureError(
                "review", 1, ValueError("No architecture report available")
            )

        yield AgentEvent(
            type=AgentEventType.TEXT_CHUNK,
            data="Reviewing architecture against the Well-Architected Framework...",
            phase=WorkflowPhase.REVIEW.value,
            timestamp=time.time(),
        )

        review = self._design_agent.review(report)
        report.well_architected_review = review
        self._session.architecture_report = report

        # Summarize review findings
        violations_count = len(review.violations)
        improvements_count = len(review.improvement_opportunities)
        review_text = (
            f"Well-Architected review complete. "
            f"Found {violations_count} violation(s) and "
            f"{improvements_count} improvement opportunity(ies)."
        )
        if review.violations:
            review_text += "\n\nViolations:\n" + "\n".join(
                f"- {v}" for v in review.violations
            )

        yield AgentEvent(
            type=AgentEventType.TEXT_CHUNK,
            data=review_text,
            phase=WorkflowPhase.REVIEW.value,
            timestamp=time.time(),
        )

    async def _run_final_report(self) -> AsyncIterator[AgentEvent]:
        """Compile and emit the final architecture report."""
        report = self._session.architecture_report
        if report is None:
            yield AgentEvent(
                type=AgentEventType.ERROR,
                data={
                    "phase": "final_report",
                    "message": "No architecture report available to finalize.",
                },
                phase=WorkflowPhase.FINAL_REPORT.value,
                timestamp=time.time(),
            )
            return

        yield AgentEvent(
            type=AgentEventType.TEXT_CHUNK,
            data="Compiling final architecture report...",
            phase=WorkflowPhase.FINAL_REPORT.value,
            timestamp=time.time(),
        )

        # Emit the full report as an artifact
        report_data = report.model_dump(mode="json")
        yield AgentEvent(
            type=AgentEventType.ARTIFACT,
            data={
                "type": "architecture_report",
                "format": "json",
                "content": report_data,
                "title": report.title,
            },
            phase=WorkflowPhase.FINAL_REPORT.value,
            timestamp=time.time(),
        )

        # Add assistant message summarizing the report
        summary_text = (
            f"## {report.title}\n\n"
            f"{report.summary}\n\n"
            f"**Services:** {', '.join(s.name for s in report.aws_services)}\n"
            f"**Estimated Cost:** {report.estimated_cost.total_monthly}/month\n"
            f"**Cost Comparisons:** {len(report.cost_comparisons)} alternatives analyzed\n"
        )
        if report.well_architected_review:
            summary_text += (
                f"**Well-Architected Review:** "
                f"{len(report.well_architected_review.violations)} violations, "
                f"{len(report.well_architected_review.improvement_opportunities)} improvements\n"
            )
        if report.iac_skeleton:
            summary_text += "**IaC Skeleton:** Included\n"

        self._session.conversation_history.append(
            ConversationMessage(
                role="assistant",
                content=summary_text,
                timestamp=datetime.utcnow(),
                phase=WorkflowPhase.FINAL_REPORT,
            )
        )

        yield AgentEvent(
            type=AgentEventType.TEXT_CHUNK,
            data=summary_text,
            phase=WorkflowPhase.FINAL_REPORT.value,
            timestamp=time.time(),
        )

    async def _transition_to_phase(
        self, new_phase: WorkflowPhase
    ) -> AsyncIterator[AgentEvent]:
        """Transition to a new workflow phase.

        Updates session state and persists after each transition.

        Args:
            new_phase: The phase to transition to.
        """
        old_phase = self._session.current_phase
        self._session.current_phase = new_phase
        self._session.updated_at = datetime.utcnow()

        yield AgentEvent(
            type=AgentEventType.PHASE_TRANSITION,
            data={
                "from_phase": old_phase.value,
                "to_phase": new_phase.value,
            },
            phase=new_phase.value,
            timestamp=time.time(),
        )

        await self._persist_session()

    async def _persist_session(self) -> None:
        """Persist session state to the SessionStore.

        Silently logs errors — session persistence failures should not
        block the workflow.
        """
        try:
            await self._session_store.save(self._session)
        except SessionPersistenceError as exc:
            logger.warning("Failed to persist session: %s", exc)
        except Exception as exc:
            logger.warning("Unexpected error persisting session: %s", exc)
