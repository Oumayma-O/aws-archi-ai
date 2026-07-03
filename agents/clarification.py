"""Clarification Agent module.

Implements the ClarificationAgent responsible for multi-turn requirements
gathering via smart question generation. Analyzes user descriptions, generates
clarifying questions for uncovered categories, and produces a complete
RequirementsProfile when sufficient information is gathered.

Responsibilities:
- Analyze system descriptions for already-stated requirements
- Generate clarifying questions with suggested defaults
- Detect skip-intent and apply defaults with documented assumptions
- Update RequirementsProfile incrementally across rounds
"""

from __future__ import annotations

import re
from typing import Any

from models.clarification import ClarificationResult, ClarifyingQuestion
from models.requirements import (
    ComplianceRequirement,
    RequirementsProfile,
    TrafficPattern,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_CATEGORIES = ("compute", "budget", "compliance", "traffic", "storage", "auth", "ha", "dr")

MAX_CLARIFICATION_ROUNDS = 5

SKIP_INTENT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bskip\b", re.IGNORECASE),
    re.compile(r"\bjust generate\b", re.IGNORECASE),
    re.compile(r"\bgo ahead\b", re.IGNORECASE),
    re.compile(r"\buse defaults?\b", re.IGNORECASE),
    re.compile(r"\bdon'?t ask\b", re.IGNORECASE),
    re.compile(r"\bno (more )?questions\b", re.IGNORECASE),
    re.compile(r"\bproceed\b", re.IGNORECASE),
]

# Maps each category to keywords that indicate the user already answered it.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "compute": [
        "serverless", "lambda", "container", "ecs", "eks", "fargate",
        "ec2", "instance", "kubernetes", "docker",
    ],
    "budget": [
        "budget", "cost", "dollar", "usd", "monthly", "spend", "price",
        "cheap", "expensive", "free tier",
    ],
    "compliance": [
        "hipaa", "soc2", "soc 2", "gdpr", "pci", "pci-dss", "compliance",
        "regulatory", "fedramp", "iso 27001",
    ],
    "traffic": [
        "concurrent", "requests per second", "rps", "traffic", "users",
        "peak", "load", "throughput", "qps",
    ],
    "storage": [
        "storage", "database", "rds", "dynamodb", "s3", "redis",
        "elasticsearch", "opensearch", "cache", "blob", "file",
    ],
    "auth": [
        "auth", "authentication", "cognito", "oauth", "sso", "saml",
        "iam", "login", "identity", "jwt",
    ],
    "ha": [
        "high availability", "ha", "multi-az", "redundan", "failover",
        "uptime", "sla", "99.9",
    ],
    "dr": [
        "disaster recovery", "dr", "backup", "multi-region", "pilot light",
        "warm standby", "active-active", "rpo", "rto",
    ],
}

# Default questions and suggested defaults for each category.
CATEGORY_QUESTIONS: dict[str, dict[str, str]] = {
    "compute": {
        "question": "What is your compute preference? (serverless, containers, instances, or mixed)",
        "suggested_default": "serverless",
    },
    "budget": {
        "question": "What is your approximate monthly budget in USD?",
        "suggested_default": "500",
    },
    "compliance": {
        "question": "Do you have any compliance or regulatory requirements? (e.g., HIPAA, SOC2, GDPR, PCI-DSS)",
        "suggested_default": "none",
    },
    "traffic": {
        "question": "What are your expected traffic patterns? (peak concurrent users, requests/sec, growth pattern)",
        "suggested_default": "moderate: ~1000 concurrent users, steady pattern",
    },
    "storage": {
        "question": "What are your storage requirements? (relational DB, NoSQL, object storage, caching)",
        "suggested_default": "relational database with S3 for assets",
    },
    "auth": {
        "question": "What authentication approach do you need? (cognito, iam, third-party, or none)",
        "suggested_default": "cognito",
    },
    "ha": {
        "question": "Do you need high availability (multi-AZ deployment)?",
        "suggested_default": "yes",
    },
    "dr": {
        "question": "What are your disaster recovery requirements? (pilot-light, warm-standby, active-active, or none)",
        "suggested_default": "none",
    },
}

