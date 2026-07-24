import math
from datetime import date
from html import escape
from pathlib import Path


CARD_BACKGROUND = "#0d1117"
PLOT_BACKGROUND = "#161b22"
TEXT_PRIMARY = "#f0f6fc"
TEXT_SECONDARY = "#8b949e"
BORDER = "#30363d"
BLUE = "#58a6ff"
GREEN = "#3fb950"
YELLOW = "#f2cc60"
PINK = "#f778ba"
FONT = "Segoe UI, Liberation Sans, sans-serif"
CARD_WIDTH = 840


def ensure_assets(path):
    Path(path).mkdir(exist_ok=True)


def format_count(count):
    return f"{int(count):,}".replace(",", ".")


def save_total_trend(series, path):
    width = CARD_WIDTH
    height = 480
    plot_x = 66
    plot_y = 184
    plot_width = 732
    plot_height = 190
    latest = _latest(series)
    latest_date = latest.get("date")
    total_label_x = 52 + len(format_count(latest["total"])) * 22

    max_value = max((item["total"] for item in series), default=0)
    y_max, y_ticks = _axis_scale(max_value)
    x_ticks = _date_ticks(series)

    grid = []
    for value in y_ticks:
        y = _scale_y(value, y_max, plot_y, plot_height)
        grid.append(
            f'<line x1="{plot_x}" y1="{y:.2f}" x2="{plot_x + plot_width}" '
            f'y2="{y:.2f}" stroke="{BORDER}" stroke-width="1" opacity="0.72"/>'
            f'<text x="{plot_x - 12}" y="{y + 4:.2f}" text-anchor="end" '
            f'fill="{TEXT_SECONDARY}" font-size="11" font-family="{FONT}">'
            f'{format_count(value)}</text>'
        )

    for tick_date in x_ticks:
        x = _scale_x(tick_date, series, plot_x, plot_width)
        grid.append(
            f'<line x1="{x:.2f}" y1="{plot_y}" x2="{x:.2f}" '
            f'y2="{plot_y + plot_height}" stroke="{BORDER}" stroke-width="1" opacity="0.36"/>'
            f'<text x="{x:.2f}" y="{plot_y + plot_height + 23}" text-anchor="middle" '
            f'fill="{TEXT_SECONDARY}" font-size="11" font-family="{FONT}">'
            f'{escape(_date_tick_label(tick_date, series))}</text>'
        )

    total_path = _line_path(series, "total", y_max, plot_x, plot_y, plot_width, plot_height)
    internal_path = _line_path(series, "internal", y_max, plot_x, plot_y, plot_width, plot_height)
    external_path = _line_path(series, "external", y_max, plot_x, plot_y, plot_width, plot_height)
    area_path = _area_path(series, "total", y_max, plot_x, plot_y, plot_width, plot_height)

    endpoints = []
    if series:
        end_x = plot_x + plot_width
        for key, color in (("total", GREEN), ("internal", BLUE), ("external", YELLOW)):
            end_y = _scale_y(latest[key], y_max, plot_y, plot_height)
            endpoints.append(
                f'<circle cx="{end_x}" cy="{end_y:.2f}" r="4.5" fill="{CARD_BACKGROUND}" '
                f'stroke="{color}" stroke-width="2.5"/>'
            )

    legend = _trend_legend(latest, y=428)
    content = f"""
{_card_header("GitHub contributions", "Cumulative organization activity since 2026")}
<text x="36" y="156" fill="{GREEN}" font-size="38" font-weight="800" font-family="{FONT}">{format_count(latest["total"])}</text>
<text x="{total_label_x}" y="154" fill="{TEXT_SECONDARY}" font-size="13" font-weight="700" font-family="{FONT}">total contributions</text>
<rect x="{plot_x}" y="{plot_y}" width="{plot_width}" height="{plot_height}" rx="12" fill="{PLOT_BACKGROUND}" stroke="{BORDER}"/>
{''.join(grid)}
<g clip-path="url(#plotClip)">
  <path d="{area_path}" fill="url(#areaGradient)"/>
  <path d="{total_path}" fill="none" stroke="{GREEN}" stroke-width="3.2" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="{internal_path}" fill="none" stroke="{BLUE}" stroke-width="2.3" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="{external_path}" fill="none" stroke="{YELLOW}" stroke-width="2.3" stroke-linejoin="round" stroke-linecap="round"/>
</g>
{''.join(endpoints)}
{legend}
{_card_footer(latest_date, height)}
"""
    _write_svg(
        path,
        width,
        height,
        "GISA cumulative GitHub contribution trend",
        "Cumulative total, GISA-OSS, and external contributions over time.",
        content,
        extra_defs=f"""
  <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{GREEN}" stop-opacity="0.24"/>
    <stop offset="100%" stop-color="{GREEN}" stop-opacity="0.02"/>
  </linearGradient>
  <clipPath id="plotClip"><rect x="{plot_x}" y="{plot_y}" width="{plot_width}" height="{plot_height}" rx="12"/></clipPath>
""",
    )


