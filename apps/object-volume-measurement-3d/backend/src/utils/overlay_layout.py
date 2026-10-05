"""Layout text as separate annotations: the viewer does not render newlines."""

import textwrap


def draw_label(
    helper, text, position, width, height, *, color, background_color=None, size=16
):
    margin = 8
    padding_x, padding_y = 4, 2  # Viewer text-background padding in image pixels.
    line_height = size + 2 * padding_y + 2
    # Reserve a full em plus headroom per character, including wide class names.
    char_width = size * 1.1
    max_chars = max(1, int((width - 2 * margin - 2 * padding_x) / char_width))
    lines = []
    for paragraph in text.splitlines():
        lines.extend(textwrap.wrap(paragraph, width=max_chars) or [""])
    if not lines:
        return
    max_lines = max(1, int((height - 2 * margin) / line_height))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max_chars - 1] + "…"

    box_width = max(len(line) for line in lines) * char_width + 2 * padding_x
    box_height = len(lines) * line_height
    x = max(margin, min(position[0] * width, width - margin - box_width))
    y = max(margin, min(position[1] * height, height - margin - box_height))
    for index, line in enumerate(lines):
        helper.draw_text(
            line,
            (x / width, (y + index * line_height) / height),
            color=color,
            background_color=background_color,
            size=size,
        )
