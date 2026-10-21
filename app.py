import streamlit as st
import requests
import google.generativeai as genai

# Page Configuration
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

# Your League ID
LEAGUE_ID = "1346846297000267776"

# Model Fallback Array
FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
    "gemini-1.5-pro-latest"
]

# Retrieve API key from Streamlit secrets
api_key = st.secrets.get("GEMINI_API_KEY", None)

@st.cache_data(ttl=86400)
def load_all_players():
    """Fetch and cache all NBA players"""
    url = "https://api.sleeper.app/v1/players/nba"
    res = requests.get(url)
    return res.json() if res.status_code == 200 else {}

@st.cache_data(ttl=3600)
def fetch_league_users():
    """Fetch all managers in the league"""
    url = f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/users"
    res = requests.get(url)
    if res.status_code == 200:
        users = res.json()
        return {u.get("display_name", f"User_{u['user_id']}"): u["user_id"] for u in users}
    return {}

@st.cache_data(ttl=3600)
def get_league_state():
    """Fetch current NBA week"""
    try:
        res = requests.get("https://api.sleeper.app/v1/state/nba").json()
        return res.get("week", 1)
    except Exception:
        return 1

def fetch_user_league_data(selected_user_id):
    """Fetch live team, opponent team, points scored, projections, and free agents"""
    all_players = load_all_players()
    current_week = get_league_state()
    
    # 1. Fetch Rosters
    rosters_res = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters")
    if rosters_res.status_code != 200:
        return {}, {}, [], current_week, 0.0, 0.0, 0.0, 0.0
        
    rosters = rosters_res.json()
    my_roster = next((r for r in rosters if str(r.get('owner_id')) == str(selected_user_id)), None)
    my_roster_id = my_roster['roster_id'] if my_roster else None
    
    taken_player_ids = set()
    for r in rosters:
        taken_player_ids.update(r.get("players", []) or [])

    # 2. Fetch Matchups for Live Points and Projections
    matchups_res = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/matchups/{current_week}")
    matchups = matchups_res.json() if matchups_res.status_code == 200 else []
    
    my_matchup = next((m for m in matchups if m.get('roster_id') == my_roster_id), None) if my_roster_id else None
    
    # Safe float conversions with fallbacks
    try:
        my_total_pts = float(my_matchup.get("pts", 0.0)) if my_matchup and my_matchup.get("pts") is not None else 0.0
    except (TypeError, ValueError):
        my_total_pts = 0.0

    try:
        my_proj_pts = float(my_matchup.get("custom_points", 0.0)) if my_matchup and my_matchup.get("custom_points") is not None else 0.0
    except (TypeError, ValueError):
        my_proj_pts = 0.0

    if my_proj_pts == 0.0 and my_matchup and "players_points" in my_matchup:
        try:
            my_proj_pts = sum(float(v) for v in my_matchup.get("players_points", {}).values() if v is not None) * 0.95
        except (TypeError, ValueError):
            pass

    # Build User Roster Breakdown (Starters with individual points)
    user_team = {"starters": [], "bench": [], "details": []}
    if my_roster:
        starters = my_roster.get("starters", []) or []
        players_pts = my_matchup.get("players_points", {}) if my_matchup else {}
        
        for pid in starters:
            p_name = all_players.get(pid, {}).get("full_name", pid)
            try:
                p_score = float(players_pts.get(pid, 0.0)) if players_pts.get(pid) is not None else 0.0
            except (TypeError, ValueError):
                p_score = 0.0
            user_team["starters"].append(f"{p_name} ({p_score:.1f} pts)")
            user_team["details"].append({"name": p_name, "points": p_score})
            
        bench_ids = [p for p in (my_roster.get("players", []) or []) if p not in starters]
        user_team["bench"] = [all_players.get(pid, {}).get("full_name", pid) for pid in bench_ids]

    # Opponent Team Data
    opponent_team = {"starters": [], "bench": []}
    opp_total_pts, opp_proj_pts = 0.0, 0.0
    if my_matchup:
        matchup_id = my_matchup.get("matchup_id")
        opp_matchup = next((m for m in matchups if m.get("matchup_id") == matchup_id and m.get('roster_id') != my_roster_id), None)
        if opp_matchup:
            try:
                opp_total_pts = float(opp_matchup.get("pts", 0.0)) if opp_matchup.get("pts") is not None else 0.0
            except (TypeError, ValueError):
                opp_total_pts = 0.0
                
            opp_players_pts = opp_matchup.get("players_points", {}) or {}
            try:
                opp_proj_pts = sum(float(v) for v in opp_players_pts.values() if v is not None)
            except (TypeError, ValueError):
                opp_proj_pts = 0.0
                
            opp_starters = opp_matchup.get("starters", []) or []
            for pid in opp_starters:
                p_name = all_players.get(pid, {}).get("full_name", pid)
                try:
                    p_score = float(opp_players_pts.get(pid, 0.0)) if opp_players_pts.get(pid) is not None else 0.0
                except (TypeError, ValueError):
                    p_score = 0.0
                opponent_team["starters"].append(f"{p_name} ({p_score:.1f} pts)")
                
            opp_bench_ids = [p for p in (opp_matchup.get("players", []) or []) if p not in opp_starters]
            opponent_team["bench"] = [all_players.get(pid, {}).get("full_name", pid) for pid in opp_bench_ids]

    # 3. Fetch Top Free Agents
    top_free_agents = []
    trending_res = requests.get("https://api.sleeper.app/v1/players/nba/trending/add")
    if trending_res.status_code == 200:
        for item in trending_res.json():
            pid = item.get("player_id")
            if pid not in taken_player_ids and pid in all_players:
                p_name = all_players[pid].get("full_name")
                p_pos = all_players[pid].get("position", "")
                p_team = all_players[pid].get("team", "")
                if p_name:
                    top_free_agents.append(f"{p_name} ({p_pos} - {p_team})")
                if len(top_free_agents) >= 10:
                    break
                    
    return user_team, opponent_team, top_free_agents, current_week, my_total_pts, my_proj_pts, opp_total_pts, opp_proj_pts

