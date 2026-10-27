import streamlit as st
import requests
from google import genai

# --- Page Configuration ---
st.set_page_config(
    page_title="Fantasy Basketball AI Assistant",
    page_icon="🏀",
    layout="wide"
)

# Initialize Gemini Client (ensure GEMINI_API_KEY is set in st.secrets)
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
    
    return {
        "league": league_resp,
        "rosters": rosters_resp,
        "users": users_resp
    }

# Helper to map user IDs to display names
def get_user_map(users):
    user_map = {}
    for user in users:
        user_id = user.get("user_id")
        display_name = user.get("display_name") or user.get("user_name") or "Unknown Manager"
        user_map[user_id] = display_name
    return user_map

# ==========================================
# 2. SIDEBAR CONFIGURATION
# ==========================================
st.sidebar.title("⚙️ League Settings")
league_id_input = st.sidebar.text_input(
    "Sleeper League ID", 
    value="123456789012345678"  # Replace with your league ID
)

selected_manager = None
selected_roster = None
league_data = None

if league_id_input:
    with st.spinner("Loading league context..."):
        try:
            league_data = fetch_sleeper_league_data(league_id_input)
            st.sidebar.success("League loaded!")
            
            # --- MANAGER SELECTION DROPDOWN ---
            users = league_data.get("users", [])
            rosters = league_data.get("rosters", [])
            user_map = get_user_map(users)
            
            # Create dropdown choices matching user display names
            manager_names = [user_map.get(u.get("user_id"), "Unknown") for u in users]
            selected_manager_name = st.sidebar.selectbox(
                "Select Your Team / Manager",
                options=manager_names if manager_names else ["No Managers Found"]
            )
            
            # Find matching roster for selected user
            for u in users:
                d_name = user_map.get(u.get("user_id"))
                if d_name == selected_manager_name:
                    target_user_id = u.get("user_id")
                    selected_roster = next((r for r in rosters if r.get("owner_id") == target_user_id), None)
                    break

        except Exception as e:
            st.sidebar.error("Could not load league data. Check League ID.")

# --- AI COACH SELECTION ---
st.sidebar.markdown("---")
st.sidebar.title("🧠 Select AI Coach")
coach_persona = st.sidebar.radio(
    "Choose your assistant style:",
    options=["📊 Analyst Coach", "🔥 Hype & Strategy Coach"]
)

# Define system prompts based on chosen coach
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
# 3. CHAT INTERFACE & STATE MANAGEMENT
# ==========================================
st.title("🏀 Fantasy Basketball AI Hub")

if selected_manager_name:
    st.subheader(f"Managing: **{selected_manager_name}** | Active Mode: **{coach_persona}**")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Chat Input
if prompt := st.chat_input("Ask about your roster, matchups, trades, or waiver wire..."):
    # Store user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build AI context with selected manager details
    with st.chat_message("assistant"):
        system_context = coach_instruction
        if league_data:
            system_context += f"\nLeague Name: {league_data['league'].get('name', 'Fantasy League')}."
        if selected_manager_name:
            system_context += f"\nCurrent User Manager: {selected_manager_name}."
        if selected_roster:
            players_list = selected_roster.get("players", [])
            system_context += f"\nUser Roster Player IDs: {players_list}."

        # Keep history light for maximum speed
        MAX_HISTORY = 6
        recent_history = st.session_state.messages[-MAX_HISTORY:]
        formatted_contents = [{"role": m["role"], "parts": [m["content"]]} for m in recent_history]

        try:
            # Real-time Streaming
            response_stream = client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=formatted_contents,
                config={"system_instruction": system_context}
            )

            # Stream straight to Streamlit UI
            ai_response = st.write_stream(chunk.text for chunk in response_stream)
            
            # Save assistant message
            st.session_state.messages.append({"role": "model", "content": ai_response})

        except Exception as e:
            st.error(f"Error generating response: {e}")
