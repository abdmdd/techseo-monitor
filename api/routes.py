import logging
from collections.abc import Callable
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query

from api.schemas import AuditResponse, ErrorResponse, HealthResponse
from services.audit_service import run_monthly_audit, run_quarterly_audit


logger = logging.getLogger(__name__)
router = APIRouter(tags=["TechSEO Monitor"])


def validate_url(url: str):
    parsed = urlparse((url or "").strip())

    if parsed.scheme not in ["http", "https"] or not parsed.netloc:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "invalid_url",
                "message": "URL must include http:// or https:// and a valid host."
            }
        )


def classify_audit_failure(audit_data, url: str):
    result = audit_data.get("result", {})
    errors = result.get("errors", [])
    warnings = result.get("crawler_warnings", [])
    combined = " ".join([*errors, *warnings]).lower()

    if any(marker in combined for marker in ["timeout", "timed out"]):
        return 408, "audit_timeout", "Audit timed out while checking the target site."

    if any(marker in combined for marker in ["playwright", "chromium"]):
        logger.warning(
            "Audit completed with Playwright fallback for %s; warnings_count=%s",
            url,
            len(warnings)
        )

    return None


def build_audit_response(url: str, audit_type: str, audit_runner: Callable[[str], dict]):
    validate_url(url)

    try:
        audit_data = audit_runner(url)
    except TimeoutError:
        logger.warning("Audit timeout for %s", url)
        raise HTTPException(
            status_code=408,
            detail={
                "success": False,
                "error": "audit_timeout",
                "message": "Audit timed out while checking the target site."
            }
        )
    except Exception:
        logger.exception("Unexpected audit failure for %s", url)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "crawler_failure",
                "message": "Crawler failed unexpectedly. Check server logs for details."
            }
        )

    classified_failure = classify_audit_failure(audit_data, url)

    if classified_failure:
        status_code, error_code, message = classified_failure
        logger.warning("%s for %s: %s", error_code, url, message)
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "error": error_code,
                "message": message
            }
        )

    result = audit_data.get("result", {})
    errors = result.get("errors", [])

    if result.get("main_page_fetch_source") == "error" and errors:
        logger.error("Crawler failure for %s: %s", url, errors[:3])
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "crawler_failure",
                "message": "Crawler could not fetch the target site."
            }
        )

    return {
        "success": True,
        "audit_type": audit_type,
        "url": url,
        "score": audit_data.get("score", 0),
        "errors_count": audit_data.get("errors_count", 0),
        "result": result,
        "advanced_checks": audit_data.get("advanced_checks", {})
    }


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns a simple service health status."
)
def health_check():
    return {"status": "ok"}


@router.get(
    "/audit/monthly",
    response_model=AuditResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid URL"},
        408: {"model": ErrorResponse, "description": "Audit timeout"},
        500: {"model": ErrorResponse, "description": "Crawler failure"},
    },
    summary="Run monthly SEO audit",
    description="Runs the standard technical SEO crawler and returns a stable audit response schema."
)
def monthly_audit(
    url: str = Query(..., description="Full URL to audit, including http:// or https://")
):
    return build_audit_response(
        url=url,
        audit_type="monthly",
        audit_runner=run_monthly_audit
    )


@router.get(
    "/audit/quarterly",
    response_model=AuditResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid URL"},
        408: {"model": ErrorResponse, "description": "Audit timeout"},
        500: {"model": ErrorResponse, "description": "Crawler failure"},
    },
    summary="Run quarterly SEO audit",
    description="Runs the extended technical SEO audit and returns the same response schema as the monthly endpoint."
)
def quarterly_audit(
    url: str = Query(..., description="Full URL to audit, including http:// or https://")
):
    return build_audit_response(
        url=url,
        audit_type="quarterly",
        audit_runner=run_quarterly_audit
    )
