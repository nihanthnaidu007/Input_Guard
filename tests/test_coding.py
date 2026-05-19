import pytest

from inputguard import InputGuard, AnalysisResult


# Instantiation tests
# Verifies the constructor accepts and rejects modes as specified.

def test_default_mode_is_warning():
    # Default mode should be "warning" so basic usage doesn't block.
    guard = InputGuard()
    assert guard.mode == "warning"


def test_strict_mode_accepted():
    # "strict" is a valid mode and must be accepted without error.
    guard = InputGuard(mode="strict")
    assert guard.mode == "strict"


def test_invalid_mode_raises():
    # Any mode other than "warning" or "strict" must raise ValueError.
    with pytest.raises(ValueError):
        InputGuard(mode="loose")


# Input validation tests
# The analyze() method must reject malformed inputs cleanly.

def test_empty_string_raises():
    # Empty input has nothing to analyze; ValueError surfaces that.
    guard = InputGuard()
    with pytest.raises(ValueError):
        guard.analyze("")


def test_whitespace_only_raises():
    # Whitespace-only input is equivalent to empty for analysis purposes.
    guard = InputGuard()
    with pytest.raises(ValueError):
        guard.analyze("   \n\t  ")


def test_non_string_raises():
    # Wrong type should be a TypeError, not a misleading ValueError.
    guard = InputGuard()
    with pytest.raises(TypeError):
        guard.analyze(123)  # type: ignore[arg-type]


def test_invalid_domain_raises():
    # Phase 1 only supports "coding" — anything else is a user error.
    guard = InputGuard()
    with pytest.raises(ValueError):
        guard.analyze("build something", domain="legal")


# Return type tests
# The public surface must be stable and predictable.

def test_returns_analysis_result():
    # Public contract: analyze() returns an AnalysisResult instance.
    guard = InputGuard()
    result = guard.analyze("build a REST API")
    assert isinstance(result, AnalysisResult)


def test_to_dict_has_expected_keys():
    # to_dict() must expose the four headline fields for downstream consumers.
    guard = InputGuard()
    result = guard.analyze("build a REST API")
    d = result.to_dict()
    for key in ("status", "clarity_score", "gaps", "recommendations"):
        assert key in d


def test_is_clear_returns_bool():
    # is_clear() must always return a boolean, never None or a string.
    guard = InputGuard()
    result = guard.analyze("build a REST API")
    assert isinstance(result.is_clear(), bool)


# Rule 1 — missing_language tests

def test_missing_language_triggers_without_language():
    # "build a REST API" has a creation verb but no named language.
    guard = InputGuard()
    result = guard.analyze("build a REST API")
    codes = [f.code for f in result.findings]
    assert "missing_language" in codes


def test_missing_language_not_triggered_with_python():
    # Naming Python should satisfy the language requirement.
    guard = InputGuard()
    result = guard.analyze("build a REST API using Python")
    codes = [f.code for f in result.findings]
    assert "missing_language" not in codes


def test_missing_language_not_triggered_with_react():
    # React counts as a recognized technology.
    guard = InputGuard()
    result = guard.analyze("create an app with React")
    codes = [f.code for f in result.findings]
    assert "missing_language" not in codes


# Rule 2 — missing_api_structure tests

def test_missing_api_structure_triggers():
    # API mentioned but no routes/methods described.
    guard = InputGuard()
    result = guard.analyze("build a REST API")
    codes = [f.code for f in result.findings]
    assert "missing_api_structure" in codes


def test_missing_api_structure_not_triggered_with_routes():
    # GET/POST and "/" indicators define structure.
    guard = InputGuard()
    result = guard.analyze("build a REST API with GET /users and POST /users endpoints")
    codes = [f.code for f in result.findings]
    assert "missing_api_structure" not in codes


def test_missing_api_structure_skipped_without_api_terms():
    # If no API terms appear at all, the rule must not fire.
    guard = InputGuard()
    result = guard.analyze("build a command line script using Python")
    codes = [f.code for f in result.findings]
    assert "missing_api_structure" not in codes


# Rule 3 — missing_data_model tests

def test_missing_data_model_triggers_with_database_no_fields():
    # Database mentioned but no field/entity description.
    guard = InputGuard()
    result = guard.analyze("build a CRUD app with a database")
    codes = [f.code for f in result.findings]
    assert "missing_data_model" in codes


def test_missing_data_model_not_triggered_with_fields():
    # Naming "users with name and email fields" satisfies the data model rule.
    guard = InputGuard()
    result = guard.analyze("build a CRUD app to store users with name and email fields")
    codes = [f.code for f in result.findings]
    assert "missing_data_model" not in codes


def test_missing_data_model_skipped_without_data_terms():
    # Without storage/db terms, the rule must not fire.
    guard = InputGuard()
    result = guard.analyze("build a CLI calculator in Python")
    codes = [f.code for f in result.findings]
    assert "missing_data_model" not in codes


# Rule 4 — missing_integration_specifics tests

def test_missing_integration_specifics_triggers_with_stripe():
    # Stripe is named but no specific action — could mean anything.
    guard = InputGuard()
    result = guard.analyze("integrate with Stripe")
    codes = [f.code for f in result.findings]
    assert "missing_integration_specifics" in codes


def test_missing_integration_specifics_not_triggered_with_subscription():
    # "subscription payments" is a concrete Stripe action.
    guard = InputGuard()
    result = guard.analyze("integrate with Stripe to handle subscription payments")
    codes = [f.code for f in result.findings]
    assert "missing_integration_specifics" not in codes


