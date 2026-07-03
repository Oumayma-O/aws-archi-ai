# Implementation Plan: Agentic Architect

## Overview

Transform the existing AWS Architect AI from a single-shot generation tool into a multi-turn, conversational AWS Solutions Architect powered by Strands Agents SDK. The implementation follows a phased approach: data models → agent scaffolding → individual agents → orchestrator → UI → deployment → observability. All work is additive — the existing Quick Generate pipeline remains untouched.

## Tasks

- [x] 1. Set up project structure and dependencies
  - [x] 1.1 Add Strands SDK and new dependencies to requirements.txt
    - Add `strands-agents`, `strands-agents-tools`, `boto3` (DynamoDB), `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`, `hypothesis` (dev), `moto` (dev), `pytest-asyncio` (dev) to requirements.txt
    - Pin exact versions for all new dependencies
    - Verify existing dependencies are not broken
    - _Requirements: 9.1, 9.3_

  - [x] 1.2 Create agents/ package directory structure
    - Create `agents/__init__.py`, `agents/orchestrator.py`, `agents/clarification.py`, `agents/research.py`, `agents/design.py`, `agents/diagram.py`, `agents/session_store.py`, `agents/mcp_config.py`, `agents/events.py`, `agents/errors.py`
    - Create empty module files with docstrings
    - Ensure agents/ does not import from pages/ (dependency rule)
    - _Requirements: 9.1_

  - [x] 1.3 Create test directory structure for agentic features
    - Create `tests/unit/`, `tests/property/`, `tests/integration/` directories
    - Add `conftest.py` files with shared fixtures (mock MCP clients, mock DynamoDB, sample RequirementsProfile)
    - Configure pytest-asyncio and Hypothesis settings
    - _Requirements: 9.1_

- [x] 2. Implement data models
  - [x] 2.1 Create models/requirements.py with RequirementsProfile and related models
    - Implement `TrafficPattern`, `ComplianceRequirement`, and `RequirementsProfile` Pydantic models as defined in the design
    - Include all fields with proper types, defaults, and descriptions
    - _Requirements: 1.1, 1.3, 1.5_

  - [x] 2.2 Create models/clarification.py with ClarificationResult model
    - Implement `ClarifyingQuestion` and `ClarificationResult` Pydantic models
    - Ensure `ClarifyingQuestion` has `question`, `category`, and `suggested_default` fields
    - _Requirements: 1.1, 1.7_

  - [x] 2.3 Create models/research.py with ResearchSummary and related models
    - Implement `ReferenceArchitecture`, `ServiceRecommendation`, `WellArchitectedGuidance`, `PricingComparison`, and `ResearchSummary` Pydantic models
    - _Requirements: 3.4, 4.1, 4.2_

  - [x] 2.4 Create models/report.py with ArchitectureReport and related models
    - Implement `VPCDesign`, `CostComparison`, `ArchitectureRationale`, `WellArchitectedReview`, and `ArchitectureReport` Pydantic models
    - Import and reuse existing types from `models/architecture.py` (ServiceDetail, SecurityConfig, EstimatedCost, DiagramData, NetworkingConfig, MonitoringConfig, ScalingConfig)
    - Ensure ArchitectureReport is a strict superset of ArchitectureModel fields
    - _Requirements: 12.1, 12.6, 14.5_

  - [x] 2.5 Create models/session.py with Session and WorkflowPhase models
    - Implement `WorkflowPhase` enum, `ConversationMessage`, and `Session` Pydantic models
    - Include all fields: session_id, user_id, timestamps, current_phase, conversation_history, requirements_profile, research_summary, architecture_report, clarification_rounds, is_complete
    - _Requirements: 2.1, 2.4, 2.5_

  - [ ]* 2.6 Write property test for ArchitectureReport serialization round-trip
    - **Property 17: Architecture report serialization round-trip**
    - Use Hypothesis `from_model(ArchitectureReport)` strategy
    - Verify `model_validate_json(report.model_dump_json()) == report`
    - **Validates: Requirements 12.6**

  - [ ]* 2.7 Write property test for backward compatibility with ArchitectureModel
    - **Property 19: ArchitectureReport is backward-compatible with ArchitectureModel**
    - For any valid ArchitectureReport, extracting ArchitectureModel fields produces a valid ArchitectureModel
    - **Validates: Requirements 14.5**

  - [ ]* 2.8 Write property test for VPC design validity
    - **Property 12: VPC design is complete and follows security checklist**
    - Generate random VPCDesign instances and validate: valid CIDR, subnets span ≥2 AZs, no 0.0.0.0/0 on non-public ports, no databases in public subnets, NAT per AZ for HA
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.6**

  - [ ]* 2.9 Write property test for report completeness
    - **Property 15: Final report contains all required sections**
    - Verify non-empty title, summary, aws_services, security.recommendations, cost_comparisons ≥2, diagram.nodes non-empty, well_architected_review non-null
    - **Validates: Requirements 8.4, 12.1, 12.2, 12.3, 12.4**

  - [ ]* 2.10 Write property test for service justification
    - **Property 10: Every selected service has a documented justification**
    - For any ArchitectureReport, every entry in aws_services has a corresponding rationale entry
    - **Validates: Requirements 5.1, 5.5**

