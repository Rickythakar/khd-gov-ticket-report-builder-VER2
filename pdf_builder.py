from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from utils import ReportArtifacts


PAGE_WIDTH = 1600
PAGE_HEIGHT = 1100
PAGE_MARGIN = 34


class PdfBuilderError(Exception):
    """Raised when the executive PDF snapshot cannot be created."""


def _load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                "C:/Windows/Fonts/segoeuib.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/Library/Fonts/Arial Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/Library/Fonts/Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
        )

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


def _draw_panel(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], *, fill: str = "#FFFFFF") -> None:
    draw.rounded_rectangle(rect, radius=24, fill=fill, outline="#D7E4EF", width=2)


def _draw_panel_title(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    title: str,
    font: ImageFont.ImageFont,
    fill: str = "#123D62",
) -> tuple[int, int]:
    x1, y1, _, _ = rect
    draw.text((x1 + 24, y1 + 18), title, font=font, fill=fill)
    return x1 + 24, y1 + 58


def _draw_bullet_list(
    draw: ImageDraw.ImageDraw,
    items: Iterable[str],
    rect: tuple[int, int, int, int],
    font: ImageFont.ImageFont,
    fill: str,
    bullet_fill: str,
    max_items: int = 6,
) -> None:
    x1, y1, x2, y2 = rect
    y = y1
    line_height = _line_height(draw, font)
    text_x = x1 + 24
    bullet_x = x1
    max_width = max(80, x2 - text_x)

    for item in list(items)[:max_items]:
        wrapped = _wrap_text(draw, item, font, max_width)
        needed_height = max(line_height, line_height * len(wrapped))
        if y + needed_height > y2:
            break
        draw.ellipse((bullet_x, y + 9, bullet_x + 8, y + 17), fill=bullet_fill)
        _draw_wrapped_text(draw, item, (text_x, y), font, fill, max_width)
        y += needed_height + 10


def _draw_metric_grid(
    draw: ImageDraw.ImageDraw,
    metrics: list[tuple[str, str]],
    rect: tuple[int, int, int, int],
    label_font: ImageFont.ImageFont,
    value_font: ImageFont.ImageFont,
) -> None:
    x1, y1, x2, y2 = rect
    metrics = metrics[:6]
    columns = 3
    gap_x = 18
    gap_y = 18
    card_width = int((x2 - x1 - gap_x * (columns - 1)) / columns)
    rows = 2
    card_height = int((y2 - y1 - gap_y * (rows - 1)) / rows)

    for index, (label, value) in enumerate(metrics):
        row = index // columns
        col = index % columns
        card_x1 = x1 + col * (card_width + gap_x)
        card_y1 = y1 + row * (card_height + gap_y)
        card_x2 = card_x1 + card_width
        card_y2 = card_y1 + card_height
        draw.rounded_rectangle((card_x1, card_y1, card_x2, card_y2), radius=22, fill="#FFFFFF", outline="#D9E4EE", width=2)
        draw.text((card_x1 + 20, card_y1 + 16), label, font=label_font, fill="#607588")
        _draw_wrapped_text(draw, value, (card_x1 + 20, card_y1 + 48), value_font, "#17324D", card_width - 40, max_lines=2)


def _draw_table(
    draw: ImageDraw.ImageDraw,
    dataframe: pd.DataFrame,
    rect: tuple[int, int, int, int],
    title: str,
    title_font: ImageFont.ImageFont,
    header_font: ImageFont.ImageFont,
    body_font: ImageFont.ImageFont,
    row_limit: int = 6,
) -> None:
    _draw_panel(draw, rect)
    x1, y1, x2, y2 = rect
    content_x, content_y = _draw_panel_title(draw, rect, title, title_font)
    if dataframe is None or dataframe.empty:
        draw.text((content_x, content_y), "No data available.", font=body_font, fill="#607588")
        return

    headers = list(dataframe.columns[:3])
    usable = dataframe[headers].head(row_limit).copy()
    usable = usable.fillna("")
    row_height = 42
    table_x1 = x1 + 18
    table_x2 = x2 - 18
    available_width = table_x2 - table_x1
    col_widths = [0.52, 0.23, 0.25] if len(headers) == 3 else [1.0 / len(headers)] * len(headers)
    col_starts = [table_x1]
    for width in col_widths[:-1]:
        col_starts.append(col_starts[-1] + int(available_width * width))

    draw.rounded_rectangle((table_x1, content_y, table_x2, content_y + row_height), radius=12, fill="#EAF2F8")
    for idx, header in enumerate(headers):
        draw.text((col_starts[idx] + 12, content_y + 10), str(header), font=header_font, fill="#123D62")

    current_y = content_y + row_height + 8
    for row in usable.itertuples(index=False, name=None):
        if current_y + row_height > y2 - 14:
            break
        draw.rounded_rectangle((table_x1, current_y, table_x2, current_y + row_height), radius=12, fill="#FFFFFF", outline="#E6EEF5")
        for idx, value in enumerate(row[:3]):
            text = str(value)
            if idx == 2 and headers[idx] == "Share" and text and not text.endswith("%"):
                text = f"{text}%"
            max_width = int(available_width * col_widths[idx]) - 20
            _draw_wrapped_text(draw, text, (col_starts[idx] + 12, current_y + 10), body_font, "#17324D", max_width, max_lines=2)
        current_y += row_height + 8


