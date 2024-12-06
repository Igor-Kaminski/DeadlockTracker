from datetime import datetime, timedelta
import time
import requests
from flask import (
    render_template,
    flash,
    redirect,
    url_for,
    request,
    jsonify
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user
)
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
from app import app, db
from app.models import User, SteamAccount, Hero, FavouriteHero
from app.forms import RegistrationForm, LoginForm

# API Keys and Important Links
API_KEY = "HEXE-22afdffb-be7a-4290-9a47-3281a1cb18ae"
STEAM_API_KEY = "461C23366FEB84116663C61D7A8A2D8B"
STEAM_OPENID_URL = "https://steamcommunity.com/openid"


@app.route("/")
@login_required
def index():
    # Fetch patch notes
    patch_notes_url = "https://data.deadlock-api.com/v1/patch-notes"
    patch_notes_response = requests.get(patch_notes_url)
    patch_notes_data = patch_notes_response.json() if patch_notes_response.status_code == 200 else []

    # Fetch all heroes
    heroes = Hero.query.all()

    # Fetch the users favourite heroes
    favourite_hero_ids = {
        favourite.hero_id for favourite in current_user.favourite_heroes
    }

    return render_template(
        "index.html",
        updates=patch_notes_data,
        heroes=heroes,
        favourite_hero_ids=favourite_hero_ids,
    )


@app.route("/favourite_hero/<int:hero_id>", methods=["POST", "DELETE"])
@login_required
def favourite_hero(hero_id):
    if request.method == "POST":
        current_favourites = FavouriteHero.query.filter_by(user_id=current_user.id).all()
        if any(fav.hero_id == hero_id for fav in current_favourites):
            return jsonify({"status": "error", "message": "This hero is already a favourite."}), 400

        # Ensure the user has no more 3 favourite heroes selected
        if len(current_favourites) >= 3:
            return jsonify({"status": "error", "message": "You can only have up to 3 favourite heroes."}), 400

        # Add hero to favourites
        favourite = FavouriteHero(user_id=current_user.id, hero_id=hero_id)
        db.session.add(favourite)
        db.session.commit()
        return jsonify({"status": "added"}), 201

    elif request.method == "DELETE":
        # Remove hero from favourites
        favourite = FavouriteHero.query.filter_by(user_id=current_user.id, hero_id=hero_id).first()
        if favourite:
            db.session.delete(favourite)
            db.session.commit()
        return jsonify({"status": "removed"}), 200


@app.route("/leaderboard")
def leaderboard_home():
    regions = ["Europe", "Asia", "NAmerica", "SAmerica", "Oceania"]
    return render_template("leaderboard_home.html", regions=regions)


@app.route("/leaderboard/<region>")
def leaderboard(region):
    leaderboard_url = f"https://data.deadlock-api.com/v1/leaderboard/{region}"
    headers = {"X-API-Key": API_KEY}

    leaderboard_response = requests.get(leaderboard_url, headers=headers)

    leaderboard_data = leaderboard_response.json().get("entries", []) if leaderboard_response.status_code == 200 else []

    return render_template("leaderboard.html", leaderboard=leaderboard_data, region=region)


@app.route("/heroes")
def heroes():
    region, time_filter, win_rate_min, tier_filter = extract_query_parameters()
    api_region, current_time, min_unix_timestamp, time_filter = configure_region_and_time(region, time_filter)
    win_loss_data = fetch_hero_win_loss_stats(api_region, min_unix_timestamp, current_time, time_filter)

    if win_loss_data:
        heroes_with_stats = process_hero_data(win_loss_data, win_rate_min, tier_filter)
        return render_template(
            "heroes.html",
            heroes=heroes_with_stats,
            region=region,
            time_filter=time_filter,
            win_rate_min=win_rate_min,
            tier_filter=tier_filter,
        )
    else:
        return "Failed to fetch hero stats", 500




def extract_query_parameters():
    region = request.args.get("region", "Europe")
    time_filter = request.args.get("time_filter", "full")
    win_rate_min = float(request.args.get("win_rate_min", 0))  # Default is 0% winrate as all heroes shown this way
    tier_filter = request.args.get("tier_filter", "")  # Default to no tier filter as all heroes shown this way
    return region, time_filter, win_rate_min, tier_filter


def configure_region_and_time(region, time_filter):
    region_map = {
        "Europe": "Europe",
        "Asia": "SEAsia",
        "NAmerica": "Row",  # No NA on Docs have to use Row
        "SAmerica": "SAmerica",
        "Oceania": "Oceania",
    }
    api_region = region_map.get(region, "Europe")

    current_time = int(time.time())
    time_filter_map = {
        "week": current_time - (7 * 24 * 60 * 60),
        "two_weeks": current_time - (14 * 24 * 60 * 60),
        "month": current_time - (30 * 24 * 60 * 60),
        "three_months": current_time - (90 * 24 * 60 * 60),
        "full": 0,
    }
    min_unix_timestamp = time_filter_map.get(time_filter, 0)
    return api_region, current_time, min_unix_timestamp, time_filter


