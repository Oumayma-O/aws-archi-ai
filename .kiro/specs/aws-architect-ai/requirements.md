# Requirements Document

## Introduction

AWS Architect AI is a production-quality Streamlit application that serves as a small architect copilot. It generates production-ready AWS architectures from natural language descriptions, visualizes them as diagrams, explains design decisions, estimates costs, and exports the architecture in multiple formats. The application is fully AWS-native, using Amazon Bedrock (Claude Sonnet) for generation and deploying on ECS Fargate.

## Glossary

- **Application**: The AWS Architect AI Streamlit web application
- **Generator**: The main page component responsible for orchestrating architecture generation from user input
- **Bedrock_Client**: The service module that communicates with Amazon Bedrock API using boto3
- **Prompt_Builder**: The service module that constructs structured prompts for the LLM from user input
- **Response_Parser**: The service module that extracts and validates structured JSON from LLM responses
- **Diagram_Renderer**: The service module that converts architecture JSON into Mermaid code and Draw.io XML
- **Cost_Estimator**: The component within the LLM response that provides estimated monthly costs broken down by service
- **Architecture_Model**: The Pydantic model defining the structure of a generated architecture response
- **User**: A person interacting with the application through the Streamlit UI
- **System_Description**: The natural language text entered by the User describing desired infrastructure
- **Architecture_JSON**: The structured JSON object returned by the LLM containing all architecture details
- **Mermaid_Code**: A text-based diagram definition in Mermaid syntax generated from Architecture_JSON
- **DrawIO_XML**: An XML document in Draw.io format generated locally from Architecture_JSON

## Requirements

### Requirement 1: Natural Language Input

**User Story:** As a User, I want to enter a natural language description of my system, so that I can generate an AWS architecture without manual design work.

#### Acceptance Criteria

1. THE Application SHALL display a multi-line text input field on the Generator page for the User to enter a System_Description, with a maximum length of 5000 characters.
2. WHEN the User clicks the "Generate" button, THE Generator SHALL send the System_Description to the Prompt_Builder for processing.
3. IF the System_Description is empty or contains only whitespace characters, THEN THE Application SHALL display a validation message on the Generator page indicating that a description is required, and SHALL NOT send the input to the Prompt_Builder.

### Requirement 2: LLM Architecture Generation

**User Story:** As a User, I want the application to generate a complete AWS architecture from my description, so that I receive production-ready infrastructure designs.

#### Acceptance Criteria

1. WHEN the Prompt_Builder receives a System_Description, THE Prompt_Builder SHALL construct a prompt requesting a structured JSON response containing: title, summary, architecture_description, aws_services, networking, security, scaling, monitoring, estimated_cost, mermaid_diagram, drawio_xml, and recommendations.
2. WHEN a prompt is constructed, THE Bedrock_Client SHALL send the prompt to Amazon Bedrock using the model identified by the BEDROCK_MODEL_ID environment variable.
3. WHILE the Bedrock_Client is awaiting a response, THE Application SHALL display a loading indicator to the User.
4. THE Bedrock_Client SHALL cache the boto3 Bedrock runtime client instance to avoid repeated initialization across generation requests within the same session.
5. IF the System_Description exceeds 5000 characters, THEN THE Application SHALL display a validation error and SHALL NOT submit the request to the Bedrock_Client.
6. IF the Bedrock_Client does not receive a response within 60 seconds, THEN THE Bedrock_Client SHALL abort the request and return a timeout error to the Application.

### Requirement 3: Response Parsing and Validation

**User Story:** As a User, I want the LLM response to be reliably parsed, so that I always see well-structured architecture information.

#### Acceptance Criteria

