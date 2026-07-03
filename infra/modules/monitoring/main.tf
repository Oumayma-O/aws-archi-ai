locals {
  log_group_name = "/ecs/${var.project_name}"
}

resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = "${var.project_name}-agentic-observability"

  dashboard_body = jsonencode({
    widgets = [
      # --- Row 1: Agent Invocations per Phase ---
      {
        type   = "log"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Agent Invocations (Count per Phase)"
          region = "us-east-1"
          query  = "SOURCE '${local.log_group_name}' | fields @timestamp, phase, agent_name | filter ispresent(phase) | stats count(*) as invocations by phase | sort invocations desc"
          view   = "bar"
        }
      },
      # --- Row 1: Error Rate per Agent ---
      {
        type   = "log"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Error Rate per Agent"
          region = "us-east-1"
          query  = "SOURCE '${local.log_group_name}' | fields @timestamp, agent_name, level | filter ispresent(agent_name) | stats count(*) as total, sum(level = 'ERROR') as errors by agent_name | display agent_name, errors, total, (errors / total * 100) as error_pct"
          view   = "table"
        }
      },
      # --- Row 2: Average Duration per Phase ---
      {
        type   = "log"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Average Duration per Phase (ms)"
          region = "us-east-1"
          query  = "SOURCE '${local.log_group_name}' | fields @timestamp, phase, duration_ms | filter ispresent(duration_ms) and ispresent(phase) | stats avg(duration_ms) as avg_duration, max(duration_ms) as max_duration, p95(duration_ms) as p95_duration by phase"
          view   = "table"
        }
      },
      # --- Row 2: MCP Tool Call Success/Failure Rates ---
      {
        type   = "log"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "MCP Tool Call Success/Failure Rates"
          region = "us-east-1"
          query  = "SOURCE '${local.log_group_name}' | fields @timestamp, tool_name, tool_status | filter ispresent(tool_name) | stats count(*) as total, sum(tool_status = 'success') as successes, sum(tool_status = 'error') as failures by tool_name"
          view   = "table"
        }
      },
      # --- Row 3: Token Usage Over Time ---
      {
        type   = "log"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "Token Usage Over Time"
          region = "us-east-1"
          query  = "SOURCE '${local.log_group_name}' | fields @timestamp, session_id, input_tokens, output_tokens | filter ispresent(input_tokens) | stats sum(input_tokens) as total_input_tokens, sum(output_tokens) as total_output_tokens by bin(5m)"
          view   = "timeSeries"
        }
      },
      # --- Row 3: Token Consumption per Session ---
      {
        type   = "log"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "Token Consumption per Session"
          region = "us-east-1"
          query  = "SOURCE '${local.log_group_name}' | fields @timestamp, session_id, input_tokens, output_tokens | filter ispresent(session_id) and ispresent(input_tokens) | stats sum(input_tokens) as total_input, sum(output_tokens) as total_output, sum(input_tokens + output_tokens) as total_tokens by session_id | sort total_tokens desc | limit 20"
          view   = "table"
        }
      },
      # --- Row 4: Session Timelines ---
      {
        type   = "log"
        x      = 0
        y      = 18
        width  = 24
        height = 6
        properties = {
          title  = "Session Timelines (Phase Transitions)"
          region = "us-east-1"
          query  = "SOURCE '${local.log_group_name}' | fields @timestamp, session_id, phase, event_type | filter event_type = 'phase_transition' | sort @timestamp asc | limit 100"
          view   = "table"
        }
      },
      # --- Row 5: Prompt Execution Durations (Histogram) ---
      {
        type   = "log"
        x      = 0
        y      = 24
        width  = 12
        height = 6
        properties = {
          title  = "Prompt Execution Durations"
          region = "us-east-1"
          query  = "SOURCE '${local.log_group_name}' | fields @timestamp, agent_name, duration_ms | filter ispresent(duration_ms) and ispresent(agent_name) | stats avg(duration_ms) as avg_ms, p50(duration_ms) as p50_ms, p95(duration_ms) as p95_ms, max(duration_ms) as max_ms by bin(5m)"
          view   = "timeSeries"
        }
      },
      # --- Row 5: Recent Errors ---
      {
        type   = "log"
        x      = 12
        y      = 24
        width  = 12
        height = 6
        properties = {
          title  = "Recent Errors"
          region = "us-east-1"
          query  = "SOURCE '${local.log_group_name}' | fields @timestamp, agent_name, phase, @message | filter level = 'ERROR' | sort @timestamp desc | limit 20"
          view   = "table"
        }
      }
    ]
  })

}