- [x] 3. Checkpoint - Ensure all data model tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement agent events and error handling
  - [x] 4.1 Implement agents/events.py with AgentEvent streaming types
    - Implement `AgentEventType` enum (TEXT_CHUNK, PHASE_TRANSITION, ARTIFACT, TOOL_CALL, ERROR, COMPLETE)
    - Implement `AgentEvent` Pydantic model with type, data, phase, timestamp
    - _Requirements: 13.2, 13.3_

  - [x] 4.2 Implement agents/errors.py with custom exception hierarchy
    - Implement `AgenticArchitectError` base class, `MCPConnectionError`, `PhaseFailureError`, `SessionPersistenceError`, `AgentTimeoutError`, `BedrockConnectionError`, `BedrockThrottlingError`, `StreamingError`, `ValidationError`
    - Include context fields (server_name, phase, attempts, etc.)
    - _Requirements: 8.5_

- [x] 5. Implement session store
  - [x] 5.1 Implement agents/session_store.py with DynamoDB-backed persistence
    - Implement `SessionStore` class with `save()`, `load()`, `list_sessions()` methods
    - Use boto3 DynamoDB resource with table name from environment variable
    - Handle serialization of Pydantic models to/from DynamoDB items
    - Implement retry logic for `SessionPersistenceError`
    - _Requirements: 2.1, 2.4, 2.5_

  - [ ]* 5.2 Write property test for session state accumulation
    - **Property 6: Session state accumulates correctly across turns**
    - For any sequence of conversation turns, verify: messages in chronological order, current phase matches latest transition, non-null requirements_profile after clarification
    - **Validates: Requirements 2.1**

  - [ ]* 5.3 Write unit tests for SessionStore CRUD operations
    - Use moto to mock DynamoDB
    - Test save, load, list_sessions, session not found, persistence error handling
    - _Requirements: 2.1, 2.4, 2.5_

- [x] 6. Implement MCP configuration
  - [x] 6.1 Implement agents/mcp_config.py with MCP client factory functions
    - Implement `create_docs_mcp()`, `create_pricing_mcp()`, `create_drawio_mcp()` functions
    - Use Strands `MCPClient` with appropriate transports (StdioTransport or StreamableHTTPTransport)
    - Load server URLs/commands from environment variables
    - Handle connection failures gracefully
    - _Requirements: 9.3, 3.1, 4.1_

