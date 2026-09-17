"""First-party data-analysis domain: six gap rules for analysis requests.

The third first-party domain (spec art_bTvdPdJS §7) — the real feature is
the registry; this module exercises it end to end. A data-analysis prompt
("analyze my sales data") fails differently from a coding prompt: the gaps
are the dataset, the question, the deliverable, the tooling, the volume,
and the rerun story — the labeled vocabulary of the clarity-evaluation set
(``eval/cases.csv``, whose ``domain`` column names this domain
``"data-analysis"``; the registry name follows the corpus so the harness
``guard.analyze(text, domain=row["domain"])`` resolves it).

Design, following the established trigger-and-satisfy shape:

- Two intents. ``"analysis"`` carries the English trigger terms that mark
  an analysis request; ``"reference"`` is the fallback for conceptual
  questions about data work ("what is a p-value?") — a clear question is a
  clear input, so no rule fires there. Detection is the trigger: the rules
  below are satisfy-only, because ``analyze()`` dispatches them only for
  the ``analysis`` intent.
- Each rule fires when its gap's satisfying evidence is absent. The
  satisfy vocabulary comes from the eval workbook's gap_vocabulary sheet
  (what a labeler accepts as "this gap is provided").
- Gap strings are pinned by the same workbook: ``"output format"`` is
  shared with the coding domain's gap string on purpose — the recommender
  entry serves both senses.
- Matching is boundary-safe standalone-word matching, mirroring the shared
  word-boundary matcher's semantics (``inputguard.matching`` on the
  word-boundary branch): terms match at word boundaries, phrases match
  adjacently, terms with no alphanumeric characters keep substring
  semantics. The helper is local so this module works whether or not that
  branch has merged; switch to ``from inputguard.matching import
  contains_any`` once it lands here.

Every gap has a curated recommendation entry and at least one follow-up
question, enforced by the registry-walking completeness invariant in the
test suite.
"""

from __future__ import annotations

import re
from typing import FrozenSet, Optional, Pattern, Tuple

from inputguard.registry import register_rule
from inputguard.types import RuleFinding


# -- intent signals ----------------------------------------------------------
# Priority-ordered (intent, terms) pairs for register_domain. The single
# empty-terms entry, "reference", is the fallback for inputs no analysis
# trigger matches.

ANALYSIS_TERMS: FrozenSet[str] = frozenset(
    {
        # analysis verbs
        "analyze", "analyzing", "analyzed", "analyse", "analysing",
        "analysed", "analysis", "explore", "exploring", "explored",
        "examine", "examining", "examined", "look at", "looking at",
        "look into", "looking into", "dig into", "digging into",
        "visualize", "visualizing", "visualise", "visualising",
        "profile", "profiling", "crunch", "crunching", "investigate",
        "investigating", "compare", "comparing", "compared", "comparison",
        "correlate", "correlating", "correlation", "correlations",
        "forecast", "forecasting", "segment", "segmenting",
        "report on", "reporting on",
        # analysis objects and data words
        "insight", "insights", "trend", "trends", "dataset", "datasets",
        "data", "metrics", "metric", "kpi", "kpis", "traffic",
        "spreadsheet", "spreadsheets", "dashboard", "dashboards",
        "cohort", "cohorts", "statistics", "stats", "statistical",
        "query", "queries", "warehouse", "numbers",
    }
)

DATA_ANALYSIS_SIGNALS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("analysis", tuple(sorted(ANALYSIS_TERMS))),
    ("reference", ()),
)


# -- satisfy vocabularies -----------------------------------------------------
# What a labeler accepts as "this gap is provided" (gap_vocabulary sheet).
# Plural forms are listed explicitly: the boundary matcher below matches
# standalone words, not inflections.

QUESTION_SATISFIED_TERMS: FrozenSet[str] = frozenset(
    {
        "want to know", "would like to know", "need to know",
        "goal is", "objective is", "purpose is",
        "whether", "compare", "comparing", "compared", "comparison",
        "versus", "vs", "understand why", "figure out", "figuring out",
        "determine", "determining", "identify", "identifying",
        "insight", "insights", "trend", "trends", "cohort", "cohorts",
        "retention", "churn", "conversion", "conversions", "funnel",
        "correlation", "correlations", "distribution", "drivers",
        "driver", "what drives",
    }
)

# An explicit question ("what does this dataset say about churn?") or a
# "find <object>" phrasing ("find why CSAT dropped") states the goal.
_QUESTION_MARK_RE: Pattern[str] = re.compile(r"\?\s*$")
_FIND_GOAL_RE: Pattern[str] = re.compile(
    r"\bfind\s+(?:insights?|why|out|what|which|how|whether|patterns?|drivers?)\b"
)

DATASET_SATISFIED_TERMS: FrozenSet[str] = frozenset(
    {
        # provided material
        "attached", "pasted", "emailed", "shared", "export", "exports",
        # concrete stores and platforms
        "database", "databases", "db", "schema", "schemas", "warehouse",
        "postgres", "postgresql", "mysql", "bigquery", "snowflake",
        "redshift", "databricks", "duckdb",
    }
)

