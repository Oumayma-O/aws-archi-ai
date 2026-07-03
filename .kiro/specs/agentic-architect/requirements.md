# Requirements Document

## Introduction

The Agentic Architect feature evolves the existing AWS Architect AI from a single-shot generation tool into an intelligent, multi-turn agentic AWS Solutions Architect. Instead of immediately generating an architecture from a description, the system conducts a conversational requirements-gathering session, performs research using MCP-based tools (AWS documentation, pricing, Well-Architected Framework), designs production-ready networking and infrastructure, generates professional diagrams, and delivers a comprehensive architecture report with cost justification. The system uses Amazon Bedrock AgentCore with the Strands Agents SDK to orchestrate specialized agents through a structured workflow: Requirements Analysis → Clarification → Research → Architecture Design → Diagram Generation → Review → Final Report.

## Glossary

- **Orchestrator_Agent**: The top-level Strands agent that manages the overall workflow, routing between specialized agents and maintaining conversation state
- **Clarification_Agent**: The specialized agent responsible for conducting multi-turn conversational interviews to gather architectural requirements from the User
- **Research_Agent**: The specialized agent that queries external knowledge sources (AWS documentation, pricing data, Well-Architected guidance) via MCP tools
- **Design_Agent**: The specialized agent that produces the final architecture design including service selection, networking topology, security configuration, and cost estimates
- **Diagram_Agent**: The specialized agent responsible for generating professional Draw.io diagrams with AWS icons, VPC boundaries, and availability zone layouts
- **MCP_Server**: A Model Context Protocol server that exposes external tool capabilities to agents
- **AWS_Docs_MCP**: The MCP server providing access to AWS documentation, reference architectures, and service recommendations
- **Pricing_MCP**: The MCP server providing real-time AWS pricing data, service cost comparisons, and free tier information
- **DrawIO_MCP**: The MCP server that generates professional Draw.io diagrams with official AWS icon stencils
- **Session**: A complete end-to-end interaction from initial User prompt through final architecture delivery, persisted across multiple turns
- **Requirements_Profile**: The structured output of the clarification phase containing all gathered constraints, preferences, and non-functional requirements
- **Architecture_Report**: The final deliverable containing architecture design, rationale, cost analysis, security recommendations, Well-Architected review, and diagram
- **AgentCore**: Amazon Bedrock AgentCore, the managed runtime for deploying and observing Strands agents in production
- **Strands_SDK**: The Strands Agents SDK, a Python framework for building tool-using agents with structured reasoning
- **Well_Architected_Framework**: The AWS Well-Architected Framework providing best practices across six pillars: Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization, and Sustainability
- **VPC_Design**: A complete Virtual Private Cloud topology including CIDR blocks, subnets, route tables, gateways, and security controls
- **User**: A person interacting with the agentic system through the conversational interface

## Requirements

### Requirement 1: Multi-Turn Conversational Clarification

**User Story:** As a User, I want the system to ask me clarifying questions like a real AWS Solutions Architect, so that the generated architecture matches my actual requirements rather than making assumptions.

#### Acceptance Criteria

1. WHEN the User submits an initial system description, THE Clarification_Agent SHALL analyze the description and generate a set of clarifying questions covering: compute preference (serverless vs containers vs instances), budget constraints, compliance requirements, multi-region and disaster recovery needs, expected traffic patterns, storage requirements, authentication requirements, and high availability requirements.
2. WHEN the Clarification_Agent generates questions, THE Clarification_Agent SHALL omit questions whose answers are already explicitly stated in the User's initial description.
3. WHEN the User responds to clarifying questions, THE Clarification_Agent SHALL update the Requirements_Profile with the new information and determine whether additional clarification is needed.
4. WHEN the Clarification_Agent determines that sufficient requirements have been gathered, THE Clarification_Agent SHALL produce a structured Requirements_Profile and pass control to the Research_Agent.
5. IF the User indicates a desire to skip clarification (by responding with "skip", "just generate", or equivalent intent), THEN THE Clarification_Agent SHALL proceed with reasonable defaults based on the initial description and document all assumptions in the Requirements_Profile.
6. THE Clarification_Agent SHALL complete the clarification phase within a maximum of 5 question-answer rounds to avoid excessive back-and-forth.
7. WHEN the Clarification_Agent presents questions to the User, THE Clarification_Agent SHALL provide suggested default answers for each question to enable quick progression.

