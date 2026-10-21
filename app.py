import streamlit as st
import requests

st.set_page_config(page_title="Cas Boys AI Coach", page_icon="🏀", layout="centered")

# --- CUSTOM BLUE-TO-BLACK GRADIENT CSS ---
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(to bottom, #1e3a8a 0%, #0a0e1a 45%, #000000 100%);
        background-attachment: fixed;
    }
    h1, h2, h3, p, label, .stMarkdown {
        color: #f8fafc !important;
    }
    </style>
    """, unsafe_allow_html=True)

LEAGUE_ID = "1346846297000267776"

@st.cache_data(ttl=3600)
def fetch_league_users():
    url = f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/users"
    res = requests.get(url)
    if res.status_code == 200:
        users = res.json()
        return {u.get("display_name", f"User_{u['user_id']}"): u["user_id"] for u in users}
    return {}

# Initialize session state
if "active_user_id" not in st.session_state:
    st.session_state.active_user_id = None
if "active_user_name" not in st.session_state:
    st.session_state.active_user_name = None

league_users = fetch_league_users()

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("<h1 style='text-align: center;'>🏀 Cas Boys Fantasy AI Coach</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #cbd5e1; font-size: 18px;'>Your hub for live Sleeper analytics and AI strategy</p>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if league_users:
        selected_name = st.selectbox("Choose Your Manager Profile:", list(league_users.keys()))
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 Enter Locker Room", use_container_width=True):
            st.session_state.active_user_name = selected_name
            st.session_state.active_user_id = league_users[selected_name]
            st.rerun()
    else:
        st.error("Could not load league users from Sleeper API.")

if st.session_state.active_user_id:
    st.markdown("---")
    st.success(f"Logged in as **{st.session_state.active_user_name}**. Use the sidebar on the left to navigate to the **AI Coach** or **Team Info** pages!")
