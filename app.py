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
