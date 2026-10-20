import streamlit as st
import requests
import google.generativeai as genai

# Page Configuration
st.set_page_config(page_title="League AI Coach", page_icon="🏀")
st.title("🏀 Fantasy Basketball AI Coach")

# Your League ID
LEAGUE_ID = "1346846297000267776"

# Backup list of model names
FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-1.5-flash",
    "gemini-flash"
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
    """Fetch team, opponent team, and top available free agents"""
    all_players = load_all_players()
    current_week = get_league_state()
    
    # 1. Fetch Rosters
    rosters_res = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters")
    if rosters_res.status_code != 200:
        return {"starters": [], "bench": []}, {"starters": [], "bench": []}, [], current_week
        
    rosters = rosters_res.json()
    my_roster = next((r for r in rosters if str(r.get('owner_id')) == str(selected_user_id)), None)
    my_roster_id = my_roster['roster_id'] if my_roster else None
    
    taken_player_ids = set()
    for r in rosters:
        taken_player_ids.update(r.get("players", []) or [])
        
    user_team = {"starters": [], "bench": []}
    if my_roster:
        starters = my_roster.get("starters", []) or []
        players = my_roster.get("players", []) or []
        bench = [p for p in players if p not in starters]
        
        user_team["starters"] = [all_players.get(pid, {}).get("full_name", pid) for pid in starters]
        user_team["bench"] = [all_players.get(pid, {}).get("full_name", pid) for pid in bench]

    # 2. Fetch Opponent Data
    opponent_team = {"starters": [], "bench": []}
    matchups_res = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/matchups/{current_week}")
    
    if matchups_res.status_code == 200 and my_roster_id:
        matchups = matchups_res.json()
        my_matchup = next((m for m in matchups if m.get('roster_id') == my_roster_id), None)
        
        if my_matchup:
            matchup_id = my_matchup.get("matchup_id")
            opp_matchup = next((m for m in matchups if m.get("matchup_id") == matchup_id and m.get('roster_id') != my_roster_id), None)
            
            if opp_matchup:
                opp_starters = opp_matchup.get("starters", []) or []
                opp_players = opp_matchup.get("players", []) or []
                opp_bench = [p for p in opp_players if p not in opp_starters]
                
                opponent_team["starters"] = [all_players.get(pid, {}).get("full_name", pid) for pid in opp_starters]
                opponent_team["bench"] = [all_players.get(pid, {}).get("full_name", pid) for pid in opp_bench]

    # 3. Fetch Top Free Agents
    top_free_agents = []
    trending_res = requests.get("https://api.sleeper.app/v1/players/nba/trending/add")
    
    if trending_res.status_code == 200:
        trending = trending_res.json()
        for item in trending:
            pid = item.get("player_id")
            if pid not in taken_player_ids and pid in all_players:
                p_name = all_players[pid].get("full_name")
                p_pos = all_players[pid].get("position", "")
                p_team = all_players[pid].get("team", "")
                if p_name:
                    top_free_agents.append(f"{p_name} ({p_pos} - {p_team})")
                if len(top_free_agents) >= 15:
                    break
                    
    return user_team, opponent_team, top_free_agents, current_week

# --- USER SELECTION HEADER ---
league_users = fetch_league_users()

if league_users:
    st.sidebar.title("⚙️ Manager Switcher")
    selected_name = st.sidebar.selectbox("Select Profile:", list(league_users.keys()))
    active_user_id = league_users[selected_name]
else:
    active_user_id = "1412647306305527808"
    selected_name = "Default User"

st.info(f"👤 Currently Viewing AI Coach for: **{selected_name}**")

# Reset chat messages when switching to a different user profile
if "current_profile" not in st.session_state or st.session_state.current_profile != selected_name:
    st.session_state.current_profile = selected_name
    st.session_state.messages = [
        {"role": "assistant", "content": f"Hey {selected_name}! I'm synced with your team's live roster and opponent data. What fantasy advice do you need?"}
    ]

# Fetch Live Data for the Selected User
user_team, opponent_team, top_fa, current_week = fetch_user_league_data(active_user_id)

# Display Dashboard
st.write(f"### 📅 Week {current_week} Overview")

col1, col2 = st.columns(2)
with col1:
    with st.expander(f"🏀 {selected_name}'s Roster", expanded=False):
        st.write(f"**Starters:** {', '.join(user_team['starters']) if user_team['starters'] else 'None'}")
        st.write(f"**Bench:** {', '.join(user_team['bench']) if user_team['bench'] else 'None'}")

with col2:
    with st.expander("⚔️ Opponent Roster", expanded=False):
        st.write(f"**Starters:** {', '.join(opponent_team['starters']) if opponent_team['starters'] else 'None'}")
        st.write(f"**Bench:** {', '.join(opponent_team['bench']) if opponent_team['bench'] else 'None'}")

with st.expander("🔥 Top Trending Free Agents Available", expanded=False):
    st.write(", ".join(top_fa) if top_fa else "No trending free agents found.")

# Render chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Sticky Chat Input
if user_prompt := st.chat_input("Ask about your starters, matchups, or waiver pickups..."):
    with st.chat_message("user"):
        st.write(user_prompt)
    
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    if not api_key:
        st.error("API Key missing! Please add GEMINI_API_KEY to your Streamlit secrets.")
    else:
        with st.chat_message("assistant"):
            with st.spinner("Analyzing team context..."):
                u_team, opp_team, free_agents, week = fetch_user_league_data(active_user_id)
                genai.configure(api_key=api_key)
                
                system_context = f"""
                You are a Fantasy Basketball expert assistant serving user '{selected_name}'.
                
                Current League Week: {week}
                Scoring Settings: PTS = 0.5, REB = 1, AST = 1, STL = 2, BLK = 2, 3PM = 1, TO = -1, DD = 1, TD = 2.
                
                --- {selected_name.upper()}'S TEAM ---
                Starters: {', '.join(u_team['starters'])}
                Bench: {', '.join(u_team['bench'])}
                
                --- OPPONENT'S TEAM ---
                Starters: {', '.join(opp_team['starters'])}
                Bench: {', '.join(opp_team['bench'])}
                
                --- TOP TRENDING AVAILABLE FREE AGENTS ---
                {', '.join(free_agents)}
                
                Provide tailored strategy for {selected_name}'s specific team.
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