### Requirement 2: Session State and Conversation Memory

**User Story:** As a User, I want the system to remember my previous answers within a session, so that I do not need to repeat myself and can iterate on the architecture.

#### Acceptance Criteria

1. THE Orchestrator_Agent SHALL maintain a persistent Session object that stores the full conversation history, the current Requirements_Profile, the latest Architecture_Report, and the current workflow phase.
2. WHEN a new turn begins, THE Orchestrator_Agent SHALL provide the relevant Session context to the active agent so that previous answers and decisions are available.
3. WHEN the User requests modifications to a generated architecture (e.g., "make it serverless" or "add a caching layer"), THE Orchestrator_Agent SHALL route the request to the appropriate agent with the existing Architecture_Report as context.
4. IF the User's session is inactive for more than 30 minutes, THEN THE Orchestrator_Agent SHALL persist the Session state so the User can resume later.
5. THE Orchestrator_Agent SHALL assign a unique identifier to each Session and maintain an index of active sessions for the User.

### Requirement 3: AWS Documentation Research via MCP

**User Story:** As a User, I want the system to research AWS documentation and reference architectures before designing, so that the recommended architecture follows current best practices.

#### Acceptance Criteria

1. WHEN the Research_Agent receives a Requirements_Profile, THE Research_Agent SHALL query the AWS_Docs_MCP for reference architectures matching the workload type described in the requirements.
2. WHEN the Research_Agent identifies relevant AWS services, THE Research_Agent SHALL retrieve service-specific best practices and limitations from the AWS_Docs_MCP.
3. THE Research_Agent SHALL query the AWS_Docs_MCP for Well-Architected Framework guidance applicable to the requirements across all six pillars: Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization, and Sustainability.
4. WHEN the Research_Agent completes its queries, THE Research_Agent SHALL produce a Research_Summary containing: relevant reference architectures, applicable best practices, service recommendations with justification, and Well-Architected considerations.
5. IF the AWS_Docs_MCP is unavailable or returns an error, THEN THE Research_Agent SHALL proceed using the Design_Agent's built-in knowledge and document in the Architecture_Report that external documentation was unavailable.

### Requirement 4: AWS Pricing Research via MCP

**User Story:** As a User, I want the system to provide real pricing data for recommended services, so that I can make informed cost decisions.

#### Acceptance Criteria

1. WHEN the Research_Agent evaluates service options, THE Research_Agent SHALL query the Pricing_MCP for current pricing data for each candidate service in the User's specified region.
2. WHEN comparing alternative services (e.g., Lambda vs ECS vs EC2 for compute), THE Research_Agent SHALL retrieve pricing for all alternatives and produce a cost comparison table showing monthly estimates for the User's expected traffic.
3. THE Research_Agent SHALL query the Pricing_MCP for AWS Free Tier eligibility for each recommended service and include free tier benefits in the cost analysis.
4. WHEN the Research_Agent produces cost estimates, THE Research_Agent SHALL calculate monthly costs based on the traffic patterns and storage volumes specified in the Requirements_Profile.
5. IF the Pricing_MCP is unavailable or returns an error, THEN THE Research_Agent SHALL use approximate pricing estimates based on the Design_Agent's training data and clearly label them as estimates rather than live data.

### Requirement 5: Intelligent Service Selection and Justification

**User Story:** As a User, I want the system to make context-appropriate service choices and explain why, so that I understand the reasoning behind the architecture.