def fetch_hero_win_loss_stats(api_region, min_unix_timestamp, current_time, time_filter):
    # Fetch and return hero win loss data
    win_loss_url = "https://analytics.deadlock-api.com/v2/hero-win-loss-stats"
    headers = {"accept": "application/json"}
    params = {
        "region": api_region,
        "min_unix_timestamp": min_unix_timestamp,
        "max_unix_timestamp": current_time if time_filter != "full" else None,
    }
    win_loss_response = requests.get(win_loss_url, headers=headers, params=params)
    return win_loss_response.json() if win_loss_response.status_code == 200 else None


def process_hero_data(win_loss_data, win_rate_min, tier_filter):
    # Process and return data to show
    hero_names = {  # Dictionary to hero IDs to hero names
        1: "Infernus", 2: "Seven", 3: "Vindicta", 4: "Lady Geist", 6: "Abrams", 7: "Wraith", 8: "McGigins",
        10: "Paradox", 11: "Dynamo", 12: "Kelvin", 13: "Haze", 15: "Bepop", 17: "Grey Talon",
        18: "Mo and Krill", 19: "Shiv", 20: "Ivy", 25: "Warden", 27: "Yamato", 31: "Lash", 35: "Viscous",
        50: "Pocket", 52: "Mirage",
    }
    exclude_ids = {14, 58, 48, 16, 53, 60, 61, 55, 54}  # List of hero IDs to exclude (test heroes don't want to show)

    total_matches_in_region_and_timeframe = sum(
        hero["wins"] + hero["losses"] for hero in win_loss_data
    )

    heroes_with_stats = []
    for hero in win_loss_data:
        hero_id = hero["hero_id"]
        if hero_id not in exclude_ids:
            name = hero_names.get(hero_id, f"Hero {hero_id}")
            hero_matches = hero["wins"] + hero["losses"]
            win_rate = (hero["wins"] / hero_matches * 100) if hero_matches > 0 else 0
            pick_rate = (
                (hero_matches / total_matches_in_region_and_timeframe * 1000)
                if total_matches_in_region_and_timeframe > 0
                else 0
            )

            # Tier calculations
            tier = "S" if win_rate > 52 and pick_rate > 50 else \
                "A" if win_rate > 50 else \
                "B" if win_rate > 49 else \
                "C" if win_rate > 48 else "D"

            # Apply win rate and tier filters
            if win_rate >= win_rate_min and (not tier_filter or tier == tier_filter):
                heroes_with_stats.append({
                    "name": name,
                    "image": url_for('static', filename=f'images/hero_{hero_id}.png'),
                    "total_matches": hero_matches,
                    "win_rate": f"{win_rate:.2f}%",
                    "pick_rate": f"{pick_rate:.2f}%",
                    "tier": tier,
                })

    # Sort heroes by tier (S > A > B > C > D) and then by win rate (descending)
    tier_order = "SABCD"
    for hero in heroes_with_stats:
        hero["sort_key"] = (tier_order.index(hero["tier"]), -float(hero["win_rate"].strip('%')))

    heroes_with_stats.sort(key=lambda h: h["sort_key"])

    return heroes_with_stats


def resolve_steam_id(nickname, steam_api_key):
    url = f"http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/"
    params = {
        "key": steam_api_key,
        "vanityurl": nickname
    }
    response = requests.get(url, params=params)
    if response.status_code == 200 and response.json().get("response", {}).get("success") == 1:
        return response.json()["response"]["steamid"]  # Return SteamID
    return None


@app.route('/player', methods=['GET'])
def player():
    player_input = request.args.get('player_id')
    if not player_input:
        return render_template("player_search.html")

    # If input is a Steam ID (numeric) or a Steam name (non-numeric)
    if player_input.isdigit():
        steam_id = player_input
    else:
        steam_id = resolve_steam_name_to_id(player_input)  # Conversion
        if not steam_id:
            error_message = "Player not found. Please try again with a valid Steam ID or name."
            return render_template("player_search.html", error_message=error_message)

    # Use converted steam_id to fetch player stats
    url = f"https://data.deadlock-api.com/v1/players/{steam_id}/match-history"
    headers = {"X-API-Key": API_KEY}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        player_data = {
            "matches": response.json()
        }
        return render_template('player_stats.html', player=player_data)
    else:
        error_message = f"Error: Unable to fetch player data (status code {response.status_code})."
        return render_template("player_search.html", error_message=error_message)



def resolve_steam_name_to_id(name):
    account = SteamAccount.query.filter_by(steam_name=name).first()
    return account.steam_id if account else None


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if email already exists
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email is already registered. Please use a different email.', 'danger')
            return redirect(url_for('register'))

        # Hash the password and create a new user
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        user = User(username=form.username.data, email=form.email.data, password_hash=hashed_password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Fetch user by username
        user = User.query.filter_by(username=form.username.data).first()

        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)  # Log the user in
            flash("Login successful!", "success")
            return redirect(url_for('profile'))
        else:
            flash("Invalid username or password.", "danger")

    return render_template('login.html', form=form)