def _draw_page_header(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    report_title: str,
    partner_name: str,
    date_range: str,
    page_label: str,
    title_font: ImageFont.ImageFont,
    subtitle_font: ImageFont.ImageFont,
    small_font: ImageFont.ImageFont,
    logo_bytes: bytes | None,
) -> None:
    draw.rounded_rectangle((PAGE_MARGIN, 24, PAGE_WIDTH - PAGE_MARGIN, 188), radius=30, fill="#123D62")
    draw.ellipse((PAGE_WIDTH - 300, -60, PAGE_WIDTH + 60, 220), fill="#4DA6D3")
    draw.text((64, 54), report_title, font=title_font, fill="#FFFFFF")

    subtitle_parts = [part for part in [partner_name.strip(), date_range.strip()] if part]
    subtitle = " | ".join(subtitle_parts) if subtitle_parts else "Executive service review snapshot"
    draw.text((66, 112), subtitle, font=subtitle_font, fill="#D7E7F3")
    draw.text((PAGE_WIDTH - 250, 146), page_label, font=small_font, fill="#EAF4FB")

    if logo_bytes:
        try:
            logo = Image.open(BytesIO(logo_bytes)).convert("RGBA")
            logo.thumbnail((230, 88))
            logo_x = PAGE_WIDTH - logo.width - 70
            logo_y = 58
            image.paste(logo, (logo_x, logo_y), logo)
        except Exception:
            pass


