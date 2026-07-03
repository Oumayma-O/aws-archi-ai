"""Unit tests for the ClarificationAgent."""

import pytest

from agents.clarification import (
    REQUIRED_CATEGORIES,
    ClarificationAgent,
    build_default_profile,
    detect_skip_intent,
    generate_questions_for_uncovered,
    identify_covered_categories,
)
from models.clarification import ClarificationResult, ClarifyingQuestion
from models.requirements import (
    ComplianceRequirement,
    RequirementsProfile,
    TrafficPattern,
)


# ---------------------------------------------------------------------------
# detect_skip_intent tests
# ---------------------------------------------------------------------------


class TestDetectSkipIntent:
    """Tests for skip-intent detection logic."""

    @pytest.mark.parametrize(
        "text",
        [
            "skip",
            "Skip",
            "SKIP",
            "just generate",
            "Just generate the architecture",
            "go ahead",
            "Go ahead with defaults",
            "use defaults",
            "use default settings",
            "don't ask",
            "dont ask me questions",
            "no more questions",
            "no questions",
            "proceed",
            "Please proceed with the design",
        ],
    )
    def test_detects_skip_intent(self, text: str):
        assert detect_skip_intent(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "I need a web app with serverless compute",
            "Build me an e-commerce platform",
            "I want containers on ECS",
            "My budget is $500/month",
            "",
            "Tell me more about the options",
        ],
    )
    def test_does_not_detect_skip_in_normal_text(self, text: str):
        assert detect_skip_intent(text) is False


# ---------------------------------------------------------------------------
# identify_covered_categories tests
# ---------------------------------------------------------------------------


class TestIdentifyCoveredCategories:
    """Tests for keyword-based category detection."""

    def test_detects_compute_serverless(self):
        covered = identify_covered_categories("I want a serverless architecture")
        assert "compute" in covered

    def test_detects_compute_containers(self):
        covered = identify_covered_categories("We use ECS Fargate containers")
        assert "compute" in covered

    def test_detects_budget(self):
        covered = identify_covered_categories("My budget is $2000 USD monthly")
        assert "budget" in covered

    def test_detects_compliance(self):
        covered = identify_covered_categories("We need HIPAA compliance and SOC2")
        assert "compliance" in covered

    def test_detects_traffic(self):
        covered = identify_covered_categories("We expect 5000 concurrent users")
        assert "traffic" in covered

    def test_detects_storage(self):
        covered = identify_covered_categories("We need a database and S3 storage")
        assert "storage" in covered

    def test_detects_auth(self):
        covered = identify_covered_categories("Authentication will use Cognito")
        assert "auth" in covered

    def test_detects_ha(self):
        covered = identify_covered_categories("We need high availability with multi-AZ")
        assert "ha" in covered

    def test_detects_dr(self):
        covered = identify_covered_categories("Disaster recovery with warm standby")
        assert "dr" in covered

    def test_multiple_categories(self):
        desc = (
            "I need a serverless architecture with HIPAA compliance, "
            "high availability, and disaster recovery using pilot light. "
            "Budget is $3000/month."
        )
        covered = identify_covered_categories(desc)
        assert "compute" in covered
        assert "compliance" in covered
        assert "ha" in covered
        assert "dr" in covered
        assert "budget" in covered

    def test_empty_description(self):
        covered = identify_covered_categories("")
        assert len(covered) == 0

    def test_generic_description_covers_nothing(self):
        covered = identify_covered_categories("Build me a web app")
        assert len(covered) == 0


# ---------------------------------------------------------------------------
# generate_questions_for_uncovered tests
# ---------------------------------------------------------------------------


class TestGenerateQuestions:
    """Tests for question generation logic."""

    def test_generates_all_questions_when_none_covered(self):
        questions = generate_questions_for_uncovered(set())
        assert len(questions) == len(REQUIRED_CATEGORIES)
        categories = {q.category for q in questions}
        assert categories == set(REQUIRED_CATEGORIES)

    def test_all_questions_have_suggested_default(self):
        questions = generate_questions_for_uncovered(set())
        for q in questions:
            assert q.suggested_default is not None
            assert len(q.suggested_default) > 0

    def test_omits_covered_categories(self):
        covered = {"compute", "budget", "ha"}
        questions = generate_questions_for_uncovered(covered)
        categories = {q.category for q in questions}
        assert "compute" not in categories
        assert "budget" not in categories
        assert "ha" not in categories
        # But uncovered categories should be present
        assert "compliance" in categories
        assert "traffic" in categories

    def test_no_questions_when_all_covered(self):
        questions = generate_questions_for_uncovered(set(REQUIRED_CATEGORIES))
        assert len(questions) == 0


