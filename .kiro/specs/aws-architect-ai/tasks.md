# Implementation Plan: AWS Architect AI

## Overview

This plan implements the AWS Architect AI Streamlit application from project scaffolding through deployment readiness. Tasks are ordered to build foundational layers first (models, config, utilities), then services, then UI pages, and finally infrastructure. Each task builds incrementally on previous work, ensuring no orphaned code.

## Tasks

- [x] 1. Set up project structure and dependencies
  - [x] 1.1 Create project scaffolding and install dependencies
    - Create the directory structure: `services/`, `models/`, `pages/`, `templates/`, `utils/`, `tests/unit/`, `tests/property/`, `tests/integration/`, `.streamlit/`, `infra/`
    - Create `__init__.py` files for `services/`, `models/`, `utils/`
    - Create `requirements.txt` with pinned versions: streamlit, boto3, pydantic, hypothesis, pytest, pytest-cov
    - Create `.env.example` with AWS_REGION, BEDROCK_MODEL_ID, AWS_PROFILE, LOG_LEVEL
    - Create `.gitignore` for Python projects (include .env, __pycache__, .terraform, etc.)
    - _Requirements: 11.3, 12.2_

  - [x] 1.2 Create Streamlit configuration and Docker setup
    - Create `.streamlit/config.toml` with server.address="0.0.0.0", server.port=8501, headless=true
    - Create `Dockerfile` using python:3.12-slim with health check on `/_stcore/health`
    - Create `app.py` entry point that configures the Streamlit app title and page icon
    - _Requirements: 11.1, 11.2, 11.5_

- [x] 2. Implement data models and configuration
  - [x] 2.1 Implement Pydantic architecture models
    - Create `models/architecture.py` with all Pydantic models: DiagramNode, DiagramConnection, ServiceDetail, SecurityConfig, ServiceCost, EstimatedCost, NetworkingConfig, ScalingConfig, MonitoringConfig, DiagramData, ArchitectureModel
    - All models must use Field descriptors with proper types and defaults
    - Include CostSummary model for formatted display data
    - _Requirements: 3.2, 12.3, 12.4, 13.1_

  - [x] 2.2 Write property test for Architecture model round-trip
    - **Property 4: Architecture model serialization round-trip**
    - Test that any valid ArchitectureModel serialized to JSON and parsed back produces an equal object
    - Use hypothesis-pydantic or custom strategies to generate valid ArchitectureModel instances
    - **Validates: Requirements 3.5**

  - [x] 2.3 Implement application configuration and custom exceptions
    - Create `utils/config.py` with AppConfig Pydantic model and `load_config()` function
    - Load from environment variables: AWS_REGION (required), BEDROCK_MODEL_ID (required), AWS_PROFILE (optional), LOG_LEVEL (optional, default INFO)
    - Raise ConfigurationError if required variables are missing
    - Create custom exception hierarchy in `services/__init__.py` or a dedicated exceptions module: ArchitectAIError, BedrockConnectionError, BedrockThrottlingError, BedrockTimeoutError, JsonExtractionError, DiagramRenderError, ConfigurationError
    - _Requirements: 8.4, 8.5, 7.4_

  - [x] 2.4 Implement structured JSON logging
    - Create `utils/logging.py` with `setup_logging(log_level)` function
    - Configure JSON-formatted output to stdout with fields: timestamp, level, logger, message
    - Support LOG_LEVEL environment variable, default to INFO
    - Ensure no credentials or sensitive data are logged
    - _Requirements: 14.1, 14.4, 14.5, 14.6_

  - [x] 2.5 Write property test for structured JSON log output
    - **Property 10: Log formatter produces valid structured JSON**
    - Test that for any log message and level, output parses as valid JSON with required keys
    - **Validates: Requirements 14.1**

- [x] 3. Implement core services
  - [x] 3.1 Implement prompt builder service
    - Create `templates/architecture_prompt.md` with the prompt template requesting all required fields
    - Create `services/prompt_builder.py` with `build_prompt(system_description: str) -> str`
    - The prompt must include the system description verbatim and request all required JSON response fields
    - Include type hints and docstrings
    - _Requirements: 2.1, 12.3, 12.5_

  - [x] 3.2 Write property test for prompt builder completeness
    - **Property 2: Prompt builder includes all required elements**
    - Test that for any non-empty description, the prompt contains the description and all required field names
    - **Validates: Requirements 2.1**

  - [x] 3.3 Implement Bedrock client service
    - Create `services/bedrock.py` with `get_bedrock_client()` (cached with lru_cache) and `invoke_model()`
    - Implement 60-second timeout handling
    - Map boto3 exceptions to custom exceptions: BedrockConnectionError, BedrockThrottlingError, BedrockTimeoutError
    - Log requests at INFO level with timestamp, model ID, and request size
    - _Requirements: 2.2, 2.4, 2.6, 14.2_

  - [x] 3.4 Implement response parser service
    - Create `services/parser.py` with `extract_json(response_text: str) -> str` and `parse_architecture(json_str: str) -> ArchitectureModel`
    - Extract JSON by finding outermost matching curly braces
    - Validate against ArchitectureModel using Pydantic
    - Raise JsonExtractionError if no JSON found, return ValidationError details for schema mismatches
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 3.5 Write property test for JSON extraction
    - **Property 3: JSON extraction from wrapped text**
    - Test that any valid JSON embedded in arbitrary prefix/suffix text is correctly extracted
    - **Validates: Requirements 3.1**

  - [x] 3.6 Write property test for whitespace-only input rejection
    - **Property 1: Whitespace-only input is always rejected**
    - Test that any string of only whitespace characters is rejected by validation
    - Use hypothesis strategy generating whitespace-only strings
    - **Validates: Requirements 1.3**

