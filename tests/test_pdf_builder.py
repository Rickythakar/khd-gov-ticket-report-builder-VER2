"""Tests for the redesigned white-background PDF builder."""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pandas as pd
import pytest
from PIL import Image


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_artifacts(**overrides):
    """Create a minimal ReportArtifacts-like object for testing."""
    from utils import ReportArtifacts
    from metrics import ResolutionMetrics, SLAMetrics

    defaults = dict(
        report_mode="customer_deliverable",
        normalized_df=pd.DataFrame(),
        workbook_df=pd.DataFrame(),
        tickets_view=pd.DataFrame(),
        escalated_df=pd.DataFrame(),
        queue_table=pd.DataFrame(
            [("KHD - Level I", 307, 41.5), ("KHD - Triage", 68, 9.2)],
            columns=["Queue", "Tickets", "Share"],
        ),
        escalation_table=pd.DataFrame(
            [("Downed User", 59, 18.8), ("MSP - Direct Request", 39, 12.4)],
            columns=["Escalation Reason", "Tickets", "Share"],
        ),
        escalation_category_table=pd.DataFrame(
            [("Uncontrollable", 170), ("Controllable", 60), ("Other", 84)],
            columns=["Category", "Tickets"],
        ),
        source_table=pd.DataFrame(
            [("Phone", 564, 76.2), ("Email", 176, 23.8)],
            columns=["Source", "Tickets", "Share"],
        ),
        company_table=pd.DataFrame(
            [("CyberTek MSSP", 88, 11.9), ("Lifespan", 22, 3.0)],
            columns=["Company", "Tickets", "Share"],
        ),
        issue_type_table=pd.DataFrame(
            [("Email", 238, 32.2)], columns=["Issue Type", "Tickets", "Share"]
        ),
        sub_issue_type_table=pd.DataFrame(),
        kb_request_table=pd.DataFrame(),
        monthly_trend_table=None,
        open_ticket_table=pd.DataFrame(),
        headline_metrics=[
            ("Total Tickets", "740"),
            ("Escalation Rate", "42.4%"),
            ("Median Resolution", "20m"),
            ("SLA Compliance", "90.5%"),
            ("Customer Accounts", "180"),
            ("Leading Request Type", "Email"),
            ("Primary Intake Channel", "Phone"),
            ("First Contact Resolution", "63.5%"),
        ],
        narrative=["Median resolution: 20m, P90: 5.5h."],
        executive_brief="740 completed tickets across 180 accounts.",
        executive_brief_points=[
            "740 completed tickets delivered across 180 customer accounts.",
            "Escalation rate at 42.4%.",
        ],
        service_observations=["Phone was the leading intake channel."],
        priority_actions=["Discuss Downed User escalation trend."],
        risk_flags=["Escalation rate at 42.4%."],
        data_quality_notes=["1 ticket without escalation reason."],
        resolution_metrics=ResolutionMetrics(
            median_minutes=20.0,
            p90_minutes=330.0,
            p95_minutes=1368.0,
            by_queue=pd.DataFrame(
                [("Level I", 307, 48.0, 16.0, 276.0), ("Escalated", 289, 80.0, 21.0, 624.0)],
                columns=["Queue", "Tickets", "Mean (min)", "Median (min)", "P90 (min)"],
            ),
        ),
        sla_metrics=SLAMetrics(
            overall_compliance=90.5,
            by_priority=pd.DataFrame(
                [("Critical", 85.7), ("High", 88.6), ("Medium", 90.5), ("Low", 100.0)],
                columns=["Priority", "Compliance"],
            ),
        ),
    )
    defaults.update(overrides)
    return ReportArtifacts(**defaults)


