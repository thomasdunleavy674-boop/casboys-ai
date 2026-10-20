import streamlit as st
import requests
import google.generativeai as genai

# Page Configuration
st.set_page_config(page_title="Cas Boys BBall AI Coach", page_icon="🏀")
st.title("🏀 Live Fantasy Basketball AI Assistant")

# Sleeper Info
LEAGUE_ID = "1346846297000267776"
USER_ID = "1412647306305527808"

# Retrieve API key automatically from Streamlit secrets
api_key = st.secrets.get("GEMINI_API_KEY", None)

@st.cache_data(ttl=86400)
def load_all_players():
    """Fetch and cache all NBA players (cached once daily)"""
    url = "https://api.sleeper.app/v1/players/nba"
    res = requests.get(url)
    return res.json() if res.status_code == 200 else {}

@st.cache_data(ttl=3600)
def get_league_state():
    """Fetch current NBA week from Sleeper API"""
    res = requests.get("https://api.sleeper.app/v1/state/nba").json()
    return res.get("week", 1)

def fetch_league_data():
    """Fetch user team, opponent team, and top available free agents"""
    all_players = load_all_players()
    current_week = get_league_state()
    
    # 1. Fetch Rosters
    rosters_res = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters")
    if rosters_res.status_code != 200:
        return {}, {}, [], current_week
        
    rosters = rosters_res.json()
    
    # Find user roster
    my_roster = next((r for r in rosters if r['owner_id'] == USER_ID), None)
    my_roster_id = my_roster['roster_id'] if my_roster else None
    
    # Track all taken player IDs across the entire league
    taken_player_ids = set()
    for r in rosters:
        taken_player_ids.update(r.get("players", []) or [])
        
    # Build User Roster Dict
    user_team = {"starters": [], "bench": []}
    if my_roster:
        starters = my_roster.get("starters", []) or []
        players = my_roster.get("players", []) or []
        bench = [p for p in players if p not in starters]
        
        user_team["starters"] = [all_players.get(pid, {}).get("full_name", pid) for pid in starters]
        user_team["bench"] = [all_players.get(pid, {}).get("full_name", pid) for pid in bench]

    # 2. Fetch Opponent Data for Current Week
    opponent_team = {"starters": [], "bench": []}
    matchups_res = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/matchups/{current_week}")
    
    if matchups_res.status_code == 200 and my_roster_id:
        matchups = matchups_res.json()
        my_matchup = next((m for m in matchups if m['roster_id'] == my_roster_id), None)
        
        if my_matchup:
            matchup_id = my_matchup.get("matchup_id")
            opp_matchup = next((m for m in matchups if m.get("matchup_id") == matchup_id and m['roster_id'] != my_roster_id), None)
            
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
                p_pos = all_players[pid].get("position")
                p_team = all_players[pid].get("team")
                if p_name:
                    top_free_agents.append(f"{p_name} ({p_pos} - {p_team})")
                if len(top_free_agents) >= 15:
                    break
                    
    return user_team, opponent_team, top_free_agents, current_week

# Fetch Live Context Data
user_team, opponent_team, top_fa, current_week = fetch_league_data()

# Display Live Dashboard info in expanding dropdowns
st.write(f"### 📅 Week {current_week} Overview")

col1, col2 = st.columns(2)
with col1:
    with st.expander("🏀 My Roster", expanded=False):
        st.write(f"**Starters:** {', '.join(user_team['starters'])}")
        st.write(f"**Bench:** {', '.join(user_team['bench'])}")

with col2:
    with st.expander("⚔️ Opponent Roster", expanded=False):
        st.write(f"**Starters:** {', '.join(opponent_team['starters'])}")
        st.write(f"**Bench:** {', '.join(opponent_team['bench'])}")

with st.expander("🔥 Top Trending Free Agents Available", expanded=False):
    st.write(", ".join(top_fa) if top_fa else "No trending free agents found.")

# Initialize message history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hey! I'm connected to your live Sleeper roster and powered by Google Search. Ask me about live NBA news, player injuries, or game schedules!"}
    ]

# Render chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Sticky Chat Input
if user_prompt := st.chat_input("Ask about injuries, real-time news, or strategy..."):
    with st.chat_message("user"):
        st.write(user_prompt)
    
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    if not api_key:
        st.error("API Key missing! Please check Streamlit app secrets.")
    else:
        with st.chat_message("assistant"):
            with st.spinner("Searching the web & analyzing league context..."):
                try:
                    u_team, opp_team, free_agents, week = fetch_league_data()
                    
                    genai.configure(api_key=api_key)
                    
                    # ENABLED GOOGLE SEARCH GROUNDING
                    model = genai.GenerativeModel(
                        "gemini-3.8-flash",
                        tools='google_search_retrieval'
                    )
                    
                    system_context = f"""
                    You are a Fantasy Basketball expert assistant with real-time access to the user's Sleeper league data AND live Google Search.
                    
                    Current League Week: {week}
                    Scoring Settings: PTS = 0.5, REB = 1, AST = 1, STL = 2, BLK = 2, 3PM = 1, TO = -1, DD = 1, TD = 2.
                    
                    --- USER'S TEAM ---
                    Starters: {', '.join(u_team['starters'])}
                    Bench: {', '.join(u_team['bench'])}
                    
                    --- OPPONENT'S TEAM ---
                    Starters: {', '.join(opp_team['starters'])}
                    Bench: {', '.join(opp_team['bench'])}
                    
                    --- TOP TRENDING AVAILABLE FREE AGENTS ---
                    {', '.join(free_agents)}
                    
                    You have access to live web search to check up-to-the-minute NBA injury reports, starting lineup announcements, and schedule updates.
                    """
                    
                    conversation = system_context + "\n\nConversation History:\n"
                    for msg in st.session_state.messages:
                        conversation += f"{msg['role'].capitalize()}: {msg['content']}\n"
                    
                    response = model.generate_content(conversation)
                    bot_reply = response.text
                    
                    st.write(bot_reply)
                    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
                    
                except Exception as e:
                    st.error(f"Error generating advice: {e}")