1. WHEN the Bedrock_Client receives a response, THE Response_Parser SHALL extract JSON content by locating the first complete JSON object (delimited by the outermost matching curly braces) within the LLM response text, ignoring any non-JSON text before or after it.
2. WHEN JSON is extracted, THE Response_Parser SHALL validate the JSON against the Architecture_Model using Pydantic, confirming that all required fields (title, summary, architecture_description, aws_services, networking, security, scaling, monitoring, estimated_cost, mermaid_diagram, drawio_xml, and recommendations) are present and conform to their defined types.
3. IF the LLM response does not contain a complete JSON object (no matching curly braces found), THEN THE Response_Parser SHALL return an error message to the Application indicating that no JSON structure was found in the response.
4. IF the JSON does not conform to the Architecture_Model schema, THEN THE Response_Parser SHALL return a validation error to the Application specifying each field that is missing or fails type validation.
5. THE Response_Parser SHALL guarantee that for any valid Architecture_Model instance, serializing to JSON via Pydantic and parsing the resulting JSON back into an Architecture_Model produces a field-by-field equal object.

### Requirement 4: Architecture Display

**User Story:** As a User, I want to view the generated architecture in organized sections, so that I can understand different aspects of the design.

#### Acceptance Criteria

1. WHEN a valid Architecture_JSON is available, THE Application SHALL display the results in tabbed sections: Overview, Diagram, AWS Services, Security, Cost, and Exports.
2. THE Application SHALL display the architecture title as a heading and the summary as body text in the Overview tab.
3. THE Application SHALL display the list of AWS services as a table or list with each service name and its role description in the AWS Services tab.
4. THE Application SHALL display security details including IAM policies, encryption settings, CloudTrail configuration, WAF rules, and security recommendations in the Security tab.
5. THE Application SHALL display the estimated monthly total cost as a prominent figure and a per-service breakdown showing service name and estimated monthly cost in the Cost tab.
6. IF any section data is absent or empty in the Architecture_JSON, THEN THE Application SHALL display a message indicating that no data is available for that section rather than showing an empty tab.

### Requirement 5: Diagram Visualization

**User Story:** As a User, I want to see a visual diagram of the architecture, so that I can understand the system layout at a glance.

#### Acceptance Criteria

1. WHEN a valid Architecture_JSON is available, THE Diagram_Renderer SHALL generate syntactically valid Mermaid_Code from the nodes and connections in the Architecture_JSON.
2. WHEN a valid Architecture_JSON is available, THE Diagram_Renderer SHALL generate well-formed DrawIO_XML from the nodes and connections in the Architecture_JSON locally without calling the LLM.
3. WHEN Mermaid_Code is available and the Mermaid visualization mode is selected, THE Application SHALL render the Mermaid_Code as a graphical diagram in the Diagram tab using a Mermaid-compatible code block.
4. WHEN Draw.io visualization mode is selected, THE Application SHALL display the DrawIO_XML content in a copyable text area and provide a download button for the XML file in the Diagram tab.
5. THE Application SHALL provide a radio button or selectbox in the Diagram tab allowing the User to switch between Mermaid and Draw.io visualization modes, defaulting to Mermaid on initial load.
6. WHEN the User switches visualization mode, THE Application SHALL display the corresponding diagram format using the previously generated output without regenerating from the LLM.
7. IF the Diagram_Renderer fails to generate Mermaid_Code or DrawIO_XML, THEN THE Application SHALL display an error message indicating the diagram generation failure in the Diagram tab and retain any successfully generated format for display.

### Requirement 6: Architecture Export

**User Story:** As a User, I want to download the architecture in multiple formats, so that I can use it in other tools and documentation.

#### Acceptance Criteria

1. THE Application SHALL provide a download button for the Mermaid_Code as a .mmd text file in the Exports tab.
2. THE Application SHALL provide a download button for the DrawIO_XML as a .drawio XML file in the Exports tab.
3. THE Application SHALL provide a download button for the full Architecture_JSON as a .json file in the Exports tab.
4. THE Application SHALL provide a download button for the diagram as a .png image file in the Exports tab.
5. WHEN the User clicks a download button, THE Application SHALL initiate a browser file download with a filename in the format "{sanitized_title}_{format}.{extension}" where sanitized_title replaces spaces and special characters with underscores.
6. IF PNG generation fails, THEN THE Application SHALL disable the PNG download button and display a tooltip or message indicating that PNG export is currently unavailable.