#### Acceptance Criteria

1. WHEN the Design_Agent selects services for the architecture, THE Design_Agent SHALL justify each service choice with at least one of: pricing data, performance characteristics, compliance fit, or Well-Architected alignment.
2. THE Design_Agent SHALL NOT default to the same service pattern for all workloads; THE Design_Agent SHALL select between serverless, container, and instance-based compute based on the traffic patterns, cost constraints, and cold-start tolerance specified in the Requirements_Profile.
3. WHEN the Requirements_Profile specifies budget constraints, THE Design_Agent SHALL optimize service selection to remain within the specified budget while documenting any capability trade-offs.
4. WHEN the Requirements_Profile indicates free tier eligibility is important, THE Design_Agent SHALL prioritize services with free tier coverage and document the free tier limits for each selected service.
5. THE Design_Agent SHALL produce an Architecture_Rationale section explaining the reasoning for each major design decision, including alternatives that were considered and why they were rejected.

### Requirement 6: Production-Ready Network Design

**User Story:** As a User, I want the system to design production-ready networking infrastructure, so that my architecture is secure and properly segmented from the start.

#### Acceptance Criteria

1. WHEN the Design_Agent produces an architecture that requires a VPC, THE Design_Agent SHALL include a complete VPC_Design with: CIDR block allocation, public and private subnets across multiple Availability Zones, Internet Gateway, NAT Gateway placement, and route table configuration.
2. WHEN the Design_Agent produces a VPC_Design, THE Design_Agent SHALL include Security Group rules for each service tier following the principle of least privilege, specifying allowed inbound and outbound ports and source restrictions.
3. WHEN the Design_Agent produces a VPC_Design, THE Design_Agent SHALL include Network ACL rules for subnet-level traffic control as an additional defense layer.
4. WHEN the architecture requires access to AWS services from private subnets, THE Design_Agent SHALL recommend VPC Endpoints (Gateway or Interface) for services that support them, specifying the cost benefit compared to NAT Gateway data processing charges.
5. IF the architecture is fully serverless (Lambda, API Gateway, DynamoDB, S3 only), THEN THE Design_Agent SHALL omit VPC design and document the rationale for not including one.
6. THE Design_Agent SHALL validate the VPC_Design against a checklist: no databases in public subnets, no overly permissive security groups (0.0.0.0/0 on non-public ports), NAT Gateway in each AZ for high availability, and appropriate CIDR sizing for future growth.
7. WHEN the Requirements_Profile specifies multi-region or disaster recovery, THE Design_Agent SHALL include cross-region networking components such as VPC Peering, Transit Gateway, or Global Accelerator as appropriate.

### Requirement 7: Professional Diagram Generation

**User Story:** As a User, I want professional architecture diagrams resembling official AWS reference architectures, so that I can use them in presentations and documentation.

#### Acceptance Criteria

1. WHEN the Diagram_Agent generates a diagram, THE Diagram_Agent SHALL produce a Draw.io XML file using official AWS architecture icon stencils for each service represented.
2. WHEN the architecture includes a VPC, THE Diagram_Agent SHALL render the diagram with nested boundaries showing: AWS Account → Region → VPC → Availability Zone → Subnet hierarchy.
3. WHEN the Diagram_Agent renders connections between services, THE Diagram_Agent SHALL use realistic routing paths showing traffic flow through load balancers, gateways, and network boundaries rather than direct point-to-point arrows.
4. THE Diagram_Agent SHALL generate the diagram as a downloadable .drawio file that opens correctly in Draw.io or diagrams.net.
5. THE Diagram_Agent SHALL generate a PNG rendering of the diagram for immediate viewing in the UI.
6. IF the DrawIO_MCP is unavailable, THEN THE Diagram_Agent SHALL fall back to local Draw.io XML generation using the existing Diagram_Renderer service and document the reduced quality.

### Requirement 8: Agent Orchestration Workflow