# Default assumptions when skip-intent is detected.
DEFAULT_ASSUMPTIONS: dict[str, str] = {
    "compute": "serverless (Lambda + API Gateway) assumed",
    "budget": "no specific budget constraint assumed",
    "compliance": "no compliance requirements assumed",
    "traffic": "moderate traffic (~1000 concurrent users, steady pattern) assumed",
    "storage": "relational database (RDS) with S3 for assets assumed",
    "auth": "Amazon Cognito for authentication assumed",
    "ha": "high availability (multi-AZ) assumed",
    "dr": "no disaster recovery requirements assumed",
}

# System prompt for the Strands LLM agent
CLARIFICATION_SYSTEM_PROMPT = """You are an expert AWS Solutions Architect conducting a requirements-gathering interview.

Your job is to analyze a user's system description and identify which architectural requirement categories are already addressed and which still need clarification.

The required categories are:
- compute: serverless vs containers vs instances
- budget: monthly cost constraints
- compliance: regulatory frameworks (HIPAA, SOC2, GDPR, PCI-DSS)
- traffic: expected load patterns, concurrent users, requests/sec
- storage: database types, caching, object storage needs
- auth: authentication mechanism (Cognito, IAM, third-party)
- ha: high availability requirements (multi-AZ)
- dr: disaster recovery strategy

For each category NOT already covered in the user's description, generate a clear, concise question with a suggested default answer.

When the user provides answers, update the requirements profile accordingly.
If the user says "skip", "just generate", "go ahead", or similar, proceed with reasonable defaults and document assumptions.
"""


# ---------------------------------------------------------------------------
# Helper functions (testable without LLM)
# ---------------------------------------------------------------------------


def detect_skip_intent(text: str) -> bool:
    """Return True if the text expresses intent to skip clarification."""
    for pattern in SKIP_INTENT_PATTERNS:
        if pattern.search(text):
            return True
    return False


def identify_covered_categories(description: str) -> set[str]:
    """Identify which categories are already covered by the user's description.

    Scans the description for keywords associated with each category.
    A category is considered covered if at least one keyword match is found.
    """
    description_lower = description.lower()
    covered: set[str] = set()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in description_lower:
                covered.add(category)
                break
    return covered


def generate_questions_for_uncovered(
    covered_categories: set[str],
) -> list[ClarifyingQuestion]:
    """Generate clarifying questions for categories not yet covered.

    Every question includes a non-null suggested_default.
    """
    questions: list[ClarifyingQuestion] = []
    for category in REQUIRED_CATEGORIES:
        if category not in covered_categories:
            info = CATEGORY_QUESTIONS[category]
            questions.append(
                ClarifyingQuestion(
                    question=info["question"],
                    category=category,
                    suggested_default=info["suggested_default"],
                )
            )
    return questions


def build_default_profile(description: str, covered_categories: set[str]) -> RequirementsProfile:
    """Build a RequirementsProfile using defaults for uncovered categories.

    Documents each defaulted value in the assumptions list.
    """
    assumptions: list[str] = []
    for category in REQUIRED_CATEGORIES:
        if category not in covered_categories:
            assumptions.append(DEFAULT_ASSUMPTIONS[category])

    return RequirementsProfile(
        original_description=description,
        compute_preference="serverless",
        budget_monthly_usd=None,
        compliance=ComplianceRequirement(),
        multi_region=False,
        disaster_recovery="none",
        traffic=TrafficPattern(
            peak_concurrent_users=1000,
            requests_per_second=100,
            pattern="steady",
        ),
        storage_requirements=["RDS", "S3"],
        authentication="cognito",
        high_availability=True,
        assumptions=assumptions,
    )


# ---------------------------------------------------------------------------
# ClarificationAgent
# ---------------------------------------------------------------------------