def save_total_trend_histogram(series, path):
    width = CARD_WIDTH
    height = 480
    plot_x = 66
    plot_y = 184
    plot_width = 732
    plot_height = 190
    latest = _latest(series)
    latest_date = latest.get("date")
    total_label_x = 52 + len(format_count(latest["total"])) * 22
    months = _monthly_contributions(series)
    max_value = max((item["total"] for item in months), default=0)
    y_max, y_ticks = _axis_scale(max_value)

    grid = []
    for value in y_ticks:
        y = _scale_y(value, y_max, plot_y, plot_height)
        grid.append(
            f'<line x1="{plot_x}" y1="{y:.2f}" x2="{plot_x + plot_width}" '
            f'y2="{y:.2f}" stroke="{BORDER}" stroke-width="1" opacity="0.72"/>'
            f'<text x="{plot_x - 12}" y="{y + 4:.2f}" text-anchor="end" '
            f'fill="{TEXT_SECONDARY}" font-size="11" font-family="{FONT}">'
            f'{format_count(value)}</text>'
        )

    bars = []
    labels = []
    month_count = len(months)
    if month_count:
        slot_width = plot_width / month_count
        label_interval = max(1, math.ceil(month_count / 10))
        multiple_years = len({item["date"].year for item in months}) > 1

        for index, item in enumerate(months):
            x = round(plot_x + index * slot_width, 2)
            next_x = round(plot_x + (index + 1) * slot_width, 2)
            bar_width = next_x - x
            internal_y = _scale_y(
                item["internal"], y_max, plot_y, plot_height
            )
            total_y = _scale_y(item["total"], y_max, plot_y, plot_height)
            bottom = plot_y + plot_height
            internal_height = bottom - internal_y
            external_height = internal_y - total_y

            if internal_height > 0:
                bars.append(
                    f'<rect x="{x:.2f}" y="{internal_y:.2f}" '
                    f'width="{bar_width:.2f}" height="{internal_height:.2f}" '
                    f'fill="{BLUE}"/>'
                )
            if external_height > 0:
                bars.append(
                    f'<rect x="{x:.2f}" y="{total_y:.2f}" '
                    f'width="{bar_width:.2f}" height="{external_height:.2f}" '
                    f'fill="{YELLOW}"/>'
                )

            if index % label_interval == 0 or index == month_count - 1:
                label = item["date"].strftime(
                    "%b %Y" if multiple_years else "%b"
                )
                labels.append(
                    f'<text x="{x + bar_width / 2:.2f}" '
                    f'y="{plot_y + plot_height + 23}" text-anchor="middle" '
                    f'fill="{TEXT_SECONDARY}" font-size="11" font-family="{FONT}">'
                    f'{escape(label)}</text>'
                )

    content = f"""
{_card_header("Monthly GitHub contributions", "Organization activity added per month since 2026")}
<text x="36" y="156" fill="{GREEN}" font-size="38" font-weight="800" font-family="{FONT}">{format_count(latest["total"])}</text>
<text x="{total_label_x}" y="154" fill="{TEXT_SECONDARY}" font-size="13" font-weight="700" font-family="{FONT}">total contributions</text>
<rect x="{plot_x}" y="{plot_y}" width="{plot_width}" height="{plot_height}" rx="12" fill="{PLOT_BACKGROUND}" stroke="{BORDER}"/>
{''.join(grid)}
<g clip-path="url(#histogramClip)">{''.join(bars)}</g>
{''.join(labels)}
{_histogram_legend(y=428)}
{_card_footer(latest_date, height)}
"""
    _write_svg(
        path,
        width,
        height,
        "GISA monthly GitHub contribution histogram",
        "Monthly GISA-OSS and external contributions shown as stacked bars.",
        content,
        extra_defs=f'<clipPath id="histogramClip"><rect x="{plot_x}" y="{plot_y}" width="{plot_width}" height="{plot_height}" rx="12"/></clipPath>',
    )