def test_missing_integration_specifics_skipped_without_service():
    # Without a named third-party service, the rule must not fire.
    guard = InputGuard()
    result = guard.analyze("build a CLI tool in Python that processes CSV files")
    codes = [f.code for f in result.findings]
    assert "missing_integration_specifics" not in codes


# Rule 5 — missing_auth_type tests

def test_missing_auth_type_triggers():
    # "authentication" with no type named is a critical gap.
    guard = InputGuard()
    result = guard.analyze("add authentication to the app")
    codes = [f.code for f in result.findings]
    assert "missing_auth_type" in codes


def test_missing_auth_type_not_triggered_with_jwt():
    # JWT is a concrete authentication type.
    guard = InputGuard()
    result = guard.analyze("add JWT authentication to the app")
    codes = [f.code for f in result.findings]
    assert "missing_auth_type" not in codes


def test_missing_auth_type_not_triggered_with_google_login():
    # "login with Google" should be recognized as a specific auth type.
    guard = InputGuard()
    result = guard.analyze("add login with Google")
    codes = [f.code for f in result.findings]
    assert "missing_auth_type" not in codes


def test_missing_auth_type_skipped_without_auth_terms():
    # No auth terms means no auth rule firing.
    guard = InputGuard()
    result = guard.analyze("build a Python script to compute prime numbers")
    codes = [f.code for f in result.findings]
    assert "missing_auth_type" not in codes


# Rule 6 — missing_output_format tests

def test_missing_output_format_triggers():
    # No output target specified.
    guard = InputGuard()
    result = guard.analyze("build a task manager")
    codes = [f.code for f in result.findings]
    assert "missing_output_format" in codes


def test_missing_output_format_not_triggered_with_web_app():
    # "web app" is a recognized output format.
    guard = InputGuard()
    result = guard.analyze("build a task manager as a web app")
    codes = [f.code for f in result.findings]
    assert "missing_output_format" not in codes


def test_missing_output_format_not_triggered_with_cli():
    # "CLI tool" specifies the delivery format.
    guard = InputGuard()
    result = guard.analyze("build a CLI tool to manage tasks")
    codes = [f.code for f in result.findings]
    assert "missing_output_format" not in codes


# Scoring tests
# Confirms penalty math and threshold behavior.

def test_three_high_severity_scores_below_30():
    # 3 high-severity hits × 25 each = 75 deducted, leaving ≤ 25.
    guard = InputGuard()
    # API (high) + data model (high) + auth (high), plus naming a language and format.
    result = guard.analyze("build an API with a database and authentication using Python as a web app")
    assert result.clarity_score < 30


def test_clean_input_scores_100():
    # A complete, specific input must receive no penalties.
    guard = InputGuard()
    result = guard.analyze(
        "Build a web app using React and FastAPI. "
        "It needs user authentication with JWT. "
        "Store tasks in a PostgreSQL database with title, description, and due date fields. "
        "Expose REST API endpoints: GET /tasks, POST /tasks, DELETE /tasks/{id}."
    )
    assert result.clarity_score == 100


def test_strict_mode_blocks_what_warning_passes():
    # Same vague input: warning passes through, strict blocks.
    warning_guard = InputGuard(mode="warning")
    strict_guard = InputGuard(mode="strict")
    text = "build me something"
    w = warning_guard.analyze(text)
    s = strict_guard.analyze(text)
    assert s.status == "blocked"
    assert w.status != "blocked"


# Recommendation tests

def test_recommendations_have_required_keys():
    # Every recommendation must contain the four user-facing keys.
    guard = InputGuard()
    result = guard.analyze("build me an app")
    assert len(result.recommendations) > 0
    for rec in result.recommendations:
        for key in ("gap", "what_is_missing", "what_to_provide", "why_it_matters"):
            assert key in rec


def test_recommendation_strings_are_non_empty():
    # Empty recommendation strings would be useless to the end user.
    guard = InputGuard()
    result = guard.analyze("build me an app")
    for rec in result.recommendations:
        assert rec["what_is_missing"].strip() != ""
        assert rec["what_to_provide"].strip() != ""
        assert rec["why_it_matters"].strip() != ""


# Interpretation note tests

def test_interpretation_note_set_for_vague_input():
    # Multiple high-severity findings → interpretation note populated.
    guard = InputGuard()
    result = guard.analyze("build an API with a database and authentication")
    assert result.interpretation_note is not None


def test_interpretation_note_none_for_specific_input():
    # Clean input has nothing ambiguous to flag.
    guard = InputGuard()
    result = guard.analyze(
        "Build a web app using React and FastAPI. "
        "It needs user authentication with JWT. "
        "Store tasks in a PostgreSQL database with title, description, and due date fields. "
        "Expose REST API endpoints: GET /tasks, POST /tasks, DELETE /tasks/{id}."
    )
    assert result.interpretation_note is None


# Mode behavior tests

def test_task_manager_strict_blocks():
    # In strict mode, "build a task manager" should be blocked outright.
    guard = InputGuard(mode="strict")
    result = guard.analyze("build a task manager")
    assert result.status == "blocked"


def test_task_manager_warning_not_blocked():
    # In warning mode, the same input is surfaced but not blocked.
    guard = InputGuard(mode="warning")
    result = guard.analyze("build a task manager")
    assert result.status != "blocked"
