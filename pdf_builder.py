from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from config import REPORT_MODE_INTERNAL
from metrics import format_minutes
from utils import ReportArtifacts

PAGE_WIDTH = 1600
PAGE_HEIGHT = 1100
PAGE_MARGIN = 44

# ---- BRAND COLORS (white-background executive theme) ----
BG = "#FFFFFF"
NAVY = "#0A2540"
INK = "#1A3A5C"
SLATE = "#5A7080"
MIST = "#94A3B0"
CLOUD = "#CBD5DE"
FROST = "#E8EDF2"
SNOW = "#F4F6F9"
KASEYA_BLUE = "#009CDE"
KASEYA_BLUE_DARK = "#0077A8"
KASEYA_BLUE_LIGHT = "#E6F5FC"
GREEN = "#10B981"
GREEN_DARK = "#059669"
AMBER = "#F59E0B"
AMBER_DARK = "#D97706"
RED = "#EF4444"
RED_DARK = "#DC2626"


class PdfBuilderError(Exception):
    """Raised when the executive PDF snapshot cannot be created."""


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def _load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend([
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Menlo.ttc",
            "C:/Windows/Fonts/segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ])
    else:
        candidates.extend([
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Menlo.ttc",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ])
    for path_str in candidates:
        path = Path(path_str)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return max(0, bbox[2] - bbox[0])


def _text_height(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return max(12, bbox[3] - bbox[1])


def _line_height(draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    return max(16, bbox[3] - bbox[1] + 6)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = str(text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _measure_text(draw, candidate, font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    font: ImageFont.ImageFont,
    fill: str,
    max_width: int,
    max_lines: int | None = None,
) -> int:
    lines = _wrap_text(draw, text, font, max_width)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            lines[-1] = lines[-1].rstrip(".") + "..."
    x, y = xy
    height = _line_height(draw, font)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += height
    return y


# ---------------------------------------------------------------------------
# Drawing primitives for the white-background design
# ---------------------------------------------------------------------------

def _draw_rounded_rect(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int],
                       radius: int, *, fill: str | None = None, outline: str | None = None,
                       width: int = 1) -> None:
    """Draw a rounded rectangle (Pillow 10+ has this natively, but we provide a fallback)."""
    try:
        draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=outline, width=width)
    except AttributeError:
        # Fallback for older Pillow
        draw.rectangle(rect, fill=fill, outline=outline, width=width)


def _draw_section_title(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    title: str,
    font: ImageFont.ImageFont,
    bar_color: str,
    *,
    badge: str | None = None,
    badge_font: ImageFont.ImageFont | None = None,
) -> int:
    """Draw a section title with a colored bar on the left. Returns the y after the title."""
    draw.rectangle((x, y + 2, x + 3, y + 20), fill=bar_color)
    draw.text((x + 12, y), title, font=font, fill=NAVY)
    if badge and badge_font:
        title_w = _measure_text(draw, title, font)
        bx = x + 12 + title_w + 8
        bw = _measure_text(draw, badge, badge_font) + 10
        _draw_rounded_rect(draw, (bx, y + 2, bx + bw, y + 16), radius=3,
                           fill="#ECFDF5", outline="#A7F3D0", width=1)
        draw.text((bx + 5, y + 2), badge, font=badge_font, fill=GREEN)
    return y + _line_height(draw, font) + 4


def _draw_bullet_list(
    draw: ImageDraw.ImageDraw,
    items: Iterable[str],
    x: int, y: int,
    max_width: int,
    max_y: int,
    font: ImageFont.ImageFont,
    fill: str = INK,
    bullet_color: str = KASEYA_BLUE,
    max_items: int = 6,
) -> int:
    """Draw a bullet list with small colored circles. Returns y after last item."""
    lh = _line_height(draw, font)
    text_x = x + 16
    for item in list(items)[:max_items]:
        wrapped = _wrap_text(draw, item, font, max_width - 16)
        needed = lh * len(wrapped)
        if y + needed > max_y:
            break
        # Bullet dot
        draw.ellipse((x, y + 7, x + 5, y + 12), fill=bullet_color)
        for line in wrapped:
            draw.text((text_x, y), line, font=font, fill=fill)
            y += lh
        y += 4
    return y


def _draw_horizontal_bar(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    width: int,
    label: str,
    value_text: str,
    pct: float,
    font_label: ImageFont.ImageFont,
    font_value: ImageFont.ImageFont,
    fill_color: str,
    fill_color_dark: str,
    bar_height: int = 20,
) -> int:
    """Draw a labeled horizontal bar chart row. Returns y after the bar."""
    # Top line: label left, value right
    draw.text((x, y), label, font=font_label, fill=INK)
    vw = _measure_text(draw, value_text, font_value)
    draw.text((x + width - vw, y), value_text, font=font_value, fill=MIST)
    y += _line_height(draw, font_label) - 2

    # Track
    track_rect = (x, y, x + width, y + bar_height)
    _draw_rounded_rect(draw, track_rect, radius=4, fill=FROST)

    # Fill
    fill_w = max(4, int(width * min(pct / 100.0, 1.0)))
    fill_rect = (x, y, x + fill_w, y + bar_height)
    _draw_rounded_rect(draw, fill_rect, radius=4, fill=fill_color)

    return y + bar_height + 10


def _draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    width: int,
    label: str,
    pct: float,
    font_label: ImageFont.ImageFont,
    font_value: ImageFont.ImageFont,
    fill_color: str,
    bar_height: int = 10,
) -> int:
    """Draw a thin progress bar with label and percentage. Returns y after."""
    draw.text((x, y), label, font=font_label, fill=MIST)
    y += _line_height(draw, font_label) - 4

    # Track + fill
    bar_w = width - 60
    track_rect = (x, y, x + bar_w, y + bar_height)
    _draw_rounded_rect(draw, track_rect, radius=5, fill=FROST)
    fill_w = max(2, int(bar_w * min(pct / 100.0, 1.0)))
    fill_rect = (x, y, x + fill_w, y + bar_height)
    _draw_rounded_rect(draw, fill_rect, radius=5, fill=fill_color)

    # Percentage label
    pct_text = f"{pct:.1f}%"
    draw.text((x + bar_w + 6, y - 2), pct_text, font=font_value, fill=fill_color)

    return y + bar_height + 8


def _draw_callout_card(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    w: int, h: int,
    big_value: str,
    label: str,
    value_font: ImageFont.ImageFont,
    label_font: ImageFont.ImageFont,
    accent_color: str = KASEYA_BLUE,
    bg_color: str = KASEYA_BLUE_LIGHT,
) -> None:
    """Draw a callout card with colored left border and big number."""
    _draw_rounded_rect(draw, (x + 3, y, x + w, y + h), radius=6, fill=bg_color)
    draw.rectangle((x, y, x + 3, y + h), fill=accent_color)
    draw.text((x + 14, y + 8), big_value, font=value_font, fill=accent_color)
    draw.text((x + 14, y + h - 22), label, font=label_font, fill=SLATE)


def _draw_donut(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    cx: int, cy: int,
    radius: int,
    stroke_width: int,
    pct: float,
    color: str,
    center_text: str,
    center_font: ImageFont.ImageFont,
    sub_text: str = "",
    sub_font: ImageFont.ImageFont | None = None,
) -> None:
    """Draw a donut ring chart centered at (cx, cy)."""
    bbox = (cx - radius, cy - radius, cx + radius, cy + radius)

    # Background ring
    draw.arc(bbox, start=0, end=360, fill=FROST, width=stroke_width)

    # Filled arc (-90 = top)
    sweep = pct / 100.0 * 360
    if sweep > 0:
        draw.arc(bbox, start=-90, end=-90 + sweep, fill=color, width=stroke_width)

    # Center text
    tw = _measure_text(draw, center_text, center_font)
    th = _text_height(draw, center_text, center_font)
    draw.text((cx - tw // 2, cy - th // 2 - (6 if sub_text else 0)), center_text, font=center_font, fill=NAVY)

    if sub_text and sub_font:
        sw = _measure_text(draw, sub_text, sub_font)
        draw.text((cx - sw // 2, cy + th // 2 - 2), sub_text, font=sub_font, fill=MIST)


def _draw_table(
    draw: ImageDraw.ImageDraw,
    dataframe: pd.DataFrame | None,
    x: int, y: int,
    width: int,
    max_y: int,
    header_font: ImageFont.ImageFont,
    body_font: ImageFont.ImageFont,
    row_limit: int = 7,
) -> int:
    """Draw a clean table. Returns y after last row."""
    if dataframe is None or dataframe.empty:
        draw.text((x, y), "No data available", font=body_font, fill=MIST)
        return y + 20

    headers = list(dataframe.columns[:3])
    usable = dataframe[headers].head(row_limit).copy().fillna("")
    row_height = 28

    col_widths = [0.52, 0.24, 0.24] if len(headers) >= 3 else [1.0 / len(headers)] * len(headers)
    col_starts = [x]
    for cw in col_widths[:-1]:
        col_starts.append(col_starts[-1] + int(width * cw))

    # Header row
    for idx, header in enumerate(headers):
        hx = col_starts[idx] + 6
        if idx > 0:
            draw.text((col_starts[idx] + int(width * col_widths[idx]) - _measure_text(draw, header.upper(), header_font) - 6, y), header.upper(), font=header_font, fill=MIST)
        else:
            draw.text((hx, y), header.upper(), font=header_font, fill=MIST)
    y += row_height
    draw.line((x, y - 6, x + width, y - 6), fill=FROST, width=2)

    # Data rows
    for row in usable.itertuples(index=False, name=None):
        if y + row_height > max_y:
            break
        for idx, value in enumerate(row[:len(headers)]):
            text = str(value)
            col_x = col_starts[idx] + 6
            if idx == 0:
                fill_c = NAVY
                draw.text((col_x, y), text, font=body_font, fill=fill_c)
            else:
                # Right-align numeric columns
                tw = _measure_text(draw, text, body_font)
                rx = col_starts[idx] + int(width * col_widths[idx]) - tw - 6
                fill_c = KASEYA_BLUE if idx == 2 else INK
                draw.text((rx, y), text, font=body_font, fill=fill_c)
        y += row_height
        draw.line((x, y - 6, x + width, y - 6), fill=SNOW, width=1)

    return y


# ---------------------------------------------------------------------------
# Page structure
# ---------------------------------------------------------------------------

def _draw_page_header(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    title_text: str,
    subtitle_parts: list[str],
    title_font: ImageFont.ImageFont,
    subtitle_font: ImageFont.ImageFont,
    logo_bytes: bytes | None,
) -> None:
    """White header with navy accent stripe, title left, logo right."""
    header_bottom = 108

    # Subtle navy accent stripe at very top (dashboard aesthetic touch)
    draw.rectangle((0, 0, PAGE_WIDTH, 5), fill=NAVY)

    # Navy bottom border
    draw.rectangle((PAGE_MARGIN, header_bottom - 3, PAGE_WIDTH - PAGE_MARGIN, header_bottom), fill=NAVY)

    # Title (serif-like bold) — with more top padding to clear the stripe
    draw.text((PAGE_MARGIN, 24), title_text, font=title_font, fill=NAVY)

    # Subtitle — pushed down to avoid overlap
    sub = " \u00b7 ".join(p for p in subtitle_parts if p.strip())
    draw.text((PAGE_MARGIN, 78), sub, font=subtitle_font, fill=MIST)

    # Logo (right)
    if logo_bytes:
        try:
            logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
            logo.thumbnail((200, 42))
            logo_x = PAGE_WIDTH - PAGE_MARGIN - logo.width
            logo_y = 28
            image.paste(logo, (logo_x, logo_y), logo)
        except Exception:
            pass


def _draw_page_footer(
    draw: ImageDraw.ImageDraw,
    page_num: int,
    total_pages: int,
    context_text: str,
    font: ImageFont.ImageFont,
) -> None:
    """Footer: left = version, center = page, right = context."""
    footer_y = PAGE_HEIGHT - 36
    draw.line((PAGE_MARGIN, footer_y - 6, PAGE_WIDTH - PAGE_MARGIN, footer_y - 6), fill=FROST, width=1)
    # Navy bottom accent (mirrors top stripe — dashboard branding)
    draw.rectangle((0, PAGE_HEIGHT - 4, PAGE_WIDTH, PAGE_HEIGHT), fill=NAVY)

    left = "KHD Governance Report Builder v1.0"
    center = f"Page {page_num} of {total_pages}"
    right = context_text

    draw.text((PAGE_MARGIN, footer_y), left, font=font, fill=CLOUD)

    cw = _measure_text(draw, center, font)
    draw.text((PAGE_WIDTH // 2 - cw // 2, footer_y), center, font=font, fill=MIST)

    rw = _measure_text(draw, right, font)
    draw.text((PAGE_WIDTH - PAGE_MARGIN - rw, footer_y), right, font=font, fill=CLOUD)


# ---------------------------------------------------------------------------
# Page 1 helpers
# ---------------------------------------------------------------------------

def _pick_headline_value(metrics: list[tuple[str, str]], label_substring: str) -> str:
    """Find a headline metric by partial label match."""
    for lbl, val in metrics:
        if label_substring.lower() in lbl.lower():
            return val
    return "N/A"


def _draw_big_metric_card(
    draw: ImageDraw.ImageDraw,
    x: int, y: int, w: int, h: int,
    label: str, value: str, subtitle: str,
    label_font: ImageFont.ImageFont,
    value_font: ImageFont.ImageFont,
    sub_font: ImageFont.ImageFont,
    value_color: str = NAVY,
) -> None:
    """Draw one big metric card (snow bg, frost border, Kaseya accent)."""
    _draw_rounded_rect(draw, (x, y, x + w, y + h), radius=0, fill=SNOW, outline=FROST, width=1)
    # Subtle left accent bar (dashboard aesthetic)
    draw.rectangle((x, y + 4, x + 3, y + h - 4), fill=KASEYA_BLUE)
    draw.text((x + 20, y + 14), label.upper(), font=label_font, fill=MIST)
    draw.text((x + 20, y + 34), value, font=value_font, fill=value_color)
    if subtitle:
        draw.text((x + 20, y + h - 22), subtitle, font=sub_font, fill=SLATE)


def _sla_color_for_priority(priority: str, pct: float) -> str:
    """Return the appropriate color for an SLA priority bar."""
    p = priority.lower()
    if p == "critical":
        return RED
    if p == "high":
        return AMBER
    if p == "low":
        return KASEYA_BLUE
    return GREEN


# ---------------------------------------------------------------------------
# AI helpers
# ---------------------------------------------------------------------------

def _ai_summary_lines(ai_results: Any | None) -> list[str]:
    summary = str(getattr(ai_results, "executive_summary", "") or "").strip()
    if not summary:
        return []
    sentences = [part.strip() for part in summary.replace("\n", " ").split(". ") if part.strip()]
    lines: list[str] = []
    for sentence in sentences[:4]:
        lines.append(sentence if sentence.endswith(".") else f"{sentence}.")
    return lines or [summary[:220]]


def _category_summary(artifacts: ReportArtifacts) -> pd.DataFrame:
    if artifacts.escalation_category_table.empty:
        return pd.DataFrame(columns=["Category", "Tickets", "Share"])
    summary = artifacts.escalation_category_table.groupby("Category", as_index=False)["Tickets"].sum()
    summary["Share"] = (summary["Tickets"] / max(summary["Tickets"].sum(), 1) * 100).round(1)
    return summary


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

class ExecutivePdfSnapshotBuilder:

    def build_pdf_bytes(
        self,
        *,
        report_title: str,
        partner_name: str,
        date_range: str,
        artifacts: ReportArtifacts,
        logo_bytes: bytes | None = None,
        ai_results: Any | None = None,
    ) -> bytes:
        try:
            # Fonts
            title_font = _load_font(30, bold=True)
            subtitle_font = _load_font(12)
            section_font = _load_font(17, bold=True)
            body_font = _load_font(11)
            body_font_med = _load_font(12)
            small_font = _load_font(9)
            tiny_font = _load_font(8)
            badge_font = _load_font(7, bold=True)
            metric_label_font = _load_font(9, bold=True)
            metric_value_font = _load_font(40, bold=True)
            metric_sub_font = _load_font(10)
            table_header_font = _load_font(9, bold=True)
            table_body_font = _load_font(11)
            donut_center_font = _load_font(28, bold=True)
            donut_sub_font = _load_font(9)
            callout_value_font = _load_font(28, bold=True)
            callout_label_font = _load_font(10)
            bar_label_font = _load_font(11)
            bar_value_font = _load_font(10)
            pbar_label_font = _load_font(10)
            pbar_value_font = _load_font(11, bold=True)
            ai_body_font = _load_font(12)
            ai_large_font = _load_font(13)

            pages: list[Image.Image] = []
            has_ai_page = ai_results is not None and bool(getattr(ai_results, "executive_summary", ""))
            total_pages = 2 + int(has_ai_page)

            # ==================================================================
            # PAGE 1 -- Executive Overview
            # ==================================================================
            p1 = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), BG)
            d1 = ImageDraw.Draw(p1)

            _draw_page_header(
                p1, d1,
                title_text=report_title,
                subtitle_parts=[partner_name, "Monthly Governance Review"],
                title_font=title_font, subtitle_font=subtitle_font, logo_bytes=logo_bytes,
            )

            # -- Big metric cards (row 1: 4 cards) --
            content_top = 130  # Extra spacing below taller header
            card_gap = 0
            card_w = (PAGE_WIDTH - 2 * PAGE_MARGIN) // 4
            card_h = 100

            hm = artifacts.headline_metrics
            row1_metrics = [
                ("Total Tickets", _pick_headline_value(hm, "Total Tickets"), ""),
                ("Escalation Rate", _pick_headline_value(hm, "Escalation Rate"),
                 f"{_pick_headline_value(hm, 'Escalated Tickets')} escalated" if _pick_headline_value(hm, 'Escalated Tickets') != 'N/A' else ""),
                ("Median Resolution", _pick_headline_value(hm, "Median Resolution"),
                 f"P90: {format_minutes(artifacts.resolution_metrics.p90_minutes)}" if artifacts.resolution_metrics else ""),
                ("SLA Compliance", _pick_headline_value(hm, "SLA Compliance"), "Against configured targets"),
            ]

            for i, (label, value, sub) in enumerate(row1_metrics):
                cx = PAGE_MARGIN + i * card_w
                vc = GREEN if "SLA" in label else NAVY
                _draw_big_metric_card(d1, cx, content_top, card_w, card_h,
                                      label, value, sub,
                                      metric_label_font, metric_value_font, metric_sub_font,
                                      value_color=vc)

            # Border around the full row of cards
            _draw_rounded_rect(d1, (PAGE_MARGIN, content_top, PAGE_WIDTH - PAGE_MARGIN, content_top + card_h),
                               radius=8, outline=FROST, width=1)

            # -- Row 2 below (two columns) --
            row2_y = content_top + card_h + 24
            mid_x = PAGE_WIDTH // 2

            # LEFT: Executive Brief
            y = _draw_section_title(d1, PAGE_MARGIN, row2_y, "Executive Brief", section_font, KASEYA_BLUE)

            brief_lines = _ai_summary_lines(ai_results)
            brief_items = brief_lines or artifacts.executive_brief_points or [artifacts.executive_brief]
            y = _draw_bullet_list(d1, brief_items, PAGE_MARGIN, y, mid_x - PAGE_MARGIN - 24, row2_y + 200,
                                  body_font_med, INK, KASEYA_BLUE, max_items=5)

            # RIGHT: SLA Donut + per-priority progress bars
            sla_x = mid_x + 12
            sy = _draw_section_title(d1, sla_x, row2_y, "SLA Compliance", section_font, GREEN)

            overall_sla = artifacts.sla_metrics.overall_compliance if artifacts.sla_metrics else 0.0
            donut_cx = sla_x + 65
            donut_cy = sy + 55
            _draw_donut(p1, d1, donut_cx, donut_cy, 52, 14,
                        overall_sla, GREEN,
                        f"{overall_sla:.1f}%", donut_center_font,
                        "OVERALL", donut_sub_font)

            # Priority progress bars beside the donut
            pbar_x = sla_x + 150
            pbar_y = sy + 4
            if artifacts.sla_metrics and artifacts.sla_metrics.by_priority is not None and not artifacts.sla_metrics.by_priority.empty:
                for _, row in artifacts.sla_metrics.by_priority.iterrows():
                    priority = str(row.get("Priority", ""))
                    compliance = float(row.get("Compliance", 0))
                    bar_color = _sla_color_for_priority(priority, compliance)
                    pbar_y = _draw_progress_bar(d1, pbar_x, pbar_y, 280, priority, compliance,
                                                 pbar_label_font, pbar_value_font, bar_color)

            # -- Queue Distribution + Top Escalation Reasons (side by side bars) --
            bars_y = row2_y + 210
            bar_section_w = (PAGE_WIDTH - 2 * PAGE_MARGIN - 24) // 2

            # Queue Distribution (left)
            qy = _draw_section_title(d1, PAGE_MARGIN, bars_y, "Queue Distribution", section_font, KASEYA_BLUE)
            if not artifacts.queue_table.empty:
                for _, row in artifacts.queue_table.head(4).iterrows():
                    label = str(row.get("Queue", ""))
                    tickets = int(row.get("Tickets", 0))
                    share = float(row.get("Share", 0))
                    qy = _draw_horizontal_bar(d1, PAGE_MARGIN, qy, bar_section_w,
                                               label, f"{tickets} \u00b7 {share:.1f}%", share,
                                               bar_label_font, bar_value_font, KASEYA_BLUE, KASEYA_BLUE_DARK)

            # Top Escalation Reasons (right)
            esc_x = PAGE_MARGIN + bar_section_w + 24
            ey = _draw_section_title(d1, esc_x, bars_y, "Top Escalation Reasons", section_font, AMBER)
            if not artifacts.escalation_table.empty:
                max_tickets = int(artifacts.escalation_table["Tickets"].max()) if "Tickets" in artifacts.escalation_table.columns else 1
                for _, row in artifacts.escalation_table.head(4).iterrows():
                    reason = str(row.get("Escalation Reason", row.get(artifacts.escalation_table.columns[0], "")))
                    tickets = int(row.get("Tickets", 0))
                    share = float(row.get("Share", 0))
                    # Scale bar relative to the max entry (double the share for visual prominence)
                    bar_pct = min(share * 2, 100)
                    ey = _draw_horizontal_bar(d1, esc_x, ey, bar_section_w,
                                               reason, f"{tickets} \u00b7 {share:.1f}%", bar_pct,
                                               bar_label_font, bar_value_font, AMBER, AMBER_DARK)

            _draw_page_footer(d1, 1, total_pages, "Generated from completed tickets only", tiny_font)
            pages.append(p1)

            # ==================================================================
            # PAGE 2 -- Detailed Analysis
            # ==================================================================
            p2 = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), BG)
            d2 = ImageDraw.Draw(p2)

            _draw_page_header(
                p2, d2,
                title_text="Detailed Analysis",
                subtitle_parts=[partner_name, date_range],
                title_font=title_font, subtitle_font=subtitle_font, logo_bytes=logo_bytes,
            )

            content_top2 = 130
            col_mid = PAGE_WIDTH // 2

            # -- Service Delivery Summary (left) + Risk Factors (right) --
            sy2 = _draw_section_title(d2, PAGE_MARGIN, content_top2, "Service Delivery Summary", section_font, KASEYA_BLUE)

            # Enhance narrative with resolution + SLA data
            enhanced_narrative = list(artifacts.narrative or [])
            rm = artifacts.resolution_metrics
            sla = artifacts.sla_metrics
            if rm and rm.median_minutes > 0:
                if "Median" not in " ".join(enhanced_narrative):
                    enhanced_narrative.insert(0, f"Median resolution time of {format_minutes(rm.median_minutes)} with P90 at {format_minutes(rm.p90_minutes)}.")
            if sla and sla.overall_compliance > 0:
                if "SLA" not in " ".join(enhanced_narrative).upper():
                    enhanced_narrative.insert(1, f"Overall SLA compliance at {sla.overall_compliance}% against configured targets.")

            sy2 = _draw_bullet_list(d2, enhanced_narrative or ["No delivery data available."],
                                     PAGE_MARGIN, sy2, col_mid - PAGE_MARGIN - 24, content_top2 + 240,
                                     body_font_med, INK, KASEYA_BLUE, max_items=6)

            # Risk Factors (right column)
            ry = _draw_section_title(d2, col_mid + 12, content_top2, "Risk Factors", section_font, RED)
            ry = _draw_bullet_list(d2, artifacts.risk_flags or ["No material risk vectors detected."],
                                    col_mid + 12, ry, PAGE_WIDTH - PAGE_MARGIN - col_mid - 24, content_top2 + 160,
                                    body_font_med, INK, RED, max_items=4)

            # Review Topics (below risk, same column)
            ry += 6
            ry = _draw_section_title(d2, col_mid + 12, ry, "Review Topics", section_font, GREEN)
            ry = _draw_bullet_list(d2, artifacts.priority_actions or ["No suggested topics."],
                                    col_mid + 12, ry, PAGE_WIDTH - PAGE_MARGIN - col_mid - 24, content_top2 + 240,
                                    body_font_med, INK, GREEN, max_items=4)

            # -- Bottom section: 3 columns --
            bottom_y = content_top2 + 252
            col3_w = (PAGE_WIDTH - 2 * PAGE_MARGIN - 40) // 3
            c1_x = PAGE_MARGIN
            c2_x = PAGE_MARGIN + col3_w + 20
            c3_x = PAGE_MARGIN + 2 * (col3_w + 20)

            # Column 1: Top Accounts
            tay = _draw_section_title(d2, c1_x, bottom_y, "Top Accounts", section_font, KASEYA_BLUE)
            tay = _draw_table(d2, artifacts.company_table, c1_x, tay, col3_w, PAGE_HEIGHT - 60,
                              table_header_font, table_body_font, row_limit=7)

            # Column 2: Escalation Categories donut + Source Distribution
            ecy = _draw_section_title(d2, c2_x, bottom_y, "Escalation Categories", section_font, AMBER)

            cat_summary = _category_summary(artifacts)
            if not cat_summary.empty:
                donut_cx2 = c2_x + 45
                donut_cy2 = ecy + 38
                total_esc = int(cat_summary["Tickets"].sum())

                # Draw category donut (multi-segment)
                # Background ring
                d2.arc((donut_cx2 - 34, donut_cy2 - 34, donut_cx2 + 34, donut_cy2 + 34),
                       start=0, end=360, fill=FROST, width=10)

                cat_colors = {
                    "Uncontrollable": CLOUD,
                    "Controllable": KASEYA_BLUE,
                    "Other": AMBER,
                }
                start_angle = -90
                for _, crow in cat_summary.iterrows():
                    cat_name = str(crow["Category"])
                    cat_tickets = int(crow["Tickets"])
                    sweep = (cat_tickets / max(total_esc, 1)) * 360
                    color = cat_colors.get(cat_name, MIST)
                    if sweep > 0:
                        d2.arc((donut_cx2 - 34, donut_cy2 - 34, donut_cx2 + 34, donut_cy2 + 34),
                               start=start_angle, end=start_angle + sweep, fill=color, width=10)
                    start_angle += sweep

                # Legend beside donut
                leg_x = c2_x + 96
                leg_y = ecy + 8
                for _, crow in cat_summary.iterrows():
                    cat_name = str(crow["Category"])
                    cat_tickets = int(crow["Tickets"])
                    cat_share = float(crow["Share"])
                    dot_color = cat_colors.get(cat_name, MIST)
                    d2.ellipse((leg_x, leg_y + 3, leg_x + 8, leg_y + 11), fill=dot_color)
                    d2.text((leg_x + 14, leg_y), f"{cat_name}: {cat_tickets} ({cat_share:.0f}%)",
                            font=bar_value_font, fill=INK)
                    leg_y += 20

                ecy = max(ecy + 90, leg_y + 8)
            else:
                ecy += 20

            # Source Distribution (below categories)
            ecy = _draw_section_title(d2, c2_x, ecy, "Source Distribution", section_font, MIST)
            if not artifacts.source_table.empty:
                for _, row in artifacts.source_table.head(3).iterrows():
                    source = str(row.get("Source", ""))
                    tickets = int(row.get("Tickets", 0))
                    share = float(row.get("Share", 0))
                    ecy = _draw_horizontal_bar(d2, c2_x, ecy, col3_w,
                                                source, f"{tickets} \u00b7 {share:.1f}%", share,
                                                bar_label_font, bar_value_font, KASEYA_BLUE, KASEYA_BLUE_DARK)

            # Column 3: Resolution Time callouts + by-queue table + data notes
            rty = _draw_section_title(d2, c3_x, bottom_y, "Resolution Time", section_font, GREEN)

            if artifacts.resolution_metrics:
                rm = artifacts.resolution_metrics
                card_w2 = (col3_w - 8) // 2
                _draw_callout_card(d2, c3_x, rty, card_w2, 60,
                                   format_minutes(rm.median_minutes), "Median",
                                   callout_value_font, callout_label_font,
                                   KASEYA_BLUE, KASEYA_BLUE_LIGHT)
                _draw_callout_card(d2, c3_x + card_w2 + 8, rty, card_w2, 60,
                                   format_minutes(rm.p90_minutes), "P90",
                                   callout_value_font, callout_label_font,
                                   AMBER, "#FEF3C7")
                rty += 70

                # Resolution by Queue table
                if rm.by_queue is not None and not rm.by_queue.empty:
                    by_q = rm.by_queue.copy()
                    # Format for display: Queue, Median, P90
                    display_cols = []
                    q_col = by_q.columns[0]
                    if "Median (min)" in by_q.columns and "P90 (min)" in by_q.columns:
                        display_df = pd.DataFrame({
                            "Queue": by_q[q_col],
                            "Median": by_q["Median (min)"].apply(format_minutes),
                            "P90": by_q["P90 (min)"].apply(format_minutes),
                        })
                        rty = _draw_table(d2, display_df, c3_x, rty + 4, col3_w, PAGE_HEIGHT - 120,
                                          table_header_font, table_body_font, row_limit=4)
            else:
                d2.text((c3_x, rty), "Resolution metrics unavailable", font=body_font_med, fill=MIST)
                rty += 24

            # Data Notes at very bottom of column 3
            rty += 12
            rty = _draw_section_title(d2, c3_x, rty, "Data Notes", section_font, MIST)
            notes_text = " ".join(artifacts.data_quality_notes or ["Nominal."])
            _draw_wrapped_text(d2, notes_text, (c3_x, rty), small_font, MIST, col3_w, max_lines=3)

            _draw_page_footer(d2, 2, total_pages, "Use workbook for ticket-level detail", tiny_font)
            pages.append(p2)

            # ==================================================================
            # PAGE 3 -- AI Insights (optional)
            # ==================================================================
            if has_ai_page:
                p3 = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), BG)
                d3 = ImageDraw.Draw(p3)

                _draw_page_header(
                    p3, d3,
                    title_text="AI-Powered Insights",
                    subtitle_parts=[partner_name, date_range, "AI Analysis"],
                    title_font=title_font, subtitle_font=subtitle_font, logo_bytes=logo_bytes,
                )

                ct3 = 120

                # AI Executive Summary (full width)
                sy3 = _draw_section_title(d3, PAGE_MARGIN, ct3, "Executive Summary", section_font, GREEN,
                                           badge="AI-GENERATED", badge_font=badge_font)

                summary_text = str(getattr(ai_results, "executive_summary", "") or "")
                sy3 = _draw_wrapped_text(d3, summary_text, (PAGE_MARGIN, sy3), ai_large_font, INK,
                                          PAGE_WIDTH - 2 * PAGE_MARGIN - 200, max_lines=6)
                sy3 += 16

                # Two columns: Talking Points (left) + Frustration + Hygiene (right)
                ai_col_mid = PAGE_WIDTH // 2

                # LEFT: Governance Talking Points
                tpy = _draw_section_title(d3, PAGE_MARGIN, sy3, "Governance Talking Points", section_font, GREEN,
                                           badge="AI-GENERATED", badge_font=badge_font)
                talking = getattr(ai_results, "talking_points", []) or []
                tpy = _draw_bullet_list(d3, talking, PAGE_MARGIN, tpy,
                                         ai_col_mid - PAGE_MARGIN - 24, PAGE_HEIGHT - 60,
                                         ai_body_font, INK, GREEN, max_items=6)

                # RIGHT: Frustration Hotspots table
                fry = _draw_section_title(d3, ai_col_mid + 12, sy3, "Frustration Hotspots", section_font, AMBER,
                                           badge="AI-GENERATED", badge_font=badge_font)
                hotspots = getattr(ai_results, "frustration_hotspots", []) or []
                if hotspots:
                    hs_df = pd.DataFrame(hotspots)
                    # Normalize column names
                    col_map = {}
                    for c in hs_df.columns:
                        cl = c.lower()
                        if "company" in cl or "account" in cl:
                            col_map[c] = "Company"
                        elif "sent" in cl or "score" in cl:
                            col_map[c] = "Sentiment"
                        elif "ticket" in cl or "count" in cl:
                            col_map[c] = "Tickets"
                    hs_df = hs_df.rename(columns=col_map)

                    if "Sentiment" in hs_df.columns:
                        hs_df["Sentiment"] = hs_df["Sentiment"].apply(lambda v: f"{float(v):.1f} / 5" if pd.notna(v) else "")
                    display_cols_hs = [c for c in ["Company", "Sentiment", "Tickets"] if c in hs_df.columns]
                    if display_cols_hs:
                        fry = _draw_table(d3, hs_df[display_cols_hs], ai_col_mid + 12, fry,
                                          PAGE_WIDTH - PAGE_MARGIN - ai_col_mid - 24, PAGE_HEIGHT - 200,
                                          table_header_font, table_body_font, row_limit=5)
                else:
                    d3.text((ai_col_mid + 12, fry), "No frustration data available", font=body_font_med, fill=MIST)
                    fry += 24

                # Data Hygiene callout (below frustration)
                fry += 16
                fry = _draw_section_title(d3, ai_col_mid + 12, fry, "Data Hygiene", section_font, AMBER,
                                           badge="AI-GENERATED", badge_font=badge_font)
                hygiene = getattr(ai_results, "hygiene_report", {}) or {}
                unknown_pct = hygiene.get("unknown_pct", 0)
                if unknown_pct:
                    card_w3 = PAGE_WIDTH - PAGE_MARGIN - ai_col_mid - 24
                    _draw_callout_card(d3, ai_col_mid + 12, fry, min(card_w3, 360), 70,
                                       f"{unknown_pct}%", "of sub-issue types are Unknown or Other",
                                       callout_value_font, callout_label_font,
                                       KASEYA_BLUE, KASEYA_BLUE_LIGHT)
                    fry += 80

                suggestions = hygiene.get("suggestions", [])
                if suggestions:
                    parts = []
                    for s in suggestions[:3]:
                        if isinstance(s, dict):
                            parts.append(f"{s.get('count', '?')} tickets as {s.get('category', 'Unknown')}")
                        else:
                            parts.append(str(s))
                    hint = "AI suggests reclassifying " + " and ".join(parts) + " based on title and description analysis."
                    _draw_wrapped_text(d3, hint, (ai_col_mid + 12, fry), bar_value_font, SLATE,
                                       PAGE_WIDTH - PAGE_MARGIN - ai_col_mid - 24, max_lines=3)

                _draw_page_footer(d3, 3, total_pages, "AI insights \u00b7 Data processed locally", tiny_font)
                pages.append(p3)

            # ==================================================================
            # Assemble PDF
            # ==================================================================
            buffer = io.BytesIO()
            pages[0].save(buffer, format="PDF", save_all=True, append_images=pages[1:], resolution=150.0)
            return buffer.getvalue()

        except Exception as exc:
            raise PdfBuilderError(f"Failed to build the executive PDF snapshot: {exc}") from exc