def _write_svg(path, width, height, title, description, content, extra_defs=""):
    svg = f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title description">
<title id="title">{escape(title)}</title>
<desc id="description">{escape(description)}</desc>
{_card_defs(extra_defs)}
{_card_background(width, height)}
{_dot_design()}
{content}
</svg>
"""
    Path(path).write_text(svg, encoding="utf-8")


def _card_header(title, subtitle):
    return f"""
<text x="36" y="42" fill="{GREEN}" font-size="12" font-weight="700" letter-spacing="2" font-family="{FONT}">GISA OPEN-SOURCE-SOFTWARE</text>
<text x="36" y="78" fill="{TEXT_PRIMARY}" font-size="26" font-weight="800" font-family="{FONT}">{escape(title)}</text>
<text x="36" y="103" fill="{TEXT_SECONDARY}" font-size="13" font-family="{FONT}">{escape(subtitle)}</text>"""


def _card_footer(data_through, height):
    label = _data_through_label(data_through)
    y = height - 15
    return f"""
<line x1="36" y1="{y - 17}" x2="804" y2="{y - 17}" stroke="{BORDER}" opacity="0.75"/>
<text x="36" y="{y}" fill="{TEXT_SECONDARY}" font-size="11" font-family="{FONT}">{escape(label)}</text>
<text x="804" y="{y}" text-anchor="end" fill="{TEXT_SECONDARY}" font-size="11" font-family="{FONT}">Updated weekly</text>"""


def _card_defs(extra_defs=""):
    return f"""
<defs>
  <linearGradient id="cardGradient" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{CARD_BACKGROUND}"/>
    <stop offset="56%" stop-color="#111827"/>
    <stop offset="100%" stop-color="#052e2b"/>
  </linearGradient>
  <radialGradient id="glow" cx="84%" cy="16%" r="70%">
    <stop offset="0%" stop-color="{BLUE}" stop-opacity="0.32"/>
    <stop offset="48%" stop-color="{GREEN}" stop-opacity="0.11"/>
    <stop offset="100%" stop-color="{CARD_BACKGROUND}" stop-opacity="0"/>
  </radialGradient>
{extra_defs}</defs>"""


def _card_background(width, height):
    return f"""
<rect width="{width}" height="{height}" rx="24" fill="url(#cardGradient)"/>
<rect width="{width}" height="{height}" rx="24" fill="url(#glow)"/>
<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="23" fill="none" stroke="{BORDER}"/>"""


def _dot_design():
    return f"""
<g aria-hidden="true" opacity="0.88">
  <circle cx="716" cy="42" r="5" fill="{GREEN}"/>
  <circle cx="772" cy="58" r="3.5" fill="{BLUE}"/>
  <circle cx="704" cy="88" r="3" fill="{YELLOW}"/>
  <circle cx="786" cy="103" r="2.5" fill="{PINK}"/>
  <path d="M716 42 L772 58 L704 88 L786 103" fill="none" stroke="{TEXT_SECONDARY}" stroke-width="1.2" opacity="0.38"/>