@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Validate current password
        if not check_password_hash(current_user.password_hash, current_password):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for('change_password'))

        # Validate new password confirmation
        if new_password != confirm_password:
            flash("New password and confirm password do not match.", "danger")
            return redirect(url_for('change_password'))

        # Update the password
        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("Your password has been updated successfully.", "success")
        return redirect(url_for('profile'))

    return render_template('change_password.html')


def extract_steamid(identity_url):
    return identity_url.split('/')[-1]


@app.route('/link_steam')
def link_steam():
    steam_openid_url = (
        f"https://steamcommunity.com/openid/login?"
        f"openid.ns=http://specs.openid.net/auth/2.0&"
        f"openid.mode=checkid_setup&"
        f"openid.return_to={url_for('steam_callback', _external=True)}&"
        f"openid.realm={request.host_url}&"
        f"openid.identity=http://specs.openid.net/auth/2.0/identifier_select&"
        f"openid.claimed_id=http://specs.openid.net/auth/2.0/identifier_select"
    )
    return redirect(steam_openid_url)


@app.route('/steam_callback')
def steam_callback():
    openid_claimed_id = request.args.get('openid.claimed_id')

    if openid_claimed_id:
        steam_id = extract_steamid(openid_claimed_id)
        print(f"Extracted SteamID: {steam_id}")

        # Check if SteamID is already linked
        existing_account = SteamAccount.query.filter_by(steam_id=steam_id).first()
        if existing_account:
            flash("This Steam account is already linked to another user.", "info")
            return redirect(url_for('profile'))

        # Ensure user logged in
        if not current_user.is_authenticated:
            flash("You must be logged in to link a Steam account.", "danger")
            return redirect(url_for('login'))

        # Create or update the SteamAccount entry
        steam_account = current_user.steam_account or SteamAccount(user_id=current_user.id)
        steam_account.steam_id = steam_id
        steam_account.steam_name = "Unknown"
        db.session.add(steam_account)
        db.session.commit()

        login_user(current_user)

        flash("Steam account linked successfully!", "success")
        return redirect(url_for('profile'))
    else:
        flash("Failed to authenticate with Steam. Please try again.", "danger")
        return redirect(url_for('profile'))


@app.route('/profile')
@login_required
def profile():
    steam_account = current_user.steam_account
    avatar_url = None
    match_history = []
    favourite_heroes = []  # Store up to 3 heroes
    win_loss = {"wins": 0, "losses": 0}

    if steam_account:
        account_id = int(steam_account.steam_id) - 76561197960265728  # Steam64 ID

        # Fetch Steam profile details
        steam_api_url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
        params = {"key": STEAM_API_KEY, "steamids": steam_account.steam_id}
        response = requests.get(steam_api_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if "response" in data and "players" in data["response"] and len(data["response"]["players"]) > 0:
                player = data["response"]["players"][0]
                avatar_url = player.get("avatarfull")
                steam_account.steam_name = player.get("personaname")
                db.session.commit()

        # Fetch match history
        match_history_url = f"https://data.deadlock-api.com/v2/players/{steam_account.steam_id}/match-history"
        headers = {"X-API-Key": API_KEY}
        match_response = requests.get(match_history_url, headers=headers)
        if match_response.status_code == 200:
            match_history = match_response.json().get("matches", [])
            last_15_matches = match_history[:15]
            for match in last_15_matches:
                if match["match_result"] == match["player_team"]:
                    win_loss["wins"] += 1
                else:
                    win_loss["losses"] += 1

    # Fetch favorite heroes
    favourites = current_user.favourite_heroes.limit(3).all()
    for favourite in favourites:
        hero = Hero.query.get(favourite.hero_id)
        hero_stats = {}

        # Fetch stats only if a Steam account is linked
        if steam_account:
            three_months_ago = int((datetime.now() - timedelta(days=90)).timestamp())
            hero_stats_url = f"https://analytics.deadlock-api.com/v2/players/hero-stats"
            stats_params = {
                "account_ids": account_id,
                "hero_id": hero.id,
                "min_unix_timestamp": three_months_ago,
            }
            stats_response = requests.get(hero_stats_url, headers={"accept": "application/json"}, params=stats_params)
            if stats_response.status_code == 200:
                stats_data = stats_response.json().get(str(account_id), [])
                if stats_data:
                    stats = stats_data[0]
                    hero_stats = {
                        "matches": stats.get("matches", 0),
                        "win_rate": round((stats.get("wins", 0) / stats.get("matches", 1)) * 100, 2) if stats.get(
                            "matches") > 0 else 0,
                        "kills_per_match": round(stats.get("kills", 0) / stats.get("matches", 1), 2) if stats.get(
                            "matches") > 0 else 0,
                        "assists_per_match": round(stats.get("assists", 0) / stats.get("matches", 1), 2) if stats.get(
                            "matches") > 0 else 0,
                    }

        # Append the hero to the favorites list
        favourite_heroes.append({"hero": hero, "stats": hero_stats})

    return render_template(
        'profile.html',
        user=current_user,
        steam_account=steam_account,
        avatar_url=avatar_url,
        match_history=match_history[:15],
        win_loss=win_loss,
        favourite_heroes=favourite_heroes,
    )
