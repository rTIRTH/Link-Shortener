"""An address a cron service can open to make the site send the alerts that are due."""
import hmac

from fastapi import APIRouter, Header, HTTPException, Query, Request

from .. import alerts
from ..config import settings
from ..resettoken import site_url

router = APIRouter()


@router.api_route("/run-alerts", methods=["GET", "POST"], include_in_schema=False)
def run_alerts(
    request: Request,
    key: str = Query(""),
    authorization: str = Header(""),
):
    """Needs CRON_SECRET (as ?key=... or a Bearer header). Without it, this page does not exist."""
    given = key or authorization.removeprefix("Bearer ").strip()
    secret = settings.cron_secret
    if not secret or not hmac.compare_digest(given.encode(), secret.encode()):
        raise HTTPException(404, "Not Found")
    sent = alerts.send_due_alerts(request.app.state.session_factory, site_url(request))
    return {"sent": sent}