**User Story:** As a User, I want a structured workflow that produces consistent, high-quality results, so that every architecture generation follows a thorough process.

#### Acceptance Criteria

1. THE Orchestrator_Agent SHALL execute the following workflow phases in order: Requirements Analysis, Clarification, Research, Architecture Design, Diagram Generation, Architecture Review, and Final Report.
2. WHEN the Orchestrator_Agent transitions between phases, THE Orchestrator_Agent SHALL pass the accumulated context (Requirements_Profile, Research_Summary, or draft architecture) to the next agent.
3. WHEN the Architecture Review phase begins, THE Design_Agent SHALL validate the draft architecture against the Well-Architected Framework pillars and produce a review summary noting any violations or improvement opportunities.
4. WHEN the Final Report phase begins, THE Orchestrator_Agent SHALL compile all outputs into a single Architecture_Report containing: architecture design, service list with justification, VPC_Design (if applicable), security configuration, cost analysis with pricing data, Well-Architected review, recommendations, and diagram reference.
5. IF any phase fails due to a tool error, THEN THE Orchestrator_Agent SHALL retry the failed phase once, and if it fails again, proceed to the next phase with degraded output and document the limitation in the Architecture_Report.
6. THE Orchestrator_Agent SHALL separate reasoning (agent planning and decision-making) from tool execution (MCP calls and data retrieval) to maintain clear audit trails.

### Requirement 9: Strands Agents SDK Integration

**User Story:** As a developer, I want the system built on the Strands Agents SDK, so that agents have structured tool access, composable skills, and a standard execution model.

#### Acceptance Criteria

1. THE Orchestrator_Agent, Clarification_Agent, Research_Agent, Design_Agent, and Diagram_Agent SHALL each be implemented as Strands Agent instances with defined system prompts, tool bindings, and output schemas.
2. WHEN an agent requires external data, THE agent SHALL invoke tools registered via the Strands SDK tool interface rather than embedding external calls in the system prompt.
3. THE system SHALL define each MCP integration (AWS_Docs_MCP, Pricing_MCP, DrawIO_MCP) as a Strands tool binding with typed input and output schemas.
4. THE system SHALL organize agent capabilities into Strands Skills that can be composed and reused: a Clarification Skill, a Research Skill, a Network Design Skill, a Cost Analysis Skill, and a Diagram Skill.
5. WHEN the Strands SDK encounters an unrecoverable error during tool execution, THE system SHALL propagate the error to the Orchestrator_Agent with context about which tool failed and what was attempted.

### Requirement 10: Amazon Bedrock AgentCore Deployment

**User Story:** As a DevOps engineer, I want to deploy the agentic system on Amazon Bedrock AgentCore, so that I get managed hosting, scaling, and observability for the agents.

#### Acceptance Criteria

1. THE system SHALL package each agent (Orchestrator, Clarification, Research, Design, Diagram) as a deployable AgentCore unit with its Strands configuration, tool bindings, and system prompt.
2. THE system SHALL configure AgentCore to use Amazon Bedrock foundation models (Claude) as the underlying LLM for all agents.
3. WHEN deployed on AgentCore, THE system SHALL expose an API endpoint that accepts User prompts and returns streaming agent responses for the conversational interface.
4. THE system SHALL configure AgentCore session management to maintain Session state across multiple User interactions within the same architecture design workflow.
5. IF AgentCore is unavailable in the deployment region, THEN THE system SHALL support a fallback deployment mode using ECS Fargate with the Strands SDK running locally (without managed AgentCore features).

### Requirement 11: Observability and Tracing

**User Story:** As a DevOps engineer, I want full observability into agent execution, so that I can monitor performance, debug issues, and understand agent behavior in production.

#### Acceptance Criteria

