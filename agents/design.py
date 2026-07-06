"""Design Agent — produces the full architecture report via structured output.

The LLM generates the complete ArchitectureReport (services, networking,
VPC decision, security, costs, diagram data, IaC skeleton, rationale)
adapted to the actual workload. The Well-Architected review is a second
structured-output call over the draft report.
"""

from __future__ import annotations

import logging
from typing import Any

from models.report import ArchitectureReport, WellArchitectedReview
from models.requirements import RequirementsProfile
from models.research import ResearchSummary

logger = logging.getLogger(__name__)

DESIGN_SYSTEM_PROMPT = """You are a senior AWS Solutions Architect producing a client-ready architecture design — the deliverable presented after a discovery workshop.

You will receive a RequirementsProfile and a ResearchSummary. Produce a complete ArchitectureReport. Non-negotiable rules:

SERVICE SELECTION
- Select services that fit THIS workload; never emit a generic stack. Payment processing means a payment gateway integration (Stripe / Amazon Payment Services — never card logic inside Lambda), AWS WAF, and Secrets Manager. Spiky/intermittent traffic favors serverless; sustained high throughput favors containers.
- Include the full request path: Route 53 -> (WAF for public HTTP) -> CloudFront/ALB -> entry point, plus monitoring (CloudWatch, X-Ray, alarms -> SNS) and IAM execution roles, all reflected in the diagram — not just the compute-to-database happy path.
- Every service in aws_services MUST have a matching `rationale` entry with real alternatives considered.

NETWORKING — what differentiates an architect from an app developer
- Non-serverless: complete vpc_design — CIDR sized for growth, public/private subnets across >=2 AZs, one NAT per AZ, route tables, least-privilege security groups, VPC endpoints with the cost argument vs NAT data processing.
- Fully serverless: vpc_design MUST be null, and architecture_description MUST explicitly justify why (e.g. "Lambda is not VPC-attached because it only reaches DynamoDB and S3 over AWS service endpoints; attaching would add cold-start latency and NAT cost with no security benefit").
- If HA was requested: serverless -> state that Lambda/API Gateway/DynamoDB/Cognito are regional services with built-in multi-AZ redundancy; VPC designs -> show multi-AZ placement explicitly.

COSTS
- Derive monthly estimates from the profile's actual traffic/storage numbers — show the arithmetic in the rationale (requests/month x unit price), not round guesses.
- cost_comparisons: at least 2 genuine alternatives with monthly figures and a recommendation.
- If the design exceeds budget_monthly_usd, document the trade-off explicitly in rationale.

DIAGRAM DATA
- diagram.nodes/connections must show realistic traffic flow from a Users node through DNS/CDN/WAF to compute, data, auth, and monitoring. No orphan nodes.
- Set `zone` on EVERY node — this drives the boundary boxes in the rendered diagram: "external" (users, third-party gateways, anything outside AWS), "vpc" (services you placed inside the VPC — must be consistent with vpc_design; a fully serverless design with vpc_design=null has NO "vpc" nodes), "cloud" (AWS regional services outside the VPC: S3, DynamoDB, CloudFront, Cognito, CloudWatch, ...).

REPORT QUALITY
- title: short and professional, derived from the workload — NEVER echo raw user phrases (a description like "skip" must never appear in the title).
- If iac_preference is set, include a real iac_skeleton for the chosen services.
- Leave well_architected_review null — it is produced by a separate review pass.

Return ONLY the structured ArchitectureReport. Do not narrate or explain what you are about to do — produce the structured output directly."""

REVIEW_SYSTEM_PROMPT = """You are an AWS Well-Architected Framework reviewer. Given an ArchitectureReport, produce a critical WellArchitectedReview across all six pillars. Actively hunt for violations: missing WAF, single NAT Gateway, unencrypted stores, missing alarms, public database exposure, missing backups, over-permissive IAM. Findings must be specific to this architecture, not boilerplate. Cap the output at the 10 most impactful violations and 10 most impactful improvement opportunities, ordered by severity. Return ONLY the structured object — no narration."""


class DesignAgent:
    """Architecture design agent backed by Strands structured output."""

    def __init__(self, model: Any):
        from strands import Agent

        self._agent = Agent(model=model, system_prompt=DESIGN_SYSTEM_PROMPT)
        self._review_agent = Agent(model=model, system_prompt=REVIEW_SYSTEM_PROMPT)

    def design(
        self, profile: RequirementsProfile, research: ResearchSummary
    ) -> ArchitectureReport:
        """Generate the complete architecture report for this workload."""
        prompt = (
            f"## Requirements Profile\n{profile.model_dump_json(indent=2)}\n\n"
            f"## Research Summary\n{research.model_dump_json(indent=2)}\n\n"
            "Produce the complete ArchitectureReport for this workload."
        )
        return self._agent(
            prompt, structured_output_model=ArchitectureReport
        ).structured_output

    def review(self, report: ArchitectureReport) -> WellArchitectedReview:
        """Run the Well-Architected review over a draft report."""
        prompt = (
            "Review this architecture against the Well-Architected Framework:\n\n"
            + report.model_dump_json(indent=2, exclude={"iac_skeleton"})
        )
        return self._review_agent(
            prompt, structured_output_model=WellArchitectedReview
        ).structured_output