- [x] 4. Checkpoint - Core services verification
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement diagram and export services
  - [x] 5.1 Implement diagram renderer service
    - Create `services/diagram.py` with `to_mermaid()`, `to_drawio_xml()`, and `parse_mermaid()` functions
    - `to_mermaid`: Convert DiagramNode/DiagramConnection lists to Mermaid flowchart syntax
    - `to_drawio_xml`: Convert to well-formed mxGraphModel XML with mxCell elements
    - `parse_mermaid`: Parse Mermaid code back into nodes and connections for round-trip verification
    - Skip connections referencing non-existent node IDs (log warning)
    - Return empty output for empty node lists without error
    - All conversions are local, no LLM calls
    - _Requirements: 5.1, 5.2, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_

  - [x] 5.2 Write property test for Mermaid generation validity
    - **Property 5: Mermaid generation produces parseable syntax**
    - Test that for any valid nodes/connections, output contains flowchart directive, node definitions, and link statements
    - **Validates: Requirements 5.1, 13.2**

  - [x] 5.3 Write property test for Draw.io XML validity
    - **Property 6: Draw.io XML generation produces well-formed XML**
    - Test that output parses as XML with mxGraphModel root and correct mxCell counts
    - **Validates: Requirements 5.2, 13.3**

  - [x] 5.4 Write property test for Mermaid round-trip
    - **Property 7: Mermaid conversion round-trip preserves structure**
    - Test that to_mermaid → parse_mermaid preserves all node IDs, labels, and connections
    - **Validates: Requirements 13.5**

  - [x] 5.5 Implement cost formatting service
    - Create `services/cost.py` with `format_cost_summary(estimated_cost: EstimatedCost) -> CostSummary`
    - Format total monthly cost and per-service breakdown for display
    - _Requirements: 4.5, 12.6_

  - [x] 5.6 Implement export utilities
    - Create `utils/export.py` with `sanitize_filename()` and `generate_export_filename()`
    - Replace spaces and special characters with underscores
    - Handle empty/whitespace-only titles with a fallback
    - Generate filenames in format: `{sanitized_title}_{format}.{extension}`
    - _Requirements: 6.5_

  - [x] 5.7 Write property test for filename sanitization
    - **Property 8: Filename sanitization produces valid filenames**
    - Test that output contains only safe characters, ends with correct format, and is never empty
    - **Validates: Requirements 6.5**

- [x] 6. Implement Streamlit UI pages
  - [x] 6.1 Implement Generator page with sidebar controls
    - Create `pages/1_Generator.py` with full generation workflow
    - Sidebar: provider selector (default Bedrock), model dropdown (default Claude Sonnet 4), temperature slider (0.0-1.0, step 0.1, default 1.0), Generate button
    - Main area: multi-line text input (max 5000 chars) with validation
    - Input validation: reject empty/whitespace-only input, reject >5000 chars
    - Show loading indicator during generation
    - Preserve user input in session_state across errors
    - Wire together: validate → prompt_builder → bedrock → parser → diagram_renderer → display
    - _Requirements: 1.1, 1.2, 1.3, 2.3, 2.5, 8.1, 8.2, 8.3_

  - [x] 6.2 Implement results display with tabbed sections
    - Display results in tabs: Overview, Diagram, AWS Services, Security, Cost, Exports
    - Overview tab: title as heading, summary as body text
    - Diagram tab: radio button for Mermaid/Draw.io mode (default Mermaid), render diagram, copyable text area for Draw.io XML, download button for XML
    - AWS Services tab: table/list with service name and role
    - Security tab: IAM policies, encryption, CloudTrail, WAF rules, recommendations
    - Cost tab: prominent total cost figure + per-service breakdown table
    - Exports tab: download buttons for .mmd, .drawio, .json, .png formats
    - Show "no data available" message for empty sections
    - Handle diagram generation failure gracefully (show error, retain other tabs)
    - Disable PNG button with tooltip if PNG export fails
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.3, 5.4, 5.5, 5.6, 5.7, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 6.3 Implement error handling in Generator page
    - Catch BedrockConnectionError: display connection failure message, preserve input
    - Catch BedrockThrottlingError: display throttling message with 5s wait suggestion
    - Catch JsonExtractionError/ValidationError: display parse error with retry button
    - Catch unhandled exceptions: log full details, show generic message, preserve input
    - Provide retry button that resubmits original input
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 6.4 Implement History page
    - Create `pages/2_History.py`
    - Display list of previous generations in sidebar, most recent first
    - Show architecture title for each entry
    - On selection, load and display architecture in same tabbed format
    - Show "no history available" message when session has no generations
    - _Requirements: 9.3, 10.1, 10.2, 10.3, 10.4_

  - [x] 6.5 Write property test for session history ordering
    - **Property 9: Session history maintains reverse-chronological order**
    - Test that appending architectures maintains most-recent-first ordering
    - **Validates: Requirements 10.1, 10.2**

  - [x] 6.6 Implement Settings page
    - Create `pages/3_Settings.py`
    - Display read-only fields for AWS_REGION, BEDROCK_MODEL_ID, LOG_LEVEL
    - _Requirements: 9.4_