1. THE system SHALL emit OpenTelemetry traces for each agent invocation, including: agent name, phase, duration, tool calls made, and token usage.
2. THE system SHALL integrate with AWS X-Ray for distributed tracing across the Orchestrator_Agent and all sub-agents within a single Session.
3. THE system SHALL send structured logs to CloudWatch Logs for each agent phase transition, tool invocation, and error event.
4. THE system SHALL expose a GenAI Observability dashboard showing: session timelines, tool invocation success rates, prompt execution durations, token consumption per session, and error rates.
5. WHEN a tool invocation (MCP call) takes longer than 10 seconds, THE system SHALL log a warning with the tool name, input parameters, and elapsed time.
6. THE system SHALL record the full prompt and response for each agent invocation in a trace span for debugging purposes, with an option to disable prompt logging in production for cost and privacy reasons.

### Requirement 12: Architecture Report Deliverables

**User Story:** As a User, I want a comprehensive final report with all architecture artifacts, so that I have everything needed to implement and present the design.

#### Acceptance Criteria

1. WHEN the workflow completes, THE Orchestrator_Agent SHALL produce an Architecture_Report containing: architecture overview, detailed service descriptions with justifications, networking topology, security configuration, cost analysis with pricing breakdown, Well-Architected review summary, and actionable recommendations.
2. THE Architecture_Report SHALL include a cost comparison section showing at least two alternative approaches (e.g., serverless vs container-based) with monthly cost estimates for the User's workload.
3. THE Architecture_Report SHALL include a security recommendations section covering: IAM least-privilege policies, encryption at rest and in transit, network segmentation rationale, and compliance alignment (if specified in Requirements_Profile).
4. THE Architecture_Report SHALL include a reference to the generated Draw.io diagram file and an inline PNG rendering.
5. IF the User's Requirements_Profile specifies infrastructure-as-code preference, THEN THE Architecture_Report SHALL include a Terraform or CDK code skeleton for the core infrastructure components.
6. THE Architecture_Report SHALL be exportable as a single Markdown document and as a structured JSON object conforming to a defined schema.

### Requirement 13: Conversational Interface

**User Story:** As a User, I want a chat-based interface for interacting with the agent, so that the experience feels natural and interactive.

#### Acceptance Criteria

1. THE Application SHALL replace the single text-area input with a chat interface displaying the full conversation history between the User and the Orchestrator_Agent.
2. WHEN an agent is processing, THE Application SHALL display a typing indicator and stream partial responses as they become available.
3. THE Application SHALL display the current workflow phase (Clarification, Research, Design, etc.) as a status indicator so the User knows what the system is doing.
4. WHEN the system generates a diagram or cost table, THE Application SHALL render the artifact inline in the conversation thread rather than only in separate tabs.
5. THE Application SHALL retain the tabbed results view for the final Architecture_Report, accessible after the workflow completes, in addition to the inline conversation display.
6. WHEN the User sends a message during the Research or Design phase, THE Application SHALL queue the message and deliver it to the agent at the next appropriate interaction point rather than interrupting the current phase.

### Requirement 14: Backward Compatibility and Migration

**User Story:** As an existing User, I want the new agentic mode to coexist with the current quick-generation mode, so that I can choose between a fast single-shot and a thorough agentic workflow.

#### Acceptance Criteria

1. THE Application SHALL provide two generation modes accessible from the UI: "Quick Generate" (existing single-shot behavior) and "Architect Mode" (new agentic workflow).
2. WHEN the User selects "Quick Generate", THE Application SHALL use the existing Prompt_Builder and Bedrock_Client pipeline without invoking any agents or MCP tools.
3. WHEN the User selects "Architect Mode", THE Application SHALL initiate the Orchestrator_Agent workflow beginning with the Clarification phase.
4. THE Application SHALL preserve all existing API interfaces (Bedrock_Client, Response_Parser, Diagram_Renderer) so that the Quick Generate mode continues to function without modification.
5. THE Application SHALL maintain the existing data model (Architecture_Model) for Quick Generate output and extend it with additional fields (rationale, well_architected_review, cost_comparison) for Architect Mode output.