# A named data file (sales.csv, nps_verbatims_2026.xlsx) or an introduced
# dataset/table ("the dataset called churn_2026").
_DATASET_FILE_RE: Pattern[str] = re.compile(
    r"(?<![\w])([\w][\w.\-]*\.(?:csv|tsv|xls|xlsx|xlsm|json|jsonl|parquet"
    r"|avro|sql|db|sqlite|sqlite3|dat|dta|sav))\b"
)
_DATASET_NAMED_RE: Pattern[str] = re.compile(
    r"\b(?:dataset|table|file|sheet)\s+(?:called|named)\s+[\w][\w.\-]*"
)

OUTPUT_SATISFIED_TERMS: FrozenSet[str] = frozenset(
    {
        "chart", "charts", "graph", "graphs", "plot", "plots",
        "heatmap", "heatmaps", "histogram", "histograms", "matrix",
        "matrices", "curve", "curves", "table", "tables", "summary",
        "summaries", "slide", "slides", "deck", "decks", "dashboard",
        "dashboards", "report", "reports", "breakdown", "breakdowns",
        # reproducible analysis output: the SQL that produces the result
        "sql",
    }
)

TOOLING_SATISFIED_TERMS: FrozenSet[str] = frozenset(
    {
        "pandas", "numpy", "polars", "matplotlib", "seaborn", "plotly",
        "sklearn", "scikit-learn", "statsmodels", "scipy", "dbt", "sql",
        "python", "pyspark", "spark", "r", "excel", "jupyter", "notebook",
        "tableau", "power bi", "looker", "no external",
        "bigquery", "snowflake", "redshift", "databricks", "duckdb",
    }
)

REPRO_SATISFIED_TERMS: FrozenSet[str] = frozenset(
    {
        "rerun", "reruns", "rerunning", "rerunnable",
        "reusable", "reuse", "reusing", "reused",
        "reproduce", "reproducing", "reproduced", "reproducible",
        "document", "documents", "documented", "documentation",
        "monthly", "weekly", "quarterly", "annually",
        "every day", "every week", "every month", "every quarter",
        "schedule", "scheduled", "scheduling", "recurring", "cron",
        "refresh", "refreshed", "refreshing",
    }
)

# Scale: "<count> <unit>" ("80,000 rows", "400m rows", "120,000 users"),
# byte sizes, and stated spans ("90 days of data", "two weeks of beacons").
_VOLUME_NOUNS = (
    r"(?:rows?|records?|responses?|comments?|entries|events?|users?"
    r"|observations?|samples?|items?|transactions?|tickets?|messages?"
    r"|clicks?|sessions?|visits?|subscribers?|accounts?|orders?|emails?)"
)
_VOLUME_COUNT_RE: Pattern[str] = re.compile(
    r"\b\d[\d.,]*\s*(?:[km]\b)?\s*" + _VOLUME_NOUNS
)
_VOLUME_SIZE_RE: Pattern[str] = re.compile(r"\b\d[\d.,]*\s*(?:kb|mb|gb|tb|bytes)\b")
_VOLUME_INTERVAL_RE: Pattern[str] = re.compile(
    r"\b\d[\d.,]*\s*(?:days?|weeks?|months?|years?|quarters?)\s+of\b"
)
_VOLUME_WORD_INTERVAL_RE: Pattern[str] = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
    r"|dozens|hundreds|thousands|millions)\s+"
    r"(?:days?|weeks?|months?|years?|quarters?)\s+of\b"
)


# -- matching helpers ----------------------------------------------------------
# Boundary-safe standalone-word matching, mirroring the shared word-boundary
# matcher's semantics (see module docstring). Normalized text only.


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _contains_term(text: str, term: str) -> bool:
    if not any(ch.isalnum() for ch in term):
        # "/", "=>", "->" — no word to bound; substring semantics.
        return term in text
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
    if re.search(pattern, text):
        return True
    if " " in term:
        tokens = term.split()
        return all(
            re.search(r"(?<![a-z0-9])" + re.escape(tok) + r"(?![a-z0-9])", text)
            for tok in tokens
        )
    return False


def _contains_any(text: str, terms: FrozenSet[str]) -> bool:
    return any(_contains_term(text, term) for term in terms)


def _is_satisfied(text: str, terms: FrozenSet[str], *regexes: Pattern[str]) -> bool:
    return _contains_any(text, terms) or any(regex.search(text) for regex in regexes)


# -- the six gap rules ---------------------------------------------------------


def _check_missing_dataset_source(text: str) -> Optional[RuleFinding]:
    """Fires when no concrete data source is named.

    "my sales data", "this dataset", and "the spreadsheet" do not satisfy —
    the labeler requires a file name, a provided export/attachment, or a
    named store (postgres, BigQuery, the warehouse, a schema).
    """
    text = _normalize(text)
    if not _is_satisfied(
        text, DATASET_SATISFIED_TERMS, _DATASET_FILE_RE, _DATASET_NAMED_RE
    ):
        return RuleFinding(
            code="missing_dataset_source",
            message=(
                "Analysis request detected but no concrete data source named — "
                "no file, table, export, or database referenced."
            ),
            severity="high",
            gap="dataset/source",
        )
    return None


