import streamlit as st
import requests
import google.generativeai as genai

st.set_page_config(page_title="AI Coach", page_icon="🏀", layout="centered")

# --- CUSTOM BLUE-TO-BLACK GRADIENT & TRANSPARENT CHAT CSS ---
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(to bottom, #1e3a8a 0%, #0a0e1a 45%, #000000 100%);
        background-attachment: fixed;
    }
    h1, h2, h3, p, label, .stMarkdown {
        color: #f8fafc !important;
    }
    
    /* --- MAKE CHAT INPUT FULLY TRANSPARENT --- */
    [data-testid="stChatInput"] {
        background-color: transparent !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 12px;
    }
    [data-testid="stChatInput"] textarea {
        color: #f8fafc !important;
        background-color: transparent !important;
    }
    </style>
    """, unsafe_allow_html=True)

LEAGUE_ID = "1346846297000267776"
FALLBACK_MODELS = [
    "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", 
    "gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-2.5-flash", 
    "gemini-2.5-pro", "gemini-2.0-flash", "gemini-2.0-flash-lite", 
    "gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-flash-latest", 
    "gemini-1.5-flash-8b", "gemini-1.5-pro", "gemini-1.5-pro-latest"
]

api_key = st.secrets.get("GEMINI_API_KEY", None)

if not st.session_state.get("active_user_id"):
    st.warning("⚠️ Please select your manager profile on the main page first!")
    st.stop()

selected_name = st.session_state.active_user_name
active_user_id = st.session_state.active_user_id

st.title("🏀 AI Fantasy Coach")
st.info(f"👤 Active Manager: **{selected_name}**")

@st.cache_data(ttl=86400)
def load_all_players():
    res = requests.get("https://api.sleeper.app/v1/players/nba")
    return res.json() if res.status_code == 200 else {}

@st.cache_data(ttl=3600)
def get_league_state():
    try:
        return requests.get("https://api.sleeper.app/v1/state/nba").json().get("week", 1)
    except:
        return 1

def fetch_context_data():
    all_players = load_all_players()
    current_week = get_league_state()
    rosters_res = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters")
    if rosters_res.status_code != 200:
        return [], [], [], current_week, 0, 0, 0, 0
    rosters = rosters_res.json()
    my_roster = next((r for r in rosters if str(r.get('owner_id')) == str(active_user_id)), None)
    my_roster_id = my_roster['roster_id'] if my_roster else None
    
    taken = set()
    for r in rosters:
        taken.update(r.get("players", []) or [])
        
    matchups_res = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/matchups/{current_week}")
    matchups = matchups_res.json() if matchups_res.status_code == 200 else []
    my_matchup = next((m for m in matchups if m.get('roster_id') == my_roster_id), None) if my_roster_id else None
    
    my_pts = float(my_matchup.get("pts", 0.0)) if my_matchup and my_matchup.get("pts") else 0.0
    my_proj = float(my_matchup.get("custom_points", 0.0)) if my_matchup and my_matchup.get("custom_points") else 0.0
    
    user_starters = []
    if my_roster:
        pts_map = my_matchup.get("players_points", {}) if my_matchup else {}
        for pid in (my_roster.get("starters", []) or []):
            name = all_players.get(pid, {}).get("full_name", pid)
            score = float(pts_map.get(pid, 0.0) or 0.0)
            user_starters.append(f"{name} ({score:.1f} pts)")
            
    opp_starters = []
    opp_pts, opp_proj = 0.0, 0.0
    if my_matchup:
        opp_matchup = next((m for m in matchups if m.get("matchup_id") == my_matchup.get("matchup_id") and m.get('roster_id') != my_roster_id), None)
        if opp_matchup:
            opp_pts = float(opp_matchup.get("pts", 0.0) or 0.0)
            opp_players_pts = opp_matchup.get("players_points", {}) or {}
            opp_proj = sum(float(v) for v in opp_players_pts.values() if v is not None)
            for pid in (opp_matchup.get("starters", []) or []):
                name = all_players.get(pid, {}).get("full_name", pid)
                score = float(opp_players_pts.get(pid, 0.0) or 0.0)
                opp_starters.append(f"{name} ({score:.1f} pts)")

    top_fa = []
    trending = requests.get("https://api.sleeper.app/v1/players/nba/trending/add")
    if trending.status_code == 200:
        for item in trending.json():
            pid = item.get("player_id")
            if pid not in taken and pid in all_players:
                p = all_players[pid]
                top_fa.append(f"{p.get('full_name')} ({p.get('position')} - {p.get('team')})")
                if len(top_fa) >= 10: break

    return user_starters, opp_starters, top_fa, current_week, my_pts, my_proj, opp_pts, opp_proj

for message in st.session_state.get("messages", []):
    with st.chat_message(message["role"]):
        st.write(message["content"])

if user_prompt := st.chat_input("Ask about lock-ins, trades, or pickups..."):
    with st.chat_message("user"):
        st.write(user_prompt)
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    if not api_key:
        st.error("API Key missing in secrets!")
    else:
        with st.chat_message("assistant"):
            with st.spinner("Analyzing matchup & lineup context..."):
                u_starters, o_starters, fa, wk, m_p, m_pr, o_p, o_pr = fetch_context_data()
                genai.configure(api_key=api_key)
                
                system_context = f"""
                You are a Fantasy Basketball expert assistant serving user '{selected_name}'.
                Week: {wk}
                Scoring: PTS=0.5, REB=1, AST=1, STL=2, BLK=2, 3PM=1, TO=-1, DD=1, TD=2.
                Matchup: {selected_name} ({m_p:.1f} pts, Proj: {m_pr:.1f}) vs Opponent ({o_p:.1f} pts, Proj: {o_pr:.1f}).
                Starters: {', '.join(u_starters)}
                Opponent Starters: {', '.join(o_starters)}
                Free Agents: {', '.join(fa)}
                Give strategic advice on whether to lock in lineups or make adjustments.
                """
                
                conversation = system_context + "\n\nHistory:\n"
                for msg in st.session_state.messages:
                    conversation += f"{msg['role'].capitalize()}: {msg['content']}\n"

                response_text = None
                for model_name in FALLBACK_MODELS:
                    try:
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(conversation)
                        response_text = response.text
                        break
                    except:
                        continue

                if response_text:
                    st.write(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                else:
                    st.error("Error generating advice from models.")