def _draw_footer(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> None:
    draw.text((PAGE_MARGIN, PAGE_HEIGHT - 32), text, font=font, fill="#607588")


def _category_summary(artifacts: ReportArtifacts) -> pd.DataFrame:
    if artifacts.escalation_category_table.empty:
        return pd.DataFrame(columns=["Category", "Tickets", "Share"])
    summary = artifacts.escalation_category_table.groupby("Category", as_index=False)["Tickets"].sum()
    summary["Share"] = (summary["Tickets"] / max(summary["Tickets"].sum(), 1) * 100).round(1)
    return summary


class ExecutivePdfSnapshotBuilder:
    def build_pdf_bytes(
        self,
        *,
        report_title: str,
        partner_name: str,
        date_range: str,
        artifacts: ReportArtifacts,
        logo_bytes: bytes | None = None,
    ) -> bytes:
        try:
            title_font = _load_font(40, bold=True)
            subtitle_font = _load_font(20)
            panel_title_font = _load_font(24, bold=True)
            metric_label_font = _load_font(18)
            metric_value_font = _load_font(27, bold=True)
            body_font = _load_font(18)
            small_font = _load_font(16)
            table_header_font = _load_font(16, bold=True)

            pages: list[Image.Image] = []

            page_one = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "#EEF4F8")
            draw_one = ImageDraw.Draw(page_one)
            _draw_page_header(
                page_one,
                draw_one,
                report_title=report_title,
                partner_name=partner_name,
                date_range=date_range,
                page_label="Page 1 of 2",
                title_font=title_font,
                subtitle_font=subtitle_font,
                small_font=small_font,
                logo_bytes=logo_bytes,
            )

            _draw_metric_grid(draw_one, artifacts.headline_metrics, (46, 226, PAGE_WIDTH - 46, 450), metric_label_font, metric_value_font)

            left_rect = (46, 478, 950, 710)
            right_rect = (982, 478, PAGE_WIDTH - 46, 710)
            lower_left_rect = (46, 734, 790, 1048)
            lower_right_top = (818, 734, 1176, 1048)
            lower_right_bottom = (1204, 734, PAGE_WIDTH - 46, 1048)

            _draw_panel(draw_one, left_rect)
            start_x, start_y = _draw_panel_title(draw_one, left_rect, "Executive Brief", panel_title_font)
            _draw_bullet_list(
                draw_one,
                artifacts.executive_brief_points or [artifacts.executive_brief],
                (start_x, start_y, left_rect[2] - 24, left_rect[3] - 20),
                body_font,
                "#17324D",
                "#2F7EAA",
                max_items=5,
            )

            _draw_panel(draw_one, right_rect)
            start_x, start_y = _draw_panel_title(draw_one, right_rect, "Suggested Review Topics", panel_title_font)
            _draw_bullet_list(
                draw_one,
                artifacts.priority_actions or ["No suggested review topics were generated."],
                (start_x, start_y, right_rect[2] - 24, right_rect[3] - 20),
                body_font,
                "#17324D",
                "#3A8B70",
                max_items=5,
            )

            _draw_panel(draw_one, lower_left_rect)
            start_x, start_y = _draw_panel_title(draw_one, lower_left_rect, "Service Highlights", panel_title_font)
            _draw_bullet_list(
                draw_one,
                artifacts.service_observations or ["No additional observations were generated from the current file."],
                (start_x, start_y, lower_left_rect[2] - 24, lower_left_rect[3] - 20),
                body_font,
                "#17324D",
                "#2F7EAA",
                max_items=6,
            )

            queue_table = artifacts.queue_table[["Queue", "Tickets", "Share"]] if not artifacts.queue_table.empty else artifacts.queue_table
            _draw_table(draw_one, queue_table, lower_right_top, "Queue Distribution", panel_title_font, table_header_font, small_font, row_limit=6)
            _draw_table(draw_one, artifacts.source_table, lower_right_bottom, "Intake Channel Distribution", panel_title_font, table_header_font, small_font, row_limit=6)
            _draw_footer(draw_one, "Executive PDF snapshot generated from completed tickets only.", small_font)
            pages.append(page_one)

            page_two = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "#EEF4F8")
            draw_two = ImageDraw.Draw(page_two)
            _draw_page_header(
                page_two,
                draw_two,
                report_title=report_title,
                partner_name=partner_name,
                date_range=date_range,
                page_label="Page 2 of 2",
                title_font=title_font,
                subtitle_font=subtitle_font,
                small_font=small_font,
                logo_bytes=logo_bytes,
            )

            narrative_rect = (46, 226, 780, 560)
            notes_rect = (808, 226, PAGE_WIDTH - 46, 560)
            accounts_rect = (46, 586, 560, 1048)
            reasons_rect = (588, 586, 1090, 1048)
            categories_rect = (1118, 586, PAGE_WIDTH - 46, 810)
            data_rect = (1118, 836, PAGE_WIDTH - 46, 1048)

            _draw_panel(draw_two, narrative_rect)
            start_x, start_y = _draw_panel_title(draw_two, narrative_rect, "Service Delivery Summary", panel_title_font)
            _draw_bullet_list(
                draw_two,
                artifacts.narrative or ["No service summary was generated."],
                (start_x, start_y, narrative_rect[2] - 24, narrative_rect[3] - 20),
                body_font,
                "#17324D",
                "#2F7EAA",
                max_items=6,
            )

            _draw_panel(draw_two, notes_rect)
            start_x, start_y = _draw_panel_title(draw_two, notes_rect, "Review Notes", panel_title_font)
            _draw_bullet_list(
                draw_two,
                artifacts.risk_flags or ["No additional review notes were generated from the current file."],
                (start_x, start_y, notes_rect[2] - 24, notes_rect[3] - 20),
                body_font,
                "#17324D",
                "#C04A4A",
                max_items=6,
            )

            _draw_table(draw_two, artifacts.company_table, accounts_rect, "Top Customer Accounts", panel_title_font, table_header_font, small_font, row_limit=8)
            _draw_table(draw_two, artifacts.escalation_table, reasons_rect, "Escalation Reasons", panel_title_font, table_header_font, small_font, row_limit=8)
            _draw_table(draw_two, _category_summary(artifacts), categories_rect, "Escalation Categories", panel_title_font, table_header_font, small_font, row_limit=5)

            _draw_panel(draw_two, data_rect)
            start_x, start_y = _draw_panel_title(draw_two, data_rect, "Reporting Notes", panel_title_font)
            _draw_bullet_list(
                draw_two,
                artifacts.data_quality_notes or ["No material reporting notes were identified in the current file."],
                (start_x, start_y, data_rect[2] - 24, data_rect[3] - 18),
                small_font,
                "#17324D",
                "#607588",
                max_items=5,
            )
            _draw_footer(draw_two, "Use the workbook for full ticket-level and escalation-level drill-in.", small_font)
            pages.append(page_two)

            buffer = BytesIO()
            pages[0].save(buffer, format="PDF", save_all=True, append_images=pages[1:], resolution=150.0)
            return buffer.getvalue()
        except Exception as exc:
            raise PdfBuilderError(f"Failed to build the executive PDF snapshot: {exc}") from exc
