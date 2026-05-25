import streamlit as st

from database.db import (
    get_audit_history,
    get_quarterly_audit_checks,
    get_quarterly_audit_history,
    get_sites,
)


@st.cache_data(ttl=60, show_spinner=False)
def cached_get_sites(user_id=None):
    return get_sites(user_id=user_id)


@st.cache_data(ttl=60, show_spinner=False)
def cached_get_audit_history(user_id=None):
    return get_audit_history(user_id=user_id)


@st.cache_data(ttl=60, show_spinner=False)
def cached_get_quarterly_audit_checks(user_id):
    return get_quarterly_audit_checks(user_id=user_id)


@st.cache_data(ttl=60, show_spinner=False)
def cached_get_quarterly_audit_history(user_id, site_id=None, limit=80):
    return get_quarterly_audit_history(user_id=user_id, site_id=site_id, limit=limit)


def clear_cached_data():
    st.cache_data.clear()
