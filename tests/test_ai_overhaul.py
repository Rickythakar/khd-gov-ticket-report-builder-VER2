"""TDD tests for P9.5 AI feature overhaul.

Tests cover:
1. AIAnalysisResult new fields (frustration_hotspots, frustration_by_type, hygiene_report, talking_points)
2. PredictionResult removed from dataclass and serialize
3. generate_talking_points method
4. generate_executive_summary with custom_instructions
5. run_full_analysis computes frustration hotspots and hygiene report
6. serialize_ai_results outputs new fields, drops predictions
7. settings.py includes custom_instructions
8. server import still works
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import fields as dataclass_fields
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# 1. AIAnalysisResult dataclass has new fields, no predictions
# ---------------------------------------------------------------------------


def test_ai_analysis_result_has_new_fields():
    from ai_engine import AIAnalysisResult

    r = AIAnalysisResult()
    assert hasattr(r, "frustration_hotspots")
    assert hasattr(r, "frustration_by_type")
    assert hasattr(r, "hygiene_report")
    assert hasattr(r, "talking_points")
    assert isinstance(r.frustration_hotspots, list)
    assert isinstance(r.frustration_by_type, list)
    assert isinstance(r.hygiene_report, dict)
    assert isinstance(r.talking_points, list)


def test_ai_analysis_result_no_predictions():
    from ai_engine import AIAnalysisResult

    field_names = {f.name for f in dataclass_fields(AIAnalysisResult)}
    assert "predictions" not in field_names
    assert "prediction_summary" not in field_names


def test_prediction_result_removed():
    """PredictionResult dataclass should no longer exist."""
    import ai_engine

    assert not hasattr(ai_engine, "PredictionResult")


# ---------------------------------------------------------------------------
# 2. generate_talking_points method exists and returns list
# ---------------------------------------------------------------------------


def test_generate_talking_points_exists():
    from ai_engine import AIEngine

    settings = {"ai": {"enabled": True, "provider": "chatgpt_oauth"}}
    engine = AIEngine(settings)
    assert hasattr(engine, "generate_talking_points")
    assert callable(engine.generate_talking_points)


def test_generate_talking_points_returns_list():
    from ai_engine import AIEngine

    settings = {"ai": {"enabled": True, "provider": "chatgpt_oauth"}}
    engine = AIEngine(settings)

    mock_response = {"talking_points": [
        "Ask Crestline about 10 password resets at SF Marriott",
        "Discuss email migration timeline with Aimbridge",
    ]}

    with patch.object(engine, "_call", return_value=mock_response):
        result = engine.generate_talking_points(
            metrics={"Total Tickets": 450},
            observations=["High volume of password resets"],
            company_data=[{"company": "Crestline", "tickets": 50}],
        )
    assert isinstance(result, list)
    assert len(result) == 2
    assert "Crestline" in result[0]


def test_generate_talking_points_empty_on_api_failure():
    from ai_engine import AIEngine

    settings = {"ai": {"enabled": True, "provider": "chatgpt_oauth"}}
    engine = AIEngine(settings)

    with patch.object(engine, "_call", return_value={}):
        result = engine.generate_talking_points({}, [], [])
    assert result == []


# ---------------------------------------------------------------------------
# 3. generate_executive_summary accepts custom_instructions
# ---------------------------------------------------------------------------


def test_executive_summary_accepts_custom_instructions():
    from ai_engine import AIEngine
    import inspect

    sig = inspect.signature(AIEngine.generate_executive_summary)
    assert "custom_instructions" in sig.parameters


def test_executive_summary_passes_custom_instructions():
    """custom_instructions should appear in the system prompt sent to the LLM."""
    from ai_engine import AIEngine

    settings = {"ai": {"enabled": True, "provider": "chatgpt_oauth"}}
    engine = AIEngine(settings)

    captured_system = []

    def mock_call(system, user, max_tokens=4096):
        captured_system.append(system)
        return {"summary": "test summary"}

    with patch.object(engine, "_call", side_effect=mock_call):
        engine.generate_executive_summary(
            metrics={"Total Tickets": 100},
            observations=["obs1"],
            actions=["act1"],
            custom_instructions="Focus on Crestline properties",
        )
    assert len(captured_system) == 1
    assert "Focus on Crestline properties" in captured_system[0]


def test_executive_summary_works_without_custom_instructions():
    from ai_engine import AIEngine

    settings = {"ai": {"enabled": True, "provider": "chatgpt_oauth"}}
    engine = AIEngine(settings)

    with patch.object(engine, "_call", return_value={"summary": "test"}):
        result = engine.generate_executive_summary(
            metrics={"Total Tickets": 100},
            observations=[],
            actions=[],
        )
    assert result == "test"


# ---------------------------------------------------------------------------
# 4. serialize_ai_results: new fields present, predictions gone
# ---------------------------------------------------------------------------


def test_serialize_has_new_fields():
    from ai_engine import AIAnalysisResult, serialize_ai_results

    r = AIAnalysisResult(
        frustration_hotspots=[{"company": "Test", "avg_sentiment": 1.5}],
        frustration_by_type=[{"issue_type": "Password", "avg_sentiment": 2.0}],
        hygiene_report={"total_unknown": 49, "groups": []},
        talking_points=["Point 1", "Point 2"],
    )
    s = serialize_ai_results(r)
    assert s["has_ai"] is True
    assert "frustration_hotspots" in s
    assert "frustration_by_type" in s
    assert "hygiene_report" in s
    assert "talking_points" in s
    assert s["talking_points"] == ["Point 1", "Point 2"]


def test_serialize_no_predictions():
    from ai_engine import AIAnalysisResult, serialize_ai_results

    r = AIAnalysisResult()
    s = serialize_ai_results(r)
    assert "prediction_summary" not in s
    assert "predictions_sample" not in s


def test_serialize_sentiment_all():
    from ai_engine import AIAnalysisResult, SentimentResult, serialize_ai_results

    r = AIAnalysisResult(sentiment=[
        SentimentResult(ticket_id="T1", sentiment=1, indicators=["angry"]),
        SentimentResult(ticket_id="T2", sentiment=5, indicators=["happy"]),
        SentimentResult(ticket_id="T3", sentiment=3, indicators=["neutral"]),
    ])
    s = serialize_ai_results(r)
    assert "sentiment_all" in s
    assert len(s["sentiment_all"]) == 3
    # Should NOT have the old sentiment_low / sentiment_high keys
    assert "sentiment_low" not in s
    assert "sentiment_high" not in s


def test_serialize_category_suggestions_has_current():
    from ai_engine import AIAnalysisResult, CategorySuggestion, serialize_ai_results

    r = AIAnalysisResult(category_suggestions=[
        CategorySuggestion(
            ticket_id="T1",
            current_issue_type="Unknown",
            suggested_issue_type="Password",
            suggested_sub_issue="Reset",
            confidence=0.9,
            reason="test",
        ),
    ])
    s = serialize_ai_results(r)
    assert len(s["category_suggestions"]) == 1
    assert "current" in s["category_suggestions"][0]
    assert s["category_suggestions"][0]["current"] == "Unknown"


# ---------------------------------------------------------------------------
# 5. run_full_analysis computes frustration hotspots and hygiene
# ---------------------------------------------------------------------------


def test_run_full_analysis_computes_frustration_hotspots():
    from ai_engine import AIEngine, SentimentResult

    settings = {"ai": {"enabled": True, "provider": "chatgpt_oauth", "features": {
        "sentiment": True, "categorization": True, "executive_summary": True,
        "anomaly_narration": True,
    }}}
    engine = AIEngine(settings)

    # Create a DataFrame with enough tickets from one company to trigger a hotspot
    rows = []
    for i in range(5):
        rows.append({
            "Ticket Number": f"T{i}", "Title": "Password reset",
            "Description": "Reset please", "Issue Type": "Unknown",
            "Sub-Issue Type": "Unknown", "Priority": "Medium",
            "Queue": "KHD-L1", "Company": "FrustrationCo", "Source": "Email",
        })
    df = pd.DataFrame(rows)

    # Mock sentiment to return low scores for FrustrationCo
    low_sentiments = [
        SentimentResult(ticket_id=f"T{i}", sentiment=1, confidence=0.9, indicators=["angry"])
        for i in range(5)
    ]

    mock_artifacts = MagicMock()
    mock_artifacts.headline_metrics = [("Total Tickets", 5)]
    mock_artifacts.service_observations = []
    mock_artifacts.priority_actions = []
    mock_artifacts.resolution_metrics = None
    mock_artifacts.queue_table = None
    mock_artifacts.company_table = pd.DataFrame([{"Company": "FrustrationCo", "Tickets": 5}])

    with patch.object(engine, "analyze_sentiment_batch", return_value=low_sentiments), \
         patch.object(engine, "suggest_categories_batch", return_value=[]), \
         patch.object(engine, "generate_executive_summary", return_value="summary"), \
         patch.object(engine, "generate_talking_points", return_value=["point1"]), \
         patch.object(engine, "narrate_anomalies", return_value=[]):
        result = engine.run_full_analysis(df, mock_artifacts)

    assert len(result.frustration_hotspots) >= 1
    hotspot = result.frustration_hotspots[0]
    assert hotspot["company"] == "FrustrationCo"
    assert hotspot["avg_sentiment"] <= 2.5
    assert hotspot["ticket_count"] == 5


def test_run_full_analysis_computes_hygiene_report():
    from ai_engine import AIEngine, CategorySuggestion

    settings = {"ai": {"enabled": True, "provider": "chatgpt_oauth", "features": {
        "sentiment": True, "categorization": True, "executive_summary": True,
        "anomaly_narration": True,
    }}}
    engine = AIEngine(settings)

    rows = []
    for i in range(4):
        rows.append({
            "Ticket Number": f"T{i}", "Title": "test",
            "Description": "test", "Issue Type": "Unknown",
            "Sub-Issue Type": "Unknown", "Priority": "Medium",
            "Queue": "KHD-L1", "Company": "TestCo", "Source": "Email",
        })
    df = pd.DataFrame(rows)

    suggestions = [
        CategorySuggestion(ticket_id=f"T{i}", suggested_issue_type="Password/Access",
                           suggested_sub_issue="Reset", confidence=0.9, reason="obvious")
        for i in range(4)
    ]

    mock_artifacts = MagicMock()
    mock_artifacts.headline_metrics = [("Total Tickets", 4)]
    mock_artifacts.service_observations = []
    mock_artifacts.priority_actions = []
    mock_artifacts.resolution_metrics = None
    mock_artifacts.queue_table = None
    mock_artifacts.company_table = pd.DataFrame()

    with patch.object(engine, "analyze_sentiment_batch", return_value=[]), \
         patch.object(engine, "suggest_categories_batch", return_value=suggestions), \
         patch.object(engine, "generate_executive_summary", return_value="summary"), \
         patch.object(engine, "generate_talking_points", return_value=[]), \
         patch.object(engine, "narrate_anomalies", return_value=[]):
        result = engine.run_full_analysis(df, mock_artifacts)

    assert result.hygiene_report["total_unknown"] == 4
    assert len(result.hygiene_report["groups"]) >= 1
    assert result.hygiene_report["groups"][0]["category"] == "Password/Access"
    assert result.hygiene_report["groups"][0]["count"] == 4


def test_run_full_analysis_no_predictions():
    """run_full_analysis should NOT call predict_outcomes."""
    from ai_engine import AIEngine

    settings = {"ai": {"enabled": True, "provider": "chatgpt_oauth", "features": {
        "sentiment": True, "categorization": True, "executive_summary": True,
        "anomaly_narration": True,
    }}}
    engine = AIEngine(settings)

    df = pd.DataFrame([{
        "Ticket Number": "T1", "Title": "test", "Description": "test",
        "Issue Type": "Computer", "Sub-Issue Type": "Hardware",
        "Priority": "Medium", "Queue": "KHD-L1", "Company": "TestCo", "Source": "Email",
    }])

    mock_artifacts = MagicMock()
    mock_artifacts.headline_metrics = [("Total Tickets", 1)]
    mock_artifacts.service_observations = []
    mock_artifacts.priority_actions = []
    mock_artifacts.resolution_metrics = None
    mock_artifacts.queue_table = None
    mock_artifacts.company_table = pd.DataFrame()

    with patch.object(engine, "analyze_sentiment_batch", return_value=[]), \
         patch.object(engine, "suggest_categories_batch", return_value=[]), \
         patch.object(engine, "generate_executive_summary", return_value=""), \
         patch.object(engine, "generate_talking_points", return_value=[]), \
         patch.object(engine, "narrate_anomalies", return_value=[]):
        # Should NOT have predict_outcomes method
        assert not hasattr(engine, "predict_outcomes")


def test_run_full_analysis_reads_custom_instructions():
    """run_full_analysis should pass custom_instructions from settings to generate_executive_summary."""
    from ai_engine import AIEngine

    settings = {"ai": {
        "enabled": True, "provider": "chatgpt_oauth",
        "custom_instructions": "Focus on Crestline",
        "features": {
            "sentiment": True, "categorization": True,
            "executive_summary": True, "anomaly_narration": True,
        },
    }}
    engine = AIEngine(settings)

    df = pd.DataFrame([{
        "Ticket Number": "T1", "Title": "test", "Description": "test",
        "Issue Type": "Computer", "Sub-Issue Type": "Hardware",
        "Priority": "Medium", "Queue": "KHD-L1", "Company": "TestCo", "Source": "Email",
    }])

    mock_artifacts = MagicMock()
    mock_artifacts.headline_metrics = [("Total Tickets", 1)]
    mock_artifacts.service_observations = []
    mock_artifacts.priority_actions = []
    mock_artifacts.resolution_metrics = None
    mock_artifacts.queue_table = None
    mock_artifacts.company_table = pd.DataFrame()

    captured_kwargs = {}

    def mock_exec_summary(metrics, observations, actions, custom_instructions=""):
        captured_kwargs["custom_instructions"] = custom_instructions
        return "summary"

    with patch.object(engine, "analyze_sentiment_batch", return_value=[]), \
         patch.object(engine, "suggest_categories_batch", return_value=[]), \
         patch.object(engine, "generate_executive_summary", side_effect=mock_exec_summary), \
         patch.object(engine, "generate_talking_points", return_value=[]), \
         patch.object(engine, "narrate_anomalies", return_value=[]):
        engine.run_full_analysis(df, mock_artifacts)

    assert captured_kwargs["custom_instructions"] == "Focus on Crestline"


# ---------------------------------------------------------------------------
# 6. settings.py has custom_instructions
# ---------------------------------------------------------------------------


def test_settings_has_custom_instructions():
    from settings import DEFAULT_SETTINGS

    assert "custom_instructions" in DEFAULT_SETTINGS["ai"]
    assert DEFAULT_SETTINGS["ai"]["custom_instructions"] == ""


def test_settings_has_no_prediction_feature():
    """The 'prediction' feature flag should be removed from defaults."""
    from settings import DEFAULT_SETTINGS

    assert "prediction" not in DEFAULT_SETTINGS["ai"]["features"]


# ---------------------------------------------------------------------------
# 7. Server import still works
# ---------------------------------------------------------------------------


def test_server_import():
    """Importing server should not raise errors after our changes."""
    from server import app  # noqa: F401
    assert app is not None