- [x] 7. Checkpoint - Application integration verification
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement Terraform infrastructure
  - [x] 8.1 Create Terraform root module and variables
    - Create `infra/main.tf` with AWS provider configuration and module references
    - Create `infra/variables.tf` with: aws_region, project_name, bedrock_model_id, container_cpu, container_memory, log_level, certificate_arn
    - Create `infra/outputs.tf` with: alb_dns_name, ecr_repository_url, ecs_cluster_name, ecs_service_name
    - Create `infra/terraform.tfvars.example` with sample values
    - _Requirements: 11.1_

  - [x] 8.2 Implement Terraform networking module
    - Create `infra/modules/networking/` with main.tf, variables.tf, outputs.tf
    - VPC with public and private subnets across 2 AZs
    - NAT Gateway for private subnet internet access
    - Security groups: ALB (inbound 80/443), ECS tasks (inbound from ALB on 8501)
    - _Requirements: 11.1_

  - [x] 8.3 Implement Terraform ECR module
    - Create `infra/modules/ecr/` with main.tf, variables.tf, outputs.tf
    - ECR repository for Docker images
    - Lifecycle policy to retain last 5 images
    - _Requirements: 11.1_

  - [x] 8.4 Implement Terraform IAM module
    - Create `infra/modules/iam/` with main.tf, variables.tf, outputs.tf
    - ECS Task Execution Role: ECR pull, CloudWatch Logs permissions
    - ECS Task Role: bedrock:InvokeModel scoped to configured model
    - _Requirements: 8.4, 11.1_

  - [x] 8.5 Implement Terraform ALB module
    - Create `infra/modules/alb/` with main.tf, variables.tf, outputs.tf
    - ALB in public subnets with target group (health check on /_stcore/health)
    - HTTP listener on port 80
    - Optional HTTPS listener on port 443 (if certificate_arn provided)
    - _Requirements: 11.5_

  - [x] 8.6 Implement Terraform ECS module
    - Create `infra/modules/ecs/` with main.tf, variables.tf, outputs.tf
    - ECS Cluster with Fargate capacity provider
    - Task Definition: 512 CPU, 1024 MB memory, port 8501, environment variables, awslogs driver
    - ECS Service: desired count 1, rolling update, private subnets, ALB target group
    - Health check configuration
    - _Requirements: 11.1, 11.5, 11.6, 14.4_

- [x] 9. Create documentation and finalize
  - [x] 9.1 Create README and project documentation
    - Create `README.md` with: project overview, prerequisites (Python 3.12, Docker, AWS CLI, Terraform), local setup instructions, environment variable configuration, Docker build and run commands, ECS Fargate deployment steps, architecture diagram
    - _Requirements: 11.4_

  - [x] 9.2 Write integration tests
    - Create `tests/conftest.py` with shared fixtures (sample ArchitectureModel instances, mocked boto3 clients)
    - Create `tests/integration/test_bedrock_integration.py` testing request structure with mocked boto3
    - Create `tests/integration/test_end_to_end.py` testing full flow: input → prompt → mocked response → parsed result → diagram
    - _Requirements: 12.1_

- [x] 10. Final checkpoint - Full system verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 10 universal correctness properties defined in the design
- Unit tests validate specific examples and edge cases
- Python is used throughout (Streamlit, Pydantic, Hypothesis, pytest, boto3, Terraform)
- The one-way dependency rule (pages/ → services/ → models/) must be maintained at all times

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4"] },
    { "id": 3, "tasks": ["2.5", "3.1", "3.3"] },
    { "id": 4, "tasks": ["3.2", "3.4", "5.6"] },
    { "id": 5, "tasks": ["3.5", "3.6", "5.1", "5.5", "5.7"] },
    { "id": 6, "tasks": ["5.2", "5.3", "5.4"] },
    { "id": 7, "tasks": ["6.1", "6.4", "6.6"] },
    { "id": 8, "tasks": ["6.2", "6.3", "6.5"] },
    { "id": 9, "tasks": ["8.1"] },
    { "id": 10, "tasks": ["8.2", "8.3", "8.4"] },
    { "id": 11, "tasks": ["8.5", "8.6"] },
    { "id": 12, "tasks": ["9.1", "9.2"] }
  ]
}
```