# Initialize session state for user login
if "active_user_id" not in st.session_state:
    st.session_state.active_user_id = None
if "active_user_name" not in st.session_state:
    st.session_state.active_user_name = None

league_users = fetch_league_users()

# --- HOME SCREEN / LANDING VIEW ---
if not st.session_state.active_user_id:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>🏀 Cas Boys Fantasy AI Coach</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #cbd5e1; font-size: 18px;'>Select your manager profile below to open your live team dashboard</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if league_users:
            selected_name = st.selectbox("Choose Your Manager Profile:", list(league_users.keys()))
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 Enter Locker Room", use_container_width=True):
                st.session_state.active_user_name = selected_name
                st.session_state.active_user_id = league_users[selected_name]
                st.session_state.messages = [
                    {"role": "assistant", "content": f"Hey {selected_name}! I'm tracking your matchup points, individual player stats, and projections. Ask me if you should lock in your lineup!"}
                ]
                st.rerun()
        else:
            st.error("Could not load league users from Sleeper API.")
    st.stop()

# --- DASHBOARD & CHAT SCREEN ---
selected_name = st.session_state.active_user_name
active_user_id = st.session_state.active_user_id

st.title("🏀 Fantasy Basketball AI Coach")

# Top Bar with Profile Info & Switch Button
top_col1, top_col2 = st.columns([3, 1])
with top_col1:
    st.info(f"👤 Active Manager: **{selected_name}**")
with top_col2:
    if st.button("🔄 Switch Manager", use_container_width=True):
        st.session_state.active_user_id = None
        st.session_state.active_user_name = None
        st.rerun()

# Fetch Live Data
user_team, opponent_team, top_fa, current_week, my_pts, my_proj, opp_pts, opp_proj = fetch_user_league_data(active_user_id)

# --- SCOREBOARD METRICS ---
st.write(f"### 📅 Week {current_week} Matchup Scoreboard")
m_col1, m_col2 = st.columns(2)
m_col1.metric(label=f"🟢 {selected_name} (You)", value=f"{my_pts:.1f} PTS", delta=f"Proj: {my_proj:.1f}")
m_col2.metric(label="⚔️ Opponent", value=f"{opp_pts:.1f} PTS", delta=f"Proj: {opp_proj:.1f}")

st.markdown("---")

# Roster and Matchup Expanders
col1, col2 = st.columns(2)
with col1:
    with st.expander(f"🏀 {selected_name}'s Starters & Points", expanded=True):
        for s in user_team.get('starters', []):
            st.write(f"- {s}")
    with st.expander("Bench", expanded=False):
        st.write(f"{', '.join(user_team.get('bench', [])) if user_team.get('bench') else 'None'}")

with col2:
    with st.expander("⚔️ Opponent Starters", expanded=True):
        for os in opponent_team.get('starters', []):
            st.write(f"- {os}")
    with st.expander("Opponent Bench", expanded=False):
        st.write(f"{', '.join(opponent_team.get('bench', [])) if opponent_team.get('bench') else 'None'}")

with st.expander("🔥 Top Trending Free Agents Available", expanded=False):
    st.write(", ".join(top_fa) if top_fa else "No trending free agents found.")

st.markdown("---")

# Render chat messages
for message in st.session_state.get("messages", []):
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Sticky Chat Input
if user_prompt := st.chat_input("Ask if you should lock in your lineup or who to stream..."):
    with st.chat_message("user"):
        st.write(user_prompt)
    
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    if not api_key:
        st.error("API Key missing! Please add GEMINI_API_KEY to your Streamlit secrets.")
    else:
        with st.chat_message("assistant"):
            with st.spinner("Analyzing matchup performance & lock-in status..."):
                u_team, opp_team, free_agents, week, m_p, m_pr, o_p, o_pr = fetch_user_league_data(active_user_id)
                genai.configure(api_key=api_key)
                
                system_context = f"""
                You are a Fantasy Basketball expert assistant serving user '{selected_name}'.
                
                Current League Week: {week}
                Scoring Settings: PTS = 0.5, REB = 1, AST = 1, STL = 2, BLK = 2, 3PM = 1, TO = -1, DD = 1, TD = 2.
                
                --- MATCHUP STATUS ---
                {selected_name}'s Total Score: {m_p:.1f} (Projected: {m_pr:.1f})
                Opponent's Total Score: {o_p:.1f} (Projected: {o_pr:.1f})
                
                --- {selected_name.upper()}'S STARTERS & INDIVIDUAL POINTS ---
                {', '.join(u_team.get('starters', []))}
                
                --- OPPONENT'S STARTERS ---
                {', '.join(opp_team.get('starters', []))}
                
                --- TOP TRENDING AVAILABLE FREE AGENTS ---
                {', '.join(free_agents)}
                
                Evaluate whether it's a good idea to lock in current lineups, who scored well, and give strategic advice based on current live scores and projections.
                """
                
                conversation = system_context + "\n\nConversation History:\n"
                for msg in st.session_state.messages:
                    conversation += f"{msg['role'].capitalize()}: {msg['content']}\n"

                response_text = None
                last_error = None

                for model_name in FALLBACK_MODELS:
                    try:
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(conversation)
                        response_text = response.text
                        break
                    except Exception as e:
                        last_error = e
                        continue

                if response_text:
                    st.write(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                else:
                    st.error(f"Error generating advice: {last_error}")