def _check_missing_question_goal(text: str) -> Optional[RuleFinding]:
    """Fires when no explicit question, goal, or comparison is stated."""
    text = _normalize(text)
    if not _is_satisfied(
        text, QUESTION_SATISFIED_TERMS, _QUESTION_MARK_RE, _FIND_GOAL_RE
    ):
        return RuleFinding(
            code="missing_question_goal",
            message=(
                "Analysis request detected but no explicit question, goal, "
                "or comparison stated."
            ),
            severity="high",
            gap="question/goal",
        )
    return None


def _check_missing_deliverable_format(text: str) -> Optional[RuleFinding]:
    """Fires when no deliverable shape is named.

    Registry adapter rule id is ``missing_deliverable_format`` — the coding
    domain owns the ``missing_output_format`` id; the GAP string
    ("output format") is the shared, eval-pinned vocabulary.
    """
    text = _normalize(text)
    if not _is_satisfied(text, OUTPUT_SATISFIED_TERMS):
        return RuleFinding(
            code="missing_deliverable_format",
            message=(
                "Analysis request detected but no deliverable shape "
                "specified — no chart, table, summary, or report named."
            ),
            severity="medium",
            gap="output format",
        )
    return None


def _check_missing_tooling(text: str) -> Optional[RuleFinding]:
    """Fires when no tool or library constraint is given."""
    text = _normalize(text)
    if not _is_satisfied(text, TOOLING_SATISFIED_TERMS):
        return RuleFinding(
            code="missing_tooling",
            message=(
                "Analysis request detected but no tool or library "
                "constraint given."
            ),
            severity="medium",
            gap="tooling",
        )
    return None


def _check_missing_volume(text: str) -> Optional[RuleFinding]:
    """Fires when no data scale is stated."""
    text = _normalize(text)
    if not _is_satisfied(
        text,
        frozenset(),
        _VOLUME_COUNT_RE,
        _VOLUME_SIZE_RE,
        _VOLUME_INTERVAL_RE,
        _VOLUME_WORD_INTERVAL_RE,
    ):
        return RuleFinding(
            code="missing_volume",
            message=(
                "Analysis request detected but no data scale stated — no "
                "row count, file size, or date range."
            ),
            severity="low",
            gap="volume",
        )
    return None


def _check_missing_reproducibility(text: str) -> Optional[RuleFinding]:
    """Fires when no rerun or reuse expectation is stated."""
    text = _normalize(text)
    if not _is_satisfied(text, REPRO_SATISFIED_TERMS):
        return RuleFinding(
            code="missing_reproducibility",
            message=(
                "Analysis request detected but no rerun or reuse "
                "expectation stated."
            ),
            severity="low",
            gap="reproducibility",
        )
    return None


# Registry adapters: the check functions above stay the single home of the
# rule logic; these classes expose it through the v0.3 Rule protocol and
# register it through the same path a user rule takes.


@register_rule
class MissingDatasetSourceRule:
    """Registry adapter for _check_missing_dataset_source."""

    id = "missing_dataset_source"
    domain = "analysis"
    severity = "high"
    gap = "dataset/source"

    def check(self, text: str) -> Optional[RuleFinding]:
        return _check_missing_dataset_source(text)


@register_rule
class MissingQuestionGoalRule:
    """Registry adapter for _check_missing_question_goal."""

    id = "missing_question_goal"
    domain = "analysis"
    severity = "high"
    gap = "question/goal"

    def check(self, text: str) -> Optional[RuleFinding]:
        return _check_missing_question_goal(text)


@register_rule
class MissingDeliverableFormatRule:
    """Registry adapter for _check_missing_deliverable_format."""

    id = "missing_deliverable_format"
    domain = "analysis"
    severity = "medium"
    gap = "output format"

    def check(self, text: str) -> Optional[RuleFinding]:
        return _check_missing_deliverable_format(text)


@register_rule
class MissingToolingRule:
    """Registry adapter for _check_missing_tooling."""

    id = "missing_tooling"
    domain = "analysis"
    severity = "medium"
    gap = "tooling"

    def check(self, text: str) -> Optional[RuleFinding]:
        return _check_missing_tooling(text)


@register_rule
class MissingVolumeRule:
    """Registry adapter for _check_missing_volume."""

    id = "missing_volume"
    domain = "analysis"
    severity = "low"
    gap = "volume"

    def check(self, text: str) -> Optional[RuleFinding]:
        return _check_missing_volume(text)


@register_rule
class MissingReproducibilityRule:
    """Registry adapter for _check_missing_reproducibility."""

    id = "missing_reproducibility"
    domain = "analysis"
    severity = "low"
    gap = "reproducibility"

    def check(self, text: str) -> Optional[RuleFinding]:
        return _check_missing_reproducibility(text)


DATA_ANALYSIS_RULES = (
    MissingDatasetSourceRule,
    MissingQuestionGoalRule,
    MissingDeliverableFormatRule,
    MissingToolingRule,
    MissingVolumeRule,
    MissingReproducibilityRule,
)