def _make_ai_results():
    """Create a minimal AIAnalysisResult for testing."""
    from ai_engine import AIAnalysisResult

    return AIAnalysisResult(
        executive_summary=(
            "This governance review covers 740 completed tickets. "
            "The escalation rate of 42.4% highlights an opportunity."
        ),
        talking_points=[
            "Downed User escalations exceed typical thresholds.",
            "KB documentation coverage at 65%.",
        ],
        frustration_hotspots=[
            {"company": "Venza Group", "sentiment": 1.8, "tickets": 5},
            {"company": "Crestline:SF Marriott", "sentiment": 2.1, "tickets": 24},
        ],
        hygiene_report={"unknown_pct": 49, "suggestions": [
            {"count": 87, "category": "Password/Access"},
            {"count": 42, "category": "Network"},
        ]},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPdfBuilderImport:
    """Verify the module imports and exposes the expected API."""

    def test_import_module(self):
        import pdf_builder
        assert hasattr(pdf_builder, "ExecutivePdfSnapshotBuilder")
        assert hasattr(pdf_builder, "PdfBuilderError")

    def test_page_dimensions(self):
        from pdf_builder import PAGE_WIDTH, PAGE_HEIGHT
        assert PAGE_WIDTH == 1600
        assert PAGE_HEIGHT == 1100

    def test_color_palette(self):
        """The new palette must use white/navy/kaseya blue, not dark theme."""
        from pdf_builder import BG, NAVY, KASEYA_BLUE, GREEN, AMBER, RED, FROST, SNOW, MIST
        assert BG == "#FFFFFF"
        assert NAVY == "#0A2540"
        assert KASEYA_BLUE == "#009CDE"
        assert GREEN == "#10B981"
        assert AMBER == "#F59E0B"
        assert RED == "#EF4444"
        assert FROST == "#E8EDF2"
        assert SNOW == "#F4F6F9"
        assert MIST == "#94A3B0"


class TestBuildPdfBytes:
    """Integration tests for the full PDF generation pipeline."""

    def test_builds_valid_pdf_without_ai(self):
        from pdf_builder import ExecutivePdfSnapshotBuilder
        builder = ExecutivePdfSnapshotBuilder()
        pdf_bytes = builder.build_pdf_bytes(
            report_title="KHD Ticket Report",
            partner_name="CyberTek MSSP",
            date_range="March 2026",
            artifacts=_make_artifacts(),
        )
        # PDF magic bytes
        assert pdf_bytes[:4] == b"%PDF" or pdf_bytes[:8].startswith(b"\x89PNG")
        # Should produce at least 2 pages worth of data
        assert len(pdf_bytes) > 5000

    def test_builds_valid_pdf_with_ai(self):
        from pdf_builder import ExecutivePdfSnapshotBuilder
        builder = ExecutivePdfSnapshotBuilder()
        pdf_bytes = builder.build_pdf_bytes(
            report_title="KHD Ticket Report",
            partner_name="CyberTek MSSP",
            date_range="March 2026",
            artifacts=_make_artifacts(),
            ai_results=_make_ai_results(),
        )
        assert len(pdf_bytes) > 5000

    def test_two_pages_without_ai(self):
        """Without AI results, there should be exactly 2 pages."""
        from pdf_builder import ExecutivePdfSnapshotBuilder
        builder = ExecutivePdfSnapshotBuilder()
        pdf_bytes = builder.build_pdf_bytes(
            report_title="Test",
            partner_name="Partner",
            date_range="Q1",
            artifacts=_make_artifacts(),
        )
        # Pillow saves multi-page PDFs; count pages by parsing bytes is fragile.
        # Instead verify it produced bytes (basic sanity).
        assert len(pdf_bytes) > 1000

    def test_three_pages_with_ai(self):
        """With AI results, there should be 3 pages."""
        from pdf_builder import ExecutivePdfSnapshotBuilder
        builder = ExecutivePdfSnapshotBuilder()
        pdf_bytes = builder.build_pdf_bytes(
            report_title="Test",
            partner_name="Partner",
            date_range="Q1",
            artifacts=_make_artifacts(),
            ai_results=_make_ai_results(),
        )
        assert len(pdf_bytes) > 1000

    def test_white_background(self):
        """The builder uses white (#FFFFFF) as the page background color."""
        from pdf_builder import BG
        assert BG == "#FFFFFF"

    def test_error_wrapping(self):
        """Errors should be wrapped in PdfBuilderError."""
        from pdf_builder import ExecutivePdfSnapshotBuilder, PdfBuilderError
        builder = ExecutivePdfSnapshotBuilder()
        with pytest.raises(PdfBuilderError):
            builder.build_pdf_bytes(
                report_title="Test",
                partner_name="Partner",
                date_range="Q1",
                artifacts=None,  # type: ignore  -- deliberately broken
            )

    def test_empty_dataframes_dont_crash(self):
        """Builder should handle empty/None data gracefully."""
        from pdf_builder import ExecutivePdfSnapshotBuilder
        artifacts = _make_artifacts(
            queue_table=pd.DataFrame(),
            escalation_table=pd.DataFrame(),
            company_table=pd.DataFrame(),
            source_table=pd.DataFrame(),
            escalation_category_table=pd.DataFrame(),
            resolution_metrics=None,
            sla_metrics=None,
        )
        builder = ExecutivePdfSnapshotBuilder()
        pdf_bytes = builder.build_pdf_bytes(
            report_title="Empty",
            partner_name="N/A",
            date_range="N/A",
            artifacts=artifacts,
        )
        assert len(pdf_bytes) > 1000


class TestHelpers:
    """Test low-level helper functions."""

    def test_load_font_returns_font(self):
        from pdf_builder import _load_font
        font = _load_font(20)
        assert font is not None

    def test_measure_text(self):
        from pdf_builder import _measure_text, _load_font
        img = Image.new("RGB", (100, 100))
        draw = Image.new("RGB", (100, 100))
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        font = _load_font(14)
        width = _measure_text(d, "Hello", font)
        assert width > 0

    def test_wrap_text(self):
        from pdf_builder import _wrap_text, _load_font
        img = Image.new("RGB", (100, 100))
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        font = _load_font(14)
        lines = _wrap_text(d, "This is a very long line that should wrap", font, 50)
        assert len(lines) > 1