# ---------------------------------------------------------------------------
# build_default_profile tests
# ---------------------------------------------------------------------------


class TestBuildDefaultProfile:
    """Tests for default profile building."""

    def test_stores_original_description(self):
        profile = build_default_profile("Build a web app", set())
        assert profile.original_description == "Build a web app"

    def test_assumptions_list_for_uncovered(self):
        profile = build_default_profile("test", set())
        # All categories uncovered → all defaults documented
        assert len(profile.assumptions) == len(REQUIRED_CATEGORIES)

    def test_fewer_assumptions_when_some_covered(self):
        covered = {"compute", "budget"}
        profile = build_default_profile("test", covered)
        assert len(profile.assumptions) == len(REQUIRED_CATEGORIES) - 2

    def test_default_compute_is_serverless(self):
        profile = build_default_profile("test", set())
        assert profile.compute_preference == "serverless"

    def test_default_ha_is_true(self):
        profile = build_default_profile("test", set())
        assert profile.high_availability is True


# ---------------------------------------------------------------------------
# ClarificationAgent integration tests
# ---------------------------------------------------------------------------


class TestClarificationAgent:
    """Tests for the ClarificationAgent class."""

    @pytest.fixture
    def agent(self):
        """Create agent without LLM model (deterministic mode)."""
        return ClarificationAgent(model=None)

    def test_initial_description_generates_questions(self, agent):
        result = agent.analyze_and_clarify("Build me a web application")
        assert isinstance(result, ClarificationResult)
        assert result.is_complete is False
        assert len(result.questions) > 0
        assert result.round_number == 1

    def test_description_with_info_omits_covered_questions(self, agent):
        desc = "I need a serverless app with HIPAA compliance on a $1000 monthly budget"
        result = agent.analyze_and_clarify(desc)
        categories = {q.category for q in result.questions}
        assert "compute" not in categories
        assert "compliance" not in categories
        assert "budget" not in categories

    def test_skip_intent_returns_complete_profile(self, agent):
        result = agent.analyze_and_clarify("skip")
        assert result.is_complete is True
        assert result.profile is not None
        assert len(result.profile.assumptions) > 0

    def test_skip_with_existing_profile_preserves_data(self, agent):
        existing = RequirementsProfile(
            original_description="E-commerce site",
            compute_preference="containers",
            budget_monthly_usd=2000.0,
        )
        result = agent.analyze_and_clarify("go ahead", existing_profile=existing)
        assert result.is_complete is True
        assert result.profile is not None
        assert result.profile.compute_preference == "containers"
        assert result.profile.budget_monthly_usd == 2000.0

    def test_all_categories_covered_produces_complete_result(self, agent):
        desc = (
            "I need a serverless Lambda application with $500 monthly budget, "
            "HIPAA compliance, expecting 5000 concurrent users, "
            "using DynamoDB for storage, Cognito authentication, "
            "high availability multi-AZ, and disaster recovery with warm standby."
        )
        result = agent.analyze_and_clarify(desc)
        assert result.is_complete is True
        assert result.profile is not None

    def test_max_rounds_exceeded_forces_completion(self, agent):
        # Create an existing profile that implies many rounds have passed
        existing = RequirementsProfile(
            original_description="Multi-round description",
            compute_preference="containers",
            budget_monthly_usd=2000.0,
            compliance=ComplianceRequirement(frameworks=["SOC2"]),
            traffic=TrafficPattern(
                peak_concurrent_users=5000,
                requests_per_second=1000,
            ),
            storage_requirements=["RDS", "S3", "Redis"],
            authentication="cognito",
            high_availability=True,
            disaster_recovery="warm-standby",
        )
        # This profile covers all categories, so round_number will be high
        result = agent.analyze_and_clarify("What about caching?", existing_profile=existing)
        # All categories covered → should be complete
        assert result.is_complete is True

    def test_every_question_has_suggested_default(self, agent):
        result = agent.analyze_and_clarify("Build me a web app")
        for q in result.questions:
            assert q.suggested_default is not None

    def test_questions_only_for_required_categories(self, agent):
        result = agent.analyze_and_clarify("Build me an API")
        for q in result.questions:
            assert q.category in REQUIRED_CATEGORIES

    def test_just_generate_is_skip_intent(self, agent):
        result = agent.analyze_and_clarify("just generate something for me")
        assert result.is_complete is True
        assert result.profile is not None

    def test_proceed_is_skip_intent(self, agent):
        result = agent.analyze_and_clarify("proceed with the defaults")
        assert result.is_complete is True
