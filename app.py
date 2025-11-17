from utils import register_nav_pages, get_supabase
import streamlit as st
from supabase import Client
from components import animated_typing_title, apply_nav_title
import pandas as pd
import os
import plotly.express as px

# run if you're getting key error "'supbase'"
# st.cache_data.clear()
# st.cache_resource.clear()

st.set_page_config(
    page_title="UF AIS Financial Management System",
    layout="wide",                # ← forces wide mode
    initial_sidebar_state="auto"   # or "expanded" if you want the sidebar open
)


# Initialize Supabase client
supabase: Client = get_supabase()

# Utility functions for user session management
def get_user_session_data(key, default=None):
    """Get user-specific session data safely"""
    if "current_user_key" in st.session_state:
        user_key = st.session_state.current_user_key
        if "user_specific_data" in st.session_state and user_key in st.session_state.user_specific_data:
            return st.session_state.user_specific_data[user_key].get(key, default)
    return default

def set_user_session_data(key, value):
    """Set user-specific session data safely"""
    if "current_user_key" in st.session_state:
        user_key = st.session_state.current_user_key
        if "user_specific_data" in st.session_state and user_key in st.session_state.user_specific_data:
            st.session_state.user_specific_data[user_key][key] = value

def clear_user_cache():
    """Clear cache for current user only"""
    if "current_user_key" in st.session_state:
        # Clear specific user's cached data
        st.cache_data.clear()

def sign_up(email: str, password: str):
    try:
        user = supabase.auth.sign_up({"email": email, "password": password})
        return user
    except Exception as e:
        st.error(f"Registration failed: {e}")


def sign_in(email: str, password: str):
    try:
        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return user
    except Exception as e:
        st.error(f"Login failed: {e}")


def sign_out():
    try:
        supabase.auth.sign_out()
        
        # Clean up user-specific session data
        if "current_user_key" in st.session_state:
            user_key = st.session_state.current_user_key
            if "user_specific_data" in st.session_state and user_key in st.session_state.user_specific_data:
                del st.session_state.user_specific_data[user_key]
            del st.session_state.current_user_key
        
        # Reset main user email
        st.session_state.user_email = None
        
        # Clear all caches to ensure fresh start for next user
        st.cache_data.clear()
        st.cache_resource.clear()
        
        st.rerun()
    except Exception as e:
        st.error(f"Logout failed: {e}")


def main_app(user_email: str):
    # Initialize user-specific session state
    if "user_specific_data" not in st.session_state:
        st.session_state.user_specific_data = {}
    
    # Create unique user session key
    user_session_key = f"user_{hash(user_email)}"
    
    # Initialize user-specific session data if it doesn't exist
    if user_session_key not in st.session_state.user_specific_data:
        st.session_state.user_specific_data[user_session_key] = {
            "selected_semester": None,
            "selected_committee": "All Committees",
            "last_page": "Homepage",
            "dashboard_filters": {},
            "treasury_authenticated": False
        }
    
    # Store current user session key for easy access
    st.session_state.current_user_key = user_session_key
    
    # Page registration and navigation only after authentication
    PAGE_DEFS = [
        {"page": "views/Homepage.py",                "title": "Homepage",                                    "icon": ":material/home:",         "default": True},
        {"page": "views/Financial_Dashboard.py",     "title": "Financial Dashboard",                          "icon": ":material/analytics:"},
        {"page": "views/Transaction_Editor.py",      "title": "Transaction Editor",                           "icon": ":material/edit:"},
        # {"page": "views/AI_Assistant.py",            "title": "AI Assistant",                                 "icon": ":material/smart_toy:"},  # Disabled - under development
        {"page": "views/Treasury_Management.py",     "title": "Treasury Management",                           "icon": ":material/account_balance:"},
    ]

    pages = register_nav_pages(PAGE_DEFS)
    pg = st.navigation(pages=pages)

    # Sidebar content - place this BEFORE the logo to ensure proper positioning
    st.sidebar.text("Made by the Treasury Committee")
    
    # Sign out button in sidebar
    st.sidebar.divider()
    if st.sidebar.button("🚪 Sign Out"):
        sign_out()

    # Shared header/logo - place this AFTER sidebar content
    st.logo("assets/AIS_logo.png", size="large")

    # Run the selected page
    pg.run()


def auth_screen():
    st.title("Authentication Page")
    option = st.selectbox("Choose an action:", ["Login", "Sign Up"], key="auth_option")

    email    = st.text_input("Email", key="auth_email")
    password = st.text_input("Password", type="password", key="auth_pwd")

    if option == "Sign Up":
        confirm = st.text_input("Confirm Password", type="password", key="auth_confirm")

        if st.button("Register"):
            # 1. validate locally
            if not email or not password or not confirm:
                st.error("All fields are required.")
                return
            if password != confirm:
                st.error("Passwords do not match.")
                return
            if len(password) < 6:
                st.error("Password must be at least 6 characters.")
                return

            # 2. call your existing sign_up()
            user = sign_up(email, password)
            if hasattr(user, "error") and user.error:
                st.error(f"Registration failed: {user.error.message}")
            elif hasattr(user, "user") and user.user:
                st.success("Registration successful! Please check your email to confirm.")
                # force a rerun so they can switch to Login
                st.rerun()

    else:  # Login flow
        if st.button("Login"):
            if not email or not password:
                st.error("Enter both email and password.")
                return

            user = sign_in(email, password)
            if hasattr(user, "error") and user.error:
                st.error(f"Login failed: {user.error.message}")
            elif hasattr(user, "user") and user.user:
                st.session_state.user_email = user.user.email
                st.success("Logged in successfully.")
                st.rerun()

# Initialize session state for user_email
if "user_email" not in st.session_state:
    st.session_state.user_email = None

# Branch to auth or main app
if st.session_state.user_email:
    main_app(st.session_state.user_email)
else:
    auth_screen()