### Requirement 7: Error Handling

**User Story:** As a User, I want the application to handle failures gracefully, so that I understand what went wrong and can retry.

#### Acceptance Criteria

1. IF the Bedrock_Client fails to connect to Amazon Bedrock, THEN THE Application SHALL display an error message indicating the connection failure and retain the User's most recent input so the User can retry without re-entering it.
2. IF the Bedrock_Client receives a throttling response, THEN THE Application SHALL display a message indicating the request was throttled and asking the User to retry after waiting at least 5 seconds.
3. IF the LLM returns a response that the Response_Parser cannot extract a valid answer from, THEN THE Response_Parser SHALL display an error message describing that the response could not be processed and provide a retry option that resubmits the User's original input.
4. IF an unhandled exception occurs, THEN THE Application SHALL log the error type, message, and stack trace, and display a non-specific error message to the User indicating that an unexpected error occurred without exposing internal details.
5. IF any error defined in criteria 1 through 4 occurs, THEN THE Application SHALL preserve the User's current input so that the User can retry the failed operation without re-entering data.

### Requirement 8: Configuration and Model Selection

**User Story:** As a User, I want to configure generation parameters, so that I can control the model behavior and output quality.

#### Acceptance Criteria

1. THE Application SHALL display a sidebar containing a provider selector defaulting to Amazon Bedrock, a model selection dropdown defaulting to Claude Sonnet 4, a temperature slider with a range of 0.0 to 1.0 in increments of 0.1 defaulting to 1.0, and the Generate button.
2. THE Application SHALL default the provider to Amazon Bedrock.
3. WHEN the User adjusts the temperature slider, THE Bedrock_Client SHALL use the selected temperature value (between 0.0 and 1.0 inclusive) for the next generation request.
4. THE Application SHALL load configuration from the environment variables AWS_REGION (required), BEDROCK_MODEL_ID (required), and AWS_PROFILE (optional), and SHALL NOT contain hardcoded credentials.
5. IF a required environment variable (AWS_REGION or BEDROCK_MODEL_ID) is not set, THEN THE Application SHALL display an error message indicating which variable is missing and SHALL NOT proceed with generation requests.

### Requirement 9: Multi-Page Navigation

**User Story:** As a User, I want to navigate between different pages, so that I can access generation, history, and settings separately.

#### Acceptance Criteria

1. THE Application SHALL provide three navigable pages: Generator (1_Generator.py), History (2_History.py), and Settings (3_Settings.py), using Streamlit's built-in multi-page directory convention.
2. THE Application SHALL default to the Generator page when first loaded.
3. WHEN the User navigates to the History page, THE Application SHALL display a list of previously generated architectures from the current session.
4. WHEN the User navigates to the Settings page, THE Application SHALL display the current AWS_REGION, BEDROCK_MODEL_ID, and LOG_LEVEL configuration values as read-only fields.

### Requirement 10: Generation History

**User Story:** As a User, I want to review my previously generated architectures, so that I can compare designs or retrieve past work.

#### Acceptance Criteria

1. WHEN an architecture is successfully generated, THE Application SHALL append the Architecture_JSON to the session-based history list stored in st.session_state.
2. THE Application SHALL display a list of previous generations in the sidebar ordered by most recent first, showing the architecture title from the Architecture_Model.title field.
3. WHEN the User selects a previous generation from the sidebar, THE Application SHALL load and display that architecture in the main content area using the same tabbed format as a new generation.
4. IF no architectures have been generated in the current session, THEN THE Application SHALL display a message in the sidebar indicating that no history is available.

### Requirement 11: Deployment Readiness

**User Story:** As a DevOps engineer, I want the application to be containerized and deployment-ready, so that I can deploy it to AWS ECS Fargate.

#### Acceptance Criteria