- [x] 7. Implement Clarification Agent
  - [x] 7.1 Implement agents/clarification.py with ClarificationAgent class
    - Create Strands Agent with system prompt for requirements gathering
    - Implement `analyze_and_clarify()` method that takes description and optional existing profile
    - Generate questions for uncovered categories, omitting already-answered ones
    - Ensure every question has a `suggested_default`
    - Handle skip-intent detection (phrases like "skip", "just generate", "go ahead")
    - Produce complete RequirementsProfile when sufficient information gathered
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ]* 7.2 Write property test for clarifying question completeness
    - **Property 1: Clarifying questions are well-formed and cover required categories**
    - For random descriptions, verify questions cover all uncovered categories and all have suggested_default
    - **Validates: Requirements 1.1, 1.7**

  - [ ]* 7.3 Write property test for question filtering
    - **Property 2: Questions for explicitly stated requirements are omitted**
    - For descriptions with embedded category answers, verify no duplicate questions
    - **Validates: Requirements 1.2**

  - [ ]* 7.4 Write property test for profile update preservation
    - **Property 3: Profile update preserves all user answers**
    - For random profiles and answer sets, verify round-trip consistency
    - **Validates: Requirements 1.3**

  - [ ]* 7.5 Write property test for skip-intent handling
    - **Property 4: Skip-intent triggers defaults with documented assumptions**
    - For random skip-intent phrases, verify is_complete=True and non-empty assumptions
    - **Validates: Requirements 1.5**

  - [ ]* 7.6 Write property test for maximum clarification rounds
    - **Property 5: Clarification rounds never exceed maximum**
    - For random answer sequences (1-10 rounds), verify counter never exceeds 5
    - **Validates: Requirements 1.6**

- [x] 8. Checkpoint - Ensure clarification agent tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement Research Agent
  - [x] 9.1 Implement agents/research.py with ResearchAgent class
    - Create Strands Agent with MCP tool bindings (docs_mcp, pricing_mcp)
    - Implement `research()` method accepting RequirementsProfile
    - Query AWS_Docs_MCP for reference architectures, best practices, and WAF guidance
    - Query Pricing_MCP for service pricing in user's region
    - Produce cost comparisons for alternative services
    - Handle MCP unavailability with graceful degradation
    - Calculate monthly costs from profile traffic patterns
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 9.2 Write property test for pricing comparison coverage
    - **Property 8: Pricing comparison includes all candidate alternatives**
    - For random service candidate sets, verify all services appear in PricingComparison output
    - **Validates: Requirements 4.2**

  - [ ]* 9.3 Write property test for cost derivation from profile
    - **Property 9: Cost estimates are derived from profile traffic and storage values**
    - For profiles with non-zero traffic, verify costs are non-zero and reference profile values
    - **Validates: Requirements 4.4**

- [x] 10. Implement Design Agent
  - [x] 10.1 Implement agents/design.py with DesignAgent class
    - Create Strands Agent with system prompt for architecture design
    - Implement `design()` method accepting RequirementsProfile and ResearchSummary
    - Produce complete ArchitectureReport with services, networking, VPC, security, costs, rationale
    - Implement `review()` method for Well-Architected Framework validation
    - Respect budget constraints with documented trade-offs
    - Include IaC skeleton when iac_preference is specified
    - Omit VPC for fully serverless architectures
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 8.3, 12.5_

  - [ ]* 10.2 Write property test for budget compliance
    - **Property 11: Architecture respects budget constraints**
    - For profiles with budget_monthly_usd, verify estimated_cost ≤ budget OR rationale documents trade-off
    - **Validates: Requirements 5.3**

  - [ ]* 10.3 Write property test for serverless VPC omission
    - **Property 13: Fully serverless architectures omit VPC design**
    - For serverless-only profiles, verify vpc_design is None
    - **Validates: Requirements 6.5**

  - [ ]* 10.4 Write property test for IaC conditional inclusion
    - **Property 16: IaC skeleton is included when preference is specified**
    - For profiles with iac_preference set, verify iac_skeleton is non-null and non-empty
    - **Validates: Requirements 12.5**

