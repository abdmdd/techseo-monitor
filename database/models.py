from datetime import date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from database.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(120))
    name = Column(String(120))
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="user", server_default="user")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    site_pages = relationship("SitePage", back_populates="updated_by_user")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    last_used_at = Column(DateTime, nullable=False, server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    domain = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="projects")
    seo_checks = relationship("SEOCheck", back_populates="project", cascade="all, delete-orphan")


class Site(Base):
    __tablename__ = "sites"
    __table_args__ = (UniqueConstraint("user_id", "url", name="uq_sites_user_url"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)
    yandex_host = Column(String(500))
    google_property = Column(String(500))
    yandex_reviews_url = Column(Text)
    google_reviews_url = Column(Text)
    twogis_reviews_url = Column(Text)
    yandex_webmaster_connected = Column(Boolean, nullable=False, default=False, server_default="false")
    yandex_webmaster_token = Column(Text)
    yandex_webmaster_connected_at = Column(DateTime)
    yandex_metrika_connected = Column(Boolean, nullable=False, default=False, server_default="false")
    yandex_metrika_token = Column(Text)
    yandex_metrika_connected_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class SEOCheck(Base):
    __tablename__ = "seo_checks"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Integer)
    issues = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    project = relationship("Project", back_populates="seo_checks")


class AuditHistory(Base):
    __tablename__ = "audit_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    site_url = Column(String(500), nullable=False)
    audit_type = Column(String(50), nullable=False)
    seo_score = Column(Integer, nullable=False)
    errors_count = Column(Integer, nullable=False)
    title = Column(Text)
    description = Column(Text)
    canonical = Column(Text)
    h1 = Column(Text)
    robots_txt = Column(Text)
    sitemap = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class AuditJob(Base):
    __tablename__ = "audit_jobs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="SET NULL"), nullable=True, index=True)
    site_url = Column(String(500), nullable=False)
    audit_type = Column(String(50), nullable=False, default="monthly", server_default="monthly")
    task_id = Column(String(255), index=True)
    status = Column(String(50), nullable=False, default="queued", server_default="queued")
    progress = Column(Integer, nullable=False, default=0, server_default="0")
    error_message = Column(Text)
    result_json = Column(Text)
    seo_score = Column(Integer)
    errors_count = Column(Integer)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(80), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text)
    is_read = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class UserNotificationSettings(Base):
    __tablename__ = "user_notification_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    seo_alerts_enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    technical_notifications_enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    ai_notifications_enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    telegram_notifications_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    daily_summary = Column(Boolean, nullable=False, default=False, server_default="false")
    weekly_summary = Column(Boolean, nullable=False, default=True, server_default="true")
    critical_only = Column(Boolean, nullable=False, default=False, server_default="false")
    notify_index_drop = Column(Boolean, nullable=False, default=True, server_default="true")
    notify_404_spike = Column(Boolean, nullable=False, default=True, server_default="true")
    notify_robots_change = Column(Boolean, nullable=False, default=True, server_default="true")
    notify_site_down = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class AIUsage(Base):
    __tablename__ = "ai_usage"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_name = Column(String(120), nullable=False)
    usage_count = Column(Integer, nullable=False, default=1, server_default="1")
    usage_date = Column(Date, nullable=False, default=date.today)


class AIFeatureUsage(Base):
    __tablename__ = "ai_feature_usage"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feature = Column(String(120), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class SitePage(Base):
    __tablename__ = "site_pages"

    id = Column(Integer, primary_key=True)
    slug = Column(String(160), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    meta_title = Column(String(255))
    meta_description = Column(Text)
    content = Column(Text, nullable=False, default="")
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    updated_by_user = relationship("User", back_populates="site_pages")


class CMSBlock(Base):
    __tablename__ = "cms_blocks"

    id = Column(Integer, primary_key=True)
    key = Column(String(160), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class SEOMonitoringSettings(Base):
    __tablename__ = "seo_monitoring_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    frequency = Column(String(50), nullable=False, default="daily", server_default="daily")
    last_run_at = Column(String(80))
    next_run_at = Column(String(80))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class TelegramIntegration(Base):
    __tablename__ = "telegram_integrations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    telegram_chat_id = Column(String(120), nullable=False)
    telegram_username = Column(String(120))
    connected_at = Column(DateTime, nullable=False, server_default=func.now())
    status = Column(String(50), nullable=False, default="connected", server_default="connected")


class AIAuditInsight(Base):
    __tablename__ = "ai_audit_insights"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    audit_id = Column(Integer, ForeignKey("audit_jobs.id", ondelete="SET NULL"))
    summary_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class SERPResultsCache(Base):
    __tablename__ = "serp_results_cache"

    id = Column(Integer, primary_key=True)
    query = Column(String(255), nullable=False)
    city = Column(String(255))
    own_site = Column(String(255))
    results_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class CompetitorAnalysisUsage(Base):
    __tablename__ = "competitor_analysis_usage"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class YandexTrafficSnapshot(Base):
    __tablename__ = "yandex_traffic_snapshots"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    counter_id = Column(String(120), nullable=False)
    date_from = Column(String(30), nullable=False)
    date_to = Column(String(30), nullable=False)
    visits = Column(Integer, nullable=False, default=0, server_default="0")
    pageviews = Column(Integer, nullable=False, default=0, server_default="0")
    users = Column(Integer, nullable=False, default=0, server_default="0")
    bounce_rate = Column(Float, nullable=False, default=0, server_default="0")
    search_visits = Column(Integer, nullable=False, default=0, server_default="0")
    ads_visits = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class YandexIntegration(Base):
    __tablename__ = "yandex_integrations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"))
    service_type = Column(String(80), nullable=False)
    access_token = Column(Text)
    refresh_token = Column(Text)
    expires_at = Column(String(80))
    connected_at = Column(DateTime, nullable=False, server_default=func.now())
    status = Column(String(50), nullable=False, default="connected", server_default="connected")


class QuarterlyAuditCheck(Base):
    __tablename__ = "quarterly_audit_checks"
    __table_args__ = (UniqueConstraint("user_id", "site_id", "check_key", name="uq_quarterly_checks_user_site_key"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    check_key = Column(String(120), nullable=False)
    status = Column(String(80))
    comment = Column(Text)
    checked_at = Column(String(80))
    checked_by = Column(String(120))
    mobile_score = Column(Integer)
    desktop_score = Column(Integer)
    lcp = Column(Float)
    inp = Column(Float)
    cls = Column(Float)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class QuarterlyAuditHistory(Base):
    __tablename__ = "quarterly_audit_history"

    id = Column(Integer, primary_key=True)
    check_id = Column(Integer, ForeignKey("quarterly_audit_checks.id", ondelete="CASCADE"), nullable=False)
    old_status = Column(String(80))
    new_status = Column(String(80))
    old_comment = Column(Text)
    new_comment = Column(Text)
    changed_at = Column(DateTime, nullable=False, server_default=func.now())
    changed_by = Column(String(120))
