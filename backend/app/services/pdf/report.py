"""Executive summary PDF via WeasyPrint (Jinja2 template + CSS bars, no chart libs in Phase 1)."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Portfolio, Report
from app.schemas.analytics import PerformanceResponse, PortfolioOverview, RiskResponse

logger = logging.getLogger("app.pdf")

_env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates")),
    autoescape=select_autoescape(["html"]),
)


def _fmt_inr(value: float | None) -> str:
    if value is None:
        return "—"
    # Indian digit grouping: 12,34,56,789.00
    neg = value < 0
    value = abs(value)
    whole, _, frac = f"{value:.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{'-' if neg else ''}₹{whole}.{frac}"


def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}%"


def _fmt_num(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def generate_executive_summary(
    db: Session,
    portfolio: Portfolio,
    overview: PortfolioOverview,
    performance: PerformanceResponse | None,
    risk: RiskResponse | None,
    generated_by_id=None,
) -> Report:
    from weasyprint import HTML  # imported lazily: needs system pango libs

    settings = get_settings()
    os.makedirs(settings.REPORT_DIR, exist_ok=True)

    template = _env.get_template("executive_summary.html")
    html = template.render(
        portfolio=portfolio,
        client=portfolio.client,
        overview=overview,
        performance=performance,
        risk=risk,
        generated_at=datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        fmt_inr=_fmt_inr, fmt_pct=_fmt_pct, fmt_num=_fmt_num,
    )

    filename = f"exec_summary_{portfolio.id.hex[:8]}_{uuid.uuid4().hex[:6]}.pdf"
    path = os.path.join(settings.REPORT_DIR, filename)
    HTML(string=html).write_pdf(path)

    report = Report(portfolio_id=portfolio.id, kind="EXECUTIVE_SUMMARY",
                    file_path=path, generated_by_id=generated_by_id,
                    params={"as_of": overview.as_of.isoformat()})
    db.add(report)
    db.flush()
    logger.info("Executive summary generated: %s", path)
    return report
