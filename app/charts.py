"""Charts for the analytics pages, drawn on the server as plain SVG.

The same numbers can be drawn three ways (bar, line, area). Because the picture is part of the
page, it works without JavaScript, follows the light/dark theme through CSS variables, and shows
its digits in the page language (the caller passes `num`, e.g. Hindi digits).
"""

from collections.abc import Callable, Iterator, Sequence
from html import escape

from markupsafe import Markup

KINDS = ("bar", "line", "area")
WIDTH, HEIGHT = 640, 250
LEFT, RIGHT, TOP, BOTTOM = 40, 12, 14, 30


def nice_max(peak: int) -> int:
    """A round top for the y axis, so its four steps are whole numbers (clicks are)."""
    if peak <= 4:
        return 4
    step = -(-peak // 4)  # peak / 4, rounded up
    scale = 10 ** (len(str(step)) - 1)
    for base in (1, 2, 3, 4, 5, 6, 8, 10):
        if base * scale >= step:
            return base * scale * 4
    return 10 * scale * 4  # unreachable, kept for safety


def _n(value: float) -> str:
    """A short number for SVG coordinates: 12.5, 7, 0.3."""
    return f"{value:.1f}".rstrip("0").rstrip(".") or "0"


def _runs(values: Sequence[int | None]) -> Iterator[list[tuple[int, int]]]:
    """Stretches of consecutive known values. A None (the future) ends a stretch."""
    run: list[tuple[int, int]] = []
    for i, value in enumerate(values):
        if value is None:
            if run:
                yield run
            run = []
        else:
            run.append((i, value))
    if run:
        yield run


def chart_svg(
    kind: str,
    labels: Sequence[str],
    series: Sequence[dict],
    *,
    aria: str,
    num: Callable[[int], str] = str,
    tip_labels: Sequence[str] | None = None,
    label_every: int = 1,
) -> Markup:
    """One chart as an <svg>.

    labels      the text under each position on the x axis
    series      [{"name": str | None, "values": [int | None, ...], "color": css colour}, ...]
                None means "has not happened yet" (nothing is drawn there)
    tip_labels  the longer text for the hover tooltip (defaults to labels)
    """
    if kind not in KINDS:
        raise KeyError(kind)  # a programming mistake, never shown to a visitor
    count = len(labels)
    tip_labels = tip_labels or labels
    peak = max((v for s in series for v in s["values"] if v), default=0)
    top = nice_max(peak)
    plot_w, plot_h = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM
    slot = plot_w / count
    base = TOP + plot_h
    radius = 4 if count > 16 else 5  # smaller dots when there are many points

    def x_at(i: int) -> float:
        return LEFT + slot * (i + 0.5)

    def y_at(value: float) -> float:
        return TOP + plot_h * (1 - value / top)

    out = [
        f'<svg class="chart-svg chart-{kind}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        f'aria-label="{escape(aria)}"><title>{escape(aria)}</title>'
    ]

    for step in range(5):  # grid lines and the numbers on the left
        value = top * step // 4
        y = _n(y_at(value))
        out.append(f'<line class="c-grid" x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{y}" y2="{y}"/>')
        out.append(
            f'<text class="c-text" x="{LEFT - 8}" y="{_n(y_at(value) + 3.5)}" text-anchor="end">'
            f"{escape(num(value))}</text>"
        )

    if kind == "bar":
        group = slot * 0.72
        each = group / len(series)
        for k, s in enumerate(series):
            for i, value in enumerate(s["values"]):
                if not value:
                    continue
                height = plot_h * value / top
                out.append(
                    f'<rect class="c-bar" x="{_n(x_at(i) - group / 2 + each * k)}" '
                    f'y="{_n(base - height)}" width="{_n(max(each - 1, 1))}" height="{_n(height)}" '
                    f'rx="2" style="fill:{s["color"]}"/>'
                )
                if len(series) == 1:  # one link: write the number above each bar
                    out.append(
                        f'<text class="c-val" x="{_n(x_at(i))}" y="{_n(base - height - 4)}" '
                        f'text-anchor="middle">{escape(num(value))}</text>'
                    )
    else:
        for s in series:
            color = s["color"]
            for run in _runs(s["values"]):
                points = [(x_at(i), y_at(v)) for i, v in run]
                line = "M" + " L".join(f"{_n(x)} {_n(y)}" for x, y in points)
                if kind == "area":
                    area = f"M{_n(points[0][0])} {_n(base)} L" + " L".join(
                        f"{_n(x)} {_n(y)}" for x, y in points
                    ) + f" L{_n(points[-1][0])} {_n(base)} Z"
                    out.append(f'<path class="c-area" d="{area}" style="fill:{color}"/>')
                out.append(f'<path class="c-line" d="{line}" style="stroke:{color}"/>')
                for x, y in points:
                    out.append(
                        f'<circle class="c-dot" cx="{_n(x)}" cy="{_n(y)}" r="{radius}" '
                        f'style="stroke:{color}"/>'
                    )

    for i, text in enumerate(labels):  # x axis
        if i % label_every == 0:
            out.append(
                f'<text class="c-text" x="{_n(x_at(i))}" y="{HEIGHT - 9}" text-anchor="middle">'
                f"{escape(text)}</text>"
            )

    for i in range(count):  # the hover areas: one tooltip per position, for every chart type
        known = [(s, s["values"][i]) for s in series if s["values"][i] is not None]
        if not known:
            continue
        if len(series) == 1:
            tip = f"{tip_labels[i]}: {num(known[0][1])}"
        else:
            tip = "\n".join([tip_labels[i]] + [f"{s['name']}: {num(v)}" for s, v in known])
        out.append(
            f'<rect class="c-hit" x="{_n(LEFT + slot * i)}" y="{TOP}" width="{_n(slot)}" '
            f'height="{_n(plot_h)}"><title>{escape(tip)}</title></rect>'
        )

    out.append("</svg>")
    return Markup("".join(out))


def chart_set(labels: Sequence[str], series: Sequence[dict], **options) -> dict[str, Markup]:
    """The same chart in every kind: {"bar": svg, "line": svg, "area": svg}."""
    return {kind: chart_svg(kind, labels, series, **options) for kind in KINDS}