</g>"""


def _trend_legend(latest, y):
    items = [
        (36, "Total", latest["total"], GREEN),
        (240, "GISA-OSS", latest["internal"], BLUE),
        (454, "External", latest["external"], YELLOW),
    ]
    parts = []
    for x, label, value, color in items:
        parts.append(
            f'<line x1="{x}" y1="{y - 4}" x2="{x + 28}" y2="{y - 4}" '
            f'stroke="{color}" stroke-width="3" stroke-linecap="round"/>'
            f'<text x="{x + 38}" y="{y}" fill="{TEXT_PRIMARY}" font-size="12" '
            f'font-weight="700" font-family="{FONT}">{label}</text>'
            f'<text x="{x + 112}" y="{y}" fill="{TEXT_SECONDARY}" font-size="12" '
            f'font-family="{FONT}">{format_count(value)}</text>'
        )
    return "".join(parts)


def _histogram_legend(y):
    items = [
        (240, "GISA-OSS", BLUE),
        (454, "External", YELLOW),
    ]
    parts = []
    for x, label, color in items:
        parts.append(
            f'<rect x="{x}" y="{y - 13}" width="14" height="14" rx="3" '
            f'fill="{color}"/>'
            f'<text x="{x + 24}" y="{y}" fill="{TEXT_PRIMARY}" font-size="12" '
            f'font-weight="700" font-family="{FONT}">{label}</text>'
        )
    return "".join(parts)


def _latest(series):
    if series:
        return series[-1]
    return {"date": None, "total": 0, "internal": 0, "external": 0}


def _data_through_label(value):
    if not isinstance(value, date):
        return "No contribution data available"
    return f"Data through {value.day} {value.strftime('%b %Y')}"


def _monthly_contributions(series):
    month_ends = {}
    for item in series:
        month_ends[(item["date"].year, item["date"].month)] = item

    previous = {"total": 0, "internal": 0, "external": 0}
    months = []
    for (year, month), current in month_ends.items():
        values = {
            key: current[key] - previous[key]
            for key in ("total", "internal", "external")
        }
        months.append({"date": date(year, month, 1), **values})
        previous = current
    return months


def _axis_scale(value):
    value = max(int(value), 1)
    rough_step = value / 4
    magnitude = 10 ** math.floor(math.log10(rough_step))
    normalized = rough_step / magnitude
    if normalized <= 1:
        step = magnitude
    elif normalized <= 2:
        step = 2 * magnitude
    elif normalized <= 5:
        step = 5 * magnitude
    else:
        step = 10 * magnitude
    step = max(int(step), 1)
    axis_max = max(step, math.ceil(value / step) * step)
    return axis_max, list(range(0, axis_max + 1, step))


def _date_ticks(series):
    if not series:
        return []
    first = series[0]["date"]
    last = series[-1]["date"]
    ticks = [first]
    current = date(first.year, first.month, 1)
    while current <= last:
        if current > first:
            ticks.append(current)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    if ticks[-1] != last and (last - ticks[-1]).days > 18:
        ticks.append(last)
    return ticks


def _date_tick_label(value, series):
    years = {item["date"].year for item in series}
    return value.strftime("%b %Y") if len(years) > 1 else value.strftime("%b")


def _scale_x(value, series, plot_x, plot_width):
    if not series or series[0]["date"] == series[-1]["date"]:
        return plot_x
    first = series[0]["date"]
    span = (series[-1]["date"] - first).days
    return plot_x + ((value - first).days / span) * plot_width


def _scale_y(value, y_max, plot_y, plot_height):
    return plot_y + plot_height - (value / y_max) * plot_height


def _line_points(series, key, y_max, plot_x, plot_y, plot_width, plot_height):
    return [
        (
            _scale_x(item["date"], series, plot_x, plot_width),
            _scale_y(item[key], y_max, plot_y, plot_height),
        )
        for item in series
    ]


def _line_path(series, key, y_max, plot_x, plot_y, plot_width, plot_height):
    points = _line_points(series, key, y_max, plot_x, plot_y, plot_width, plot_height)
    if not points:
        return ""
    commands = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
    commands.extend(f"L {x:.2f} {y:.2f}" for x, y in points[1:])
    return " ".join(commands)


def _area_path(series, key, y_max, plot_x, plot_y, plot_width, plot_height):
    points = _line_points(series, key, y_max, plot_x, plot_y, plot_width, plot_height)
    if not points:
        return ""
    bottom = plot_y + plot_height
    commands = [f"M {points[0][0]:.2f} {bottom:.2f}"]
    commands.extend(f"L {x:.2f} {y:.2f}" for x, y in points)
    commands.append(f"L {points[-1][0]:.2f} {bottom:.2f} Z")
    return " ".join(commands)
