import streamlit as st

from services.auth_service import authenticate_user, get_public_user, register_user


def init_auth_state():
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = None

    if st.session_state.auth_user:
        user = get_public_user(st.session_state.auth_user["id"])
        st.session_state.auth_user = user


def get_current_user():
    return st.session_state.get("auth_user")


def require_user_id():
    user = get_current_user()
    return user["id"] if user else None


def logout():
    st.session_state.auth_user = None
    st.rerun()


def show_auth_page():
    st.markdown('<div class="ts-page-title">TechSEO Monitor</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ts-page-subtitle">Войдите в аккаунт, чтобы управлять своими сайтами, аудитами и PDF-отчетами.</div>',
        unsafe_allow_html=True
    )

    left, center, right = st.columns([1, 1.15, 1])

    with center:
        st.markdown(
            """
            <div style="
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                padding: 22px 22px 10px 22px;
                background: #ffffff;
                box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
            ">
            """,
            unsafe_allow_html=True
        )

        tab_login, tab_register = st.tabs(["Вход", "Регистрация"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Пароль", type="password")
                submitted = st.form_submit_button("Войти", type="primary", use_container_width=True)

                if submitted:
                    user = authenticate_user(email, password)

                    if user:
                        st.session_state.auth_user = user
                        st.success("Вход выполнен.")
                        st.rerun()
                    else:
                        st.error("Неверный email или пароль.")

        with tab_register:
            with st.form("register_form"):
                email = st.text_input("Email", placeholder="you@example.com", key="register_email")
                password = st.text_input("Пароль", type="password", key="register_password")
                password_confirm = st.text_input("Повторите пароль", type="password")
                submitted = st.form_submit_button("Создать аккаунт", type="primary", use_container_width=True)

                if submitted:
                    if password != password_confirm:
                        st.error("Пароли не совпадают.")
                    else:
                        user, error = register_user(email, password)

                        if error:
                            st.error(error)
                        else:
                            st.session_state.auth_user = user
                            st.success("Аккаунт создан.")
                            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