1. THE Application SHALL include a Dockerfile using python:3.12-slim as the base image that builds a container image exposing port 8501.
2. THE Application SHALL include a .streamlit/config.toml file configuring server.address as "0.0.0.0" and server.port as 8501.
3. THE Application SHALL include a requirements.txt file listing all Python dependencies with pinned versions.
4. THE Application SHALL include a README.md documenting: project overview, prerequisites, local setup instructions, environment variable configuration, Docker build and run commands, and ECS Fargate deployment steps.
5. THE Application SHALL include a health check endpoint or mechanism compatible with ECS Fargate task health checks.
6. THE Application SHALL write all logs to stdout to ensure compatibility with the awslogs log driver for CloudWatch Logs on ECS Fargate.

### Requirement 12: Code Architecture

**User Story:** As a developer, I want the codebase to follow clean architecture principles, so that the application is maintainable and extensible.

#### Acceptance Criteria

1. THE Application SHALL enforce a one-way dependency rule where the services/ and models/ modules do not import from the pages/ module.
2. THE Application SHALL organize code into: services/ (bedrock.py, prompt_builder.py, parser.py, diagram.py, cost.py), models/ (architecture.py), templates/ (architecture_prompt.md), pages/, and utils/ directories.
3. THE Application SHALL use Python type hints on all function parameters and return types for every function and method definition.
4. THE Application SHALL use Pydantic models for all data structures passed as arguments or returned between functions in different modules.
5. THE Application SHALL include docstrings on all public functions (not prefixed with underscore) and classes, containing at minimum a one-line summary of the function or class purpose.
6. THE Application SHALL ensure that each file in the services/ directory contains only functions and classes related to a single responsibility as indicated by its filename.

### Requirement 13: Diagram JSON-to-Format Conversion

**User Story:** As a User, I want diagrams generated locally from structured data rather than raw LLM output, so that diagrams are consistent and reliable.

#### Acceptance Criteria

1. WHEN the LLM generates an architecture, THE LLM response SHALL include a structured JSON representation of diagram nodes and connections, where each node contains an id, a label, and an aws_service type, and each connection contains a source_id, a target_id, and an optional label.
2. WHEN the Diagram_Renderer receives diagram nodes and connections, THE Diagram_Renderer SHALL convert the structure into Mermaid_Code that is parseable by a Mermaid renderer without syntax errors, using flowchart syntax with one node definition per node and one link statement per connection.
3. WHEN the Diagram_Renderer receives diagram nodes and connections, THE Diagram_Renderer SHALL convert the structure into DrawIO_XML that is well-formed XML conforming to mxGraphModel structure, containing one mxCell element per node and one mxCell edge element per connection.
4. THE Diagram_Renderer SHALL perform all format conversions locally without additional LLM calls.
5. FOR ALL valid diagram node-and-connection structures, converting to Mermaid_Code and parsing the Mermaid_Code back into nodes and connections SHALL preserve all node ids, labels, and all connections between them (round-trip property).
6. IF the Diagram_Renderer receives a node-and-connection structure where a connection references a source_id or target_id that does not exist in the nodes list, THEN THE Diagram_Renderer SHALL omit that connection from the output and include a warning in the application log.
7. IF the Diagram_Renderer receives an empty nodes list, THEN THE Diagram_Renderer SHALL return empty Mermaid_Code and empty DrawIO_XML without raising an error.

### Requirement 14: Logging and Observability

**User Story:** As a DevOps engineer, I want structured logging throughout the application, so that I can monitor and debug issues in production.

#### Acceptance Criteria

1. THE Application SHALL use Python's logging module with JSON-formatted structured log output containing timestamp, level, logger name, and message fields.
2. WHEN the Bedrock_Client sends a request, THE Application SHALL log a message at INFO level including the timestamp, model identifier, and request size.
3. WHEN an error occurs, THE Application SHALL log the error at ERROR level with the error type, message, and stack trace.
4. THE Application SHALL write all logs to stdout for compatibility with CloudWatch Logs on ECS Fargate.
5. THE Application SHALL support configuring the log level via a LOG_LEVEL environment variable, defaulting to INFO if not set.
6. THE Application SHALL NOT log any AWS credentials, session tokens, or sensitive user input content in log messages.
