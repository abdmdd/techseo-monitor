from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Service health status", examples=["ok"])


class ErrorResponse(BaseModel):
    success: bool = Field(default=False, description="Always false for error responses")
    error: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable error message")


class AuditResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: str = Field(description="Audited URL")
    title: str | None = Field(default=None, description="Page title or fallback value")
    description: str | None = Field(default=None, description="Meta description or fallback value")
    canonical: str | None = Field(default=None, description="Canonical URL or fallback value")
    h1: str | None = Field(default=None, description="H1 text or fallback value")
    robots_txt: str | None = Field(default=None, description="robots.txt status")
    sitemap: str | None = Field(default=None, description="sitemap.xml status")
    errors: list[str] = Field(default_factory=list, description="Crawler findings that affect SEO score")
    recommendations: list[str] = Field(default_factory=list, description="Suggested fixes")
    crawler_warnings: list[str] = Field(default_factory=list, description="Non-fatal crawler/runtime warnings")


class AuditResponse(BaseModel):
    success: bool = Field(default=True, description="Whether the audit request completed")
    audit_type: str = Field(description="Audit type: monthly or quarterly")
    url: str = Field(description="Input URL")
    score: int = Field(description="SEO score calculated by services.score_service")
    errors_count: int = Field(description="Number of crawler errors used for score")
    result: AuditResult = Field(description="Detailed crawler result")
    advanced_checks: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional quarterly checks; empty for monthly audit"
    )