- [x] 11. Implement Diagram Agent
  - [x] 11.1 Implement agents/diagram.py with DiagramAgent class
    - Create Strands Agent with MCP tool binding (drawio_mcp)
    - Implement `generate()` method accepting ArchitectureReport
    - Produce Draw.io XML with AWS icon stencils, VPC boundaries, AZ layouts
    - Fall back to local XML generation when MCP unavailable (reuse existing diagram service)
    - Generate PNG rendering for inline display
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 11.2 Write property test for diagram XML validity
    - **Property 14: Generated diagram XML is well-formed and parseable**
    - For random DiagramData with non-empty nodes, verify well-formed XML with mxGraphModel root and mxCell per node
    - **Validates: Requirements 7.4**

- [x] 12. Checkpoint - Ensure all agent tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Implement Orchestrator Agent
  - [x] 13.1 Implement agents/orchestrator.py with OrchestratorAgent class
    - Create top-level Strands Agent using agents-as-tools pattern
    - Register ClarificationAgent, ResearchAgent, DesignAgent, DiagramAgent as tools
    - Implement `run()` async method yielding AgentEvent stream
    - Manage workflow phase transitions in strict order
    - Pass accumulated context between phases (RequirementsProfile → ResearchSummary → ArchitectureReport)
    - Implement retry and degradation strategy (retry once, then proceed with degraded output)
    - Implement message queuing for non-interactive phases
    - Implement session persistence via SessionStore (save after each phase transition)
    - Enforce max 5 clarification rounds
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 2.2, 2.3, 13.6_

  - [ ]* 13.2 Write property test for workflow phase ordering
    - **Property 7: Workflow phases follow required ordering**
    - For random phase transition sequences, verify ordering is a subsequence of the canonical order
    - **Validates: Requirements 8.1**

  - [ ]* 13.3 Write property test for message queuing during non-interactive phases
    - **Property 18: Messages during non-interactive phases are queued**
    - For random messages sent during RESEARCH/DESIGN/DIAGRAM_GENERATION/REVIEW, verify queued and delivered later
    - **Validates: Requirements 13.6**

- [x] 14. Implement Streamlit Chat UI (Architect Mode)
  - [x] 14.1 Add mode selector to pages/1_Generator.py
    - Add a radio/toggle UI element for "Quick Generate" vs "Architect Mode" selection
    - Wrap existing Quick Generate logic in `render_quick_generate_mode()` function
    - When "Quick Generate" selected, run existing pipeline unchanged
    - When "Architect Mode" selected, call `render_architect_mode()`
    - _Requirements: 14.1, 14.2, 14.3_

  - [x] 14.2 Implement render_architect_mode() chat interface
    - Use `st.chat_message()` for conversation display
    - Display full conversation history from session state
    - Implement chat input with `st.chat_input()`
    - Stream agent responses using `st.write_stream()` or iterating AgentEvents
    - Show workflow phase indicator (st.status or sidebar badge)
    - Render inline artifacts (diagrams, cost tables) within conversation
    - Retain tabbed results view for final ArchitectureReport
    - Queue user messages during non-interactive phases with visual feedback
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

  - [ ]* 14.3 Write unit tests for UI mode switching
    - Verify Quick Generate mode does not instantiate any agent classes
    - Verify Architect Mode initiates OrchestratorAgent workflow
    - _Requirements: 14.2, 14.3, 14.4_

