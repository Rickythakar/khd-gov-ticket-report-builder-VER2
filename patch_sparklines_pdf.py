import re

with open("pdf_builder.py", "r") as f:
    content = f.read()

old_func = r"""def _draw_metric_grid(
    draw: ImageDraw.ImageDraw,
    metrics: list[tuple[str, str]],
    rect: tuple[int, int, int, int],
    label_font: ImageFont.ImageFont,
    value_font: ImageFont.ImageFont,
) -> None:
    x1, y1, x2, y2 = rect
    metrics = metrics[:8]
    columns = 4
    gap_x = 16
    gap_y = 16
    card_width = int((x2 - x1 - gap_x * (columns - 1)) / columns)
    rows = 2
    card_height = int((y2 - y1 - gap_y * (rows - 1)) / rows)
    colors = [CYAN, BLUE, AMBER, GREEN]

    for index, (label, value) in enumerate(metrics):
        row = index // columns
        col = index % columns
        card_x1 = x1 + col * (card_width + gap_x)
        card_y1 = y1 + row * (card_height + gap_y)
        card_x2 = card_x1 + card_width
        card_y2 = card_y1 + card_height
        draw.rectangle((card_x1, card_y1, card_x2, card_y2), fill=SURFACE, outline=BORDER, width=1)
        draw.rectangle((card_x1, card_y1, card_x1 + 4, card_y2), fill=colors[col % 4])
        draw.text((card_x1 + 18, card_y1 + 14), label.upper(), font=label_font, fill=DIM)
        _draw_wrapped_text(draw, value, (card_x1 + 18, card_y1 + 46), value_font, BRIGHT, card_width - 40, max_lines=2)

        # Draw an abstract pattern in the bottom right corner (instead of sparklines for PDF)
        pattern_x = card_x2 - 40
        pattern_y = card_y2 - 20
        for i in range(5):
            for j in range(2):
                if (i+j) % 2 == 0:
                    draw.rectangle((pattern_x + i*5, pattern_y + j*5, pattern_x + i*5 + 3, pattern_y + j*5 + 3), fill=colors[col % 4])"""

new_func = r"""def _draw_metric_grid(
    draw: ImageDraw.ImageDraw,
    artifacts: ReportArtifacts,
    rect: tuple[int, int, int, int],
    label_font: ImageFont.ImageFont,
    value_font: ImageFont.ImageFont,
) -> None:
    x1, y1, x2, y2 = rect
    metrics = artifacts.headline_metrics[:8]
    sparks = artifacts.sparks if hasattr(artifacts, 'sparks') else {}
    columns = 4
    gap_x = 16
    gap_y = 16
    card_width = int((x2 - x1 - gap_x * (columns - 1)) / columns)
    rows = 2
    card_height = int((y2 - y1 - gap_y * (rows - 1)) / rows)
    colors = [CYAN, BLUE, AMBER, GREEN]

    for index, (label, value) in enumerate(metrics):
        row = index // columns
        col = index % columns
        card_x1 = x1 + col * (card_width + gap_x)
        card_y1 = y1 + row * (card_height + gap_y)
        card_x2 = card_x1 + card_width
        card_y2 = card_y1 + card_height
        draw.rectangle((card_x1, card_y1, card_x2, card_y2), fill=SURFACE, outline=BORDER, width=1)
        draw.rectangle((card_x1, card_y1, card_x1 + 4, card_y2), fill=colors[col % 4])
        draw.text((card_x1 + 18, card_y1 + 14), label.upper(), font=label_font, fill=DIM)
        _draw_wrapped_text(draw, value, (card_x1 + 18, card_y1 + 46), value_font, BRIGHT, card_width - 40, max_lines=2)

        data = sparks.get(label) if sparks else None
        if data and len(data) > 1:
            # Draw real sparkline
            w = 100
            h = 40
            px = card_x2 - w - 16
            py = card_y2 - h - 16
            mx = max(*data, 1)
            pts = []
            for i, v in enumerate(data):
                xx = px + i * (w / (len(data) - 1))
                yy = py + h - (v / mx) * h
                pts.append((xx, yy))
            
            # Subtle grid for sparkline
            for i in range(3):
                gy = py + i*(h/2)
                for dash_x in range(int(px), int(px+w), 8):
                    draw.line((dash_x, gy, dash_x+2, gy), fill=BORDER_HI, width=1)

            draw.line(pts, fill=colors[col % 4], width=2, joint="curve")
            for p in pts:
                draw.ellipse((p[0]-2, p[1]-2, p[0]+2, p[1]+2), fill=SURFACE, outline=colors[col % 4], width=1)
        else:
            # Draw abstract pattern
            pattern_x = card_x2 - 40
            pattern_y = card_y2 - 20
            for i in range(5):
                for j in range(2):
                    if (i+j) % 2 == 0:
                        draw.rectangle((pattern_x + i*5, pattern_y + j*5, pattern_x + i*5 + 3, pattern_y + j*5 + 3), fill=colors[col % 4])
"""

content = content.replace(old_func, new_func)

# Fix the call to _draw_metric_grid in build_pdf_bytes
content = content.replace(
    "_draw_metric_grid(draw_one, artifacts.headline_metrics, (PAGE_MARGIN, 200, PAGE_WIDTH - PAGE_MARGIN, 450), metric_label_font, metric_value_font)",
    "_draw_metric_grid(draw_one, artifacts, (PAGE_MARGIN, 200, PAGE_WIDTH - PAGE_MARGIN, 450), metric_label_font, metric_value_font)"
)

with open("pdf_builder.py", "w") as f:
    f.write(content)

