import streamlit as st
import requests
from google import genai

# --- Page Configuration ---
st.set_page_config(
    page_title="Fantasy Basketball AI Assistant",
    page_icon="🏀",
    layout="wide"
)

# Initialize Gemini Client (ensure GEMINI_API_KEY is in st.secrets)
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# ==========================================
# 1. CACHED SLEEPER API FUNCTIONS
# ==========================================
@st.cache_data(ttl=600)
def fetch_sleeper_league_data(league_id):
    """Fetches league details, rosters, and users from Sleeper."""
    base_url = f"https://api.sleeper.app/v1/league/{league_id}"
    
    league_resp = requests.get(base_url).json()
    rosters_resp = requests.get(f"{base_url}/rosters").json()
    users_resp = requests.get(f"{base_url}/users").json()
    
    # Check if league actually exists / returned valid lists
    if not isinstance(users_resp, list) or len(users_resp) == 0:
        return None

    return {
        "league": league_resp,
        "rosters": rosters_resp,
        "users": users_resp
    }

def get_user_map(users):
    user_map = {}
    for user in users:
        user_id = user.get("user_id")
        display_name = user.get("display_name") or user.get("user_name") or "Unknown Manager"
        user_map[user_id] = display_name
    return user_map

# ==========================================
# 2. SIDEBAR CONFIGURATION & STATE
# ==========================================
st.sidebar.title("⚙️ League Settings")

league_id_input = st.sidebar.text_input(
    "Sleeper League ID", 
    value=st.session_state.get("league_id", "")
)

if league_id_input:
    st.session_state["league_id"] = league_id_input
    with st.spinner("Loading league context..."):
        league_data = fetch_sleeper_league_data(league_id_input)
        
        if league_data and league_data.get("users"):
            st.sidebar.success("League loaded!")
            st.session_state["league_data"] = league_data
            
            users = league_data.get("users", [])
            rosters = league_data.get("rosters", [])
            user_map = get_user_map(users)
            
            manager_names = [user_map.get(u.get("user_id"), "Unknown") for u in users]
            
            selected_manager_name = st.sidebar.selectbox(
                "Select Your Team / Manager",
                options=manager_names,
                key="selected_manager_name"
            )
            
            # Save selected roster to session_state
            for u in users:
                if user_map.get(u.get("user_id")) == selected_manager_name:
                    target_user_id = u.get("user_id")
                    st.session_state["selected_roster"] = next(
                        (r for r in rosters if r.get("owner_id") == target_user_id), None
                    )
                    break
        else:
            st.sidebar.error("No managers found for this League ID. Please double check the ID.")
            st.session_state["league_data"] = None

# --- AI COACH SELECTION ---
st.sidebar.markdown("---")
st.sidebar.title("🧠 Select AI Coach")
coach_persona = st.sidebar.radio(
    "Choose your assistant style:",
    options=["📊 Analyst Coach", "🔥 Hype & Strategy Coach"],
    key="coach_persona"
)

if coach_persona == "📊 Analyst Coach":
    coach_instruction = (
        "You are an analytical Fantasy Basketball AI Coach. Your responses are clear, "
        "data-driven, objective, and direct. Focus on stats, efficiency, roster strengths, and match projections."
    )
else:
    coach_instruction = (
        "You are an energetic, motivational, highly competitive Fantasy Basketball Coach. "
        "Give strategic advice, bold predictions, trash-talk warnings, and hype up roster moves!"
    )

# ==========================================
# 3. MAIN DISPLAY & CHAT INTERFACE
# ==========================================
st.title("🏀 Fantasy Basketball AI Hub")

curr_manager = st.session_state.get("selected_manager_name", "No Manager Selected")
st.subheader(f"Managing: **{curr_manager}** | Active Mode: **{coach_persona}**")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display existing messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat Input
if prompt := st.chat_input("Ask about your roster, matchups, trades, or waiver wire..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        system_context = coach_instruction
        
        league_data = st.session_state.get("league_data")
        selected_roster = st.session_state.get("selected_roster")
        
        if league_data:
            system_context += f"\nLeague Name: {league_data['league'].get('name', 'Fantasy League')}."
        if curr_manager != "No Manager Selected":
            system_context += f"\nCurrent User Manager: {curr_manager}."
        if selected_roster:
            system_context += f"\nUser Roster Player IDs: {selected_roster.get('players', [])}."

        # Keep history payload concise
        MAX_HISTORY = 6
        recent_history = st.session_state.messages[-MAX_HISTORY:]
        formatted_contents = [{"role": m["role"], "parts": [m["content"]]} for m in recent_history]

        try:
            response_stream = client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=formatted_contents,
                config={"system_instruction": system_context}
            )

            ai_response = st.write_stream(chunk.text for chunk in response_stream)
            st.session_state.messages.append({"role": "model", "content": ai_response})

        except Exception as e:
            st.error(f"Error generating response: {e}")