- [x] 15. Checkpoint - Ensure UI and orchestration tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Infrastructure and deployment
  - [x] 16.1 Add DynamoDB table to Terraform infrastructure
    - Add `architect-sessions` DynamoDB table with partition key `session_id` (String)
    - Add GSI on `user_id` with sort key `updated_at` for listing sessions
    - Set TTL attribute on `expires_at` for automatic cleanup of old sessions
    - Add appropriate IAM permissions for ECS task role
    - _Requirements: 2.1, 2.4_

  - [x] 16.2 Configure AgentCore deployment with ECS Fargate fallback
    - Create AgentCore configuration files for each agent (system prompts, tool bindings, model config)
    - Add environment variables for AgentCore endpoint, fallback mode flag
    - Update Dockerfile to include new agents/ package and dependencies
    - Ensure fallback to local Strands execution on ECS if AgentCore unavailable
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 16.3 Update CI/CD pipeline for agentic features
    - Add property tests and integration tests to GitHub Actions CI workflow
    - Add environment variables for MCP server configuration
    - Ensure deployment targets `dev` branch
    - Add DynamoDB table provisioning to deploy workflow
    - _Requirements: 10.5_

- [x] 17. Implement observability
  - [x] 17.1 Add OpenTelemetry tracing to all agents
    - Configure Strands SDK built-in OTel support
    - Add trace spans for each agent invocation (agent name, phase, duration, tool calls, token usage)
    - Configure X-Ray as the trace collector backend
    - Add structured CloudWatch Logs for phase transitions, tool invocations, and errors
    - Log warnings for MCP calls exceeding 10 seconds
    - Add option to disable prompt logging in production
    - _Requirements: 11.1, 11.2, 11.3, 11.5, 11.6_

  - [x] 17.2 Create observability dashboard configuration
    - Define CloudWatch dashboard JSON for: session timelines, tool invocation success rates, prompt execution durations, token consumption per session, error rates
    - Add dashboard provisioning to Terraform
    - _Requirements: 11.4_

- [x] 18. Integration wiring and final validation
  - [x] 18.1 Wire all components together in agents/__init__.py
    - Export public API: `OrchestratorAgent`, `AgentEvent`, `AgentEventType`, `Session`, `WorkflowPhase`
    - Ensure proper initialization order (MCP config → agents → orchestrator)
    - Add factory function `create_architect_agent(session_id=None)` for UI consumption
    - _Requirements: 9.1, 8.1_

  - [ ]* 18.2 Write integration tests for full workflow
    - Test complete happy path with mocked MCP servers and mocked Bedrock
    - Verify all phases execute in order and produce expected outputs
    - Test MCP fallback scenarios (docs unavailable, pricing unavailable, diagram MCP down)
    - Test session resume from persisted state
    - Test Quick Generate isolation (no agent instantiation)
    - _Requirements: 8.1, 8.5, 3.5, 4.5, 7.6, 14.2_

- [x] 19. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All work is on the `dev` branch — existing Quick Generate pipeline remains functional throughout
- The `agents/` module is additive and does not modify existing `services/` or `models/architecture.py`
- MCP server URLs/commands are loaded from environment variables for flexibility
- Hypothesis property tests use `max_examples=100` with `deadline=None` for agent-related tests

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3", "2.4", "2.5", "4.1", "4.2"] },
    { "id": 2, "tasks": ["2.6", "2.7", "2.8", "2.9", "2.10", "5.1", "6.1"] },
    { "id": 3, "tasks": ["5.2", "5.3", "7.1"] },
    { "id": 4, "tasks": ["7.2", "7.3", "7.4", "7.5", "7.6", "9.1"] },
    { "id": 5, "tasks": ["9.2", "9.3", "10.1"] },
    { "id": 6, "tasks": ["10.2", "10.3", "10.4", "11.1"] },
    { "id": 7, "tasks": ["11.2", "13.1"] },
    { "id": 8, "tasks": ["13.2", "13.3", "14.1"] },
    { "id": 9, "tasks": ["14.2", "14.3"] },
    { "id": 10, "tasks": ["16.1", "16.2", "16.3", "17.1", "17.2"] },
    { "id": 11, "tasks": ["18.1"] },
    { "id": 12, "tasks": ["18.2"] }
  ]
}
```
