#!/usr/bin/env bash
# ============================================================================
# enable-observability.sh — turn on AgentCore-native observability for the
# whole AWS account in this region.
#
# AgentCore Runtime already emits OTel traces from inside each runtime (the
# `opentelemetry-instrument` CMD wrapper in Dockerfile.agentcore). Two
# account-level X-Ray settings control how those traces are stored/indexed:
#
#   1. Trace segment destination = CloudWatchLogs
#      Sends spans to CloudWatch Logs (Transaction Search) instead of the
#      legacy X-Ray store. Required for the GenAI Observability dashboard
#      and the per-session timeline view.
#
#   2. Indexing rule = 100%
#      Default sampling indexes ~5% of spans. For a low-traffic agent
#      pipeline you want everything indexed so every invocation is queryable.
#
# Both settings are account-and-region scoped (NOT per-runtime), so this
# script only needs to run once per account/region. Idempotent.
#
# Usage:
#   AWS_REGION=eu-west-1 ./scripts/enable-observability.sh
#
# Pricing note: CloudWatch Logs ingestion is billed per GB; for a handful
# of runs/day during dev this is well under $1/month.
# ============================================================================
set -euo pipefail
: "${AWS_REGION:?AWS_REGION is required}"
for bin in aws jq; do
  command -v "${bin}" >/dev/null 2>&1 || { echo "ERROR: ${bin} not on PATH" >&2; exit 1; }
done
step() { echo; echo "▸ $1"; }
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# ----------------------------------------------------------------------------
# 0. CloudWatch Logs resource policy — grant the X-Ray service principal
#    write access to BOTH aws/spans (raw spans) and
#    /aws/application-signals/data (Application Signals aggregates).
#    Without both, UpdateTraceSegmentDestination fails with AccessDenied.
# ----------------------------------------------------------------------------
step "Ensuring X-Ray can write spans to CloudWatch Logs"
POLICY_NAME="AWSServiceRoleForXRay-AgentCoreSpans"
POLICY_DOC=$(jq -n --arg account "${ACCOUNT_ID}" --arg region "${AWS_REGION}" '
  {
    Version: "2012-10-17",
    Statement: [{
      Sid: "TransactionSearchXRayAccess",
      Effect: "Allow",
      Principal: { Service: "xray.amazonaws.com" },
      Action: "logs:PutLogEvents",
      Resource: [
        ("arn:aws:logs:" + $region + ":" + $account + ":log-group:aws/spans:*"),
        ("arn:aws:logs:" + $region + ":" + $account + ":log-group:/aws/application-signals/data:*")
      ],
      Condition: {
        StringEquals: { "aws:SourceAccount": $account },
        ArnLike:      { "aws:SourceArn":     ("arn:aws:xray:" + $region + ":" + $account + ":*") }
      }
    }]
  }')
aws logs put-resource-policy \
  --policy-name "${POLICY_NAME}" \
  --policy-document "${POLICY_DOC}" \
  --region "${AWS_REGION}" >/dev/null
echo "  ✓ resource policy '${POLICY_NAME}' applied"

for lg in "aws/spans" "/aws/application-signals/data"; do
  if ! aws logs describe-log-groups \
          --log-group-name-prefix "${lg}" \
          --region "${AWS_REGION}" \
          --query "logGroups[?logGroupName=='${lg}'] | [0].logGroupName" \
          --output text 2>/dev/null | grep -q "${lg}"; then
    aws logs create-log-group --log-group-name "${lg}" --region "${AWS_REGION}" 2>/dev/null || true
    echo "  ✓ created log group ${lg}"
  else
    echo "  ✓ log group ${lg} exists"
  fi
done

# ----------------------------------------------------------------------------
# 1. Trace segment destination
# ----------------------------------------------------------------------------
step "Checking trace segment destination"
CURRENT_DEST=$(aws xray get-trace-segment-destination \
  --region "${AWS_REGION}" \
  --query 'Destination' --output text 2>/dev/null || echo "UNKNOWN")
echo "  current: ${CURRENT_DEST}"
if [[ "${CURRENT_DEST}" == "CloudWatchLogs" ]]; then
  echo "  ✓ already routed to CloudWatch Logs"
else
  step "Switching destination to CloudWatchLogs (enables Transaction Search)"
  aws xray update-trace-segment-destination \
    --destination CloudWatchLogs \
    --region "${AWS_REGION}" >/dev/null
  echo "  ✓ updated"
fi

# ----------------------------------------------------------------------------
# 2. Indexing rule — keep 100% of spans
# ----------------------------------------------------------------------------
step "Checking indexing rule (Default)"
CURRENT_PCT=$(aws xray get-indexing-rules \
  --region "${AWS_REGION}" \
  --query "IndexingRules[?Name=='Default'].Rule.Probabilistic.DesiredSamplingPercentage | [0]" \
  --output text 2>/dev/null || echo "UNKNOWN")
echo "  current sampling: ${CURRENT_PCT}%"
if [[ "${CURRENT_PCT}" == "100.0" || "${CURRENT_PCT}" == "100" ]]; then
  echo "  ✓ already at 100%"
else
  step "Bumping default indexing rule to 100%"
  aws xray update-indexing-rule \
    --name Default \
    --rule '{"Probabilistic":{"DesiredSamplingPercentage":100}}' \
    --region "${AWS_REGION}" >/dev/null
  echo "  ✓ updated"
fi

# ----------------------------------------------------------------------------
# 3. Sanity-check per-runtime log groups (AgentCore creates them lazily)
# ----------------------------------------------------------------------------
step "Verifying AgentCore log groups"
LG_PREFIX="/aws/bedrock-agentcore/runtimes/"
COUNT=$(aws logs describe-log-groups \
  --log-group-name-prefix "${LG_PREFIX}" \
  --region "${AWS_REGION}" \
  --query 'length(logGroups)' --output text 2>/dev/null || echo "0")
echo "  found ${COUNT} runtime log group(s) under ${LG_PREFIX}"
echo
echo "✓ AgentCore observability enabled in ${AWS_REGION}."
echo "  GenAI Observability dashboard:"
echo "  https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#gen-ai-observability"