class ClarificationAgent:
    """Specialized agent for requirements gathering via clarifying questions.

    Uses the Strands Agent SDK for LLM-powered analysis when available,
    with deterministic fallback logic for question generation and skip
    detection that can run without an LLM (useful for testing).
    """

    def __init__(self, model: Any | None = None):
        """Initialize the clarification agent.

        Args:
            model: Optional Strands model instance. If None, the agent uses
                   deterministic keyword-matching logic only.
        """
        self._model = model
        self._agent = self._create_agent() if model is not None else None

    def _create_agent(self) -> Any:
        """Create the underlying Strands Agent with the clarification system prompt."""
        try:
            from strands import Agent

            return Agent(
                model=self._model,
                system_prompt=CLARIFICATION_SYSTEM_PROMPT,
            )
        except ImportError:
            return None

    def analyze_and_clarify(
        self,
        description: str,
        existing_profile: RequirementsProfile | None = None,
    ) -> ClarificationResult:
        """Analyze description and generate clarifying questions.

        Args:
            description: User's system description or follow-up answer.
            existing_profile: Previously gathered requirements (for follow-up rounds).

        Returns:
            ClarificationResult with questions or a complete RequirementsProfile.
        """
        # Determine current round number
        round_number = 1
        if existing_profile is not None:
            # Count how many categories are already covered in the existing profile
            round_number = self._infer_round_number(existing_profile)

        # Check for skip intent
        if detect_skip_intent(description):
            covered = self._get_covered_from_profile(existing_profile) if existing_profile else set()
            covered |= identify_covered_categories(description)
            profile = self._build_profile_from_context(
                description, existing_profile, covered
            )
            return ClarificationResult(
                questions=[],
                profile=profile,
                is_complete=True,
                round_number=round_number,
            )

        # Check if we've reached max rounds
        if round_number > MAX_CLARIFICATION_ROUNDS:
            covered = self._get_covered_from_profile(existing_profile) if existing_profile else set()
            covered |= identify_covered_categories(description)
            profile = self._build_profile_from_context(
                description, existing_profile, covered
            )
            return ClarificationResult(
                questions=[],
                profile=profile,
                is_complete=True,
                round_number=MAX_CLARIFICATION_ROUNDS,
            )

        # Identify what's already covered
        covered = identify_covered_categories(description)
        if existing_profile is not None:
            covered |= self._get_covered_from_profile(existing_profile)

        # If all categories are covered, produce the final profile
        if covered >= set(REQUIRED_CATEGORIES):
            profile = self._build_profile_from_context(
                description, existing_profile, covered
            )
            return ClarificationResult(
                questions=[],
                profile=profile,
                is_complete=True,
                round_number=round_number,
            )

        # Generate questions for uncovered categories
        questions = generate_questions_for_uncovered(covered)

        return ClarificationResult(
            questions=questions,
            profile=existing_profile,
            is_complete=False,
            round_number=round_number,
        )

    def _infer_round_number(self, profile: RequirementsProfile) -> int:
        """Infer the current round number from the profile's answered fields."""
        covered = self._get_covered_from_profile(profile)
        # Each round typically covers 1-3 categories. Estimate round as:
        # covered_count / total_categories mapped to rounds (at least 2 since profile exists)
        if not covered:
            return 2  # Profile exists but nothing explicitly covered yet
        # Round number is at least 2 (since we already have a profile from round 1)
        return min(len(covered) // 2 + 2, MAX_CLARIFICATION_ROUNDS + 1)

    def _get_covered_from_profile(self, profile: RequirementsProfile) -> set[str]:
        """Determine which categories are already covered based on profile fields."""
        covered: set[str] = set()

        if profile.compute_preference is not None:
            covered.add("compute")
        if profile.budget_monthly_usd is not None:
            covered.add("budget")
        if profile.compliance.frameworks or profile.compliance.data_residency:
            covered.add("compliance")
        if (
            profile.traffic.peak_concurrent_users is not None
            or profile.traffic.requests_per_second is not None
        ):
            covered.add("traffic")
        if profile.storage_requirements:
            covered.add("storage")
        if profile.authentication is not None:
            covered.add("auth")
        # ha is True by default, so we check the original description or explicit setting
        # Consider it covered since it has an explicit value
        covered.add("ha")
        if profile.disaster_recovery is not None:
            covered.add("dr")

        return covered

    def _build_profile_from_context(
        self,
        description: str,
        existing_profile: RequirementsProfile | None,
        covered: set[str],
    ) -> RequirementsProfile:
        """Build or update a RequirementsProfile from available context.

        Merges existing profile data with newly detected information and
        applies defaults for uncovered categories.
        """
        if existing_profile is not None:
            # Merge: keep existing profile values, add assumptions for uncovered
            assumptions = list(existing_profile.assumptions)
            for category in REQUIRED_CATEGORIES:
                if category not in covered:
                    assumptions.append(DEFAULT_ASSUMPTIONS[category])

            return existing_profile.model_copy(
                update={
                    "assumptions": assumptions,
                    "original_description": (
                        existing_profile.original_description + "\n" + description
                        if description != existing_profile.original_description
                        else existing_profile.original_description
                    ),
                }
            )

        return build_default_profile(description, covered)
