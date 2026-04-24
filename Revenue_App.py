import streamlit as st
import pandas as pd
import requests
from curl_cffi import requests as curl_requests
from lxml import html


# ============================================================
# Streamlit page config
# ============================================================

st.set_page_config(
    page_title="Roblox Revenue Calculator",
    page_icon="💰",
    layout="wide",
)


# ============================================================
# Styling
# ============================================================

st.markdown(
    """
    <style>
        .main {
            background-color: #f7f8fb;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        .metric-card {
            background: white;
            padding: 1.2rem;
            border-radius: 18px;
            box-shadow: 0 4px 18px rgba(0,0,0,0.06);
            border: 1px solid #eeeeee;
        }

        .section-card {
            background: white;
            padding: 1.5rem;
            border-radius: 20px;
            box-shadow: 0 4px 18px rgba(0,0,0,0.06);
            border: 1px solid #eeeeee;
            margin-bottom: 1rem;
        }

        .big-title {
            font-size: 2.4rem;
            font-weight: 800;
            margin-bottom: 0.25rem;
        }

        .subtitle {
            color: #666;
            font-size: 1rem;
            margin-bottom: 2rem;
        }

        .revenue-total {
            background: linear-gradient(135deg, #111827, #374151);
            color: white;
            padding: 2rem;
            border-radius: 24px;
            text-align: center;
            box-shadow: 0 6px 24px rgba(0,0,0,0.16);
        }

        .revenue-total h1 {
            font-size: 3rem;
            margin: 0;
        }

        .revenue-total p {
            margin: 0;
            color: #d1d5db;
            font-size: 1rem;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.8rem;
            font-weight: 800;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 16px;
            overflow: hidden;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# Roblox API scraper logic
# ============================================================

def get_game_and_passes(place_id):
    universe_url = f"https://apis.roblox.com/universes/v1/places/{place_id}/universe"

    try:
        u_resp = requests.get(universe_url, timeout=30)
        u_resp.raise_for_status()
        universe_id = u_resp.json().get("universeId")

        if not universe_id:
            return None, "Invalid Place ID."

        game_url = f"https://games.roblox.com/v1/games?universeIds={universe_id}"
        votes_url = f"https://games.roblox.com/v1/games/votes?universeIds={universe_id}"

        game_resp = requests.get(game_url, timeout=30)
        votes_resp = requests.get(votes_url, timeout=30)

        game_resp.raise_for_status()
        votes_resp.raise_for_status()

        game_json = game_resp.json()
        votes_json = votes_resp.json()

        if not game_json.get("data"):
            return None, "No Roblox game data found."

        game_data = game_json["data"][0]

        if votes_json.get("data"):
            votes_data = votes_json["data"][0]
        else:
            votes_data = {}

        genre = (
            game_data.get("genre")
            or game_data.get("genre_l1")
            or game_data.get("genre_l2")
            or "Unknown"
        )

        passes_url = (
            f"https://apis.roblox.com/game-passes/v1/universes/"
            f"{universe_id}/game-passes?passView=Full&pageSize=100"
        )

        passes_resp = requests.get(passes_url, timeout=30)
        passes_resp.raise_for_status()

        passes_data = passes_resp.json().get("gamePasses", [])

        return {
            "place_id": place_id,
            "universe_id": universe_id,
            "name": game_data.get("name"),
            "description": game_data.get("description"),
            "genre": genre,
            "creator": game_data.get("creator", {}),
            "visits": game_data.get("visits", 0),
            "playing": game_data.get("playing", 0),
            "favorites": game_data.get("favoritedCount", 0),
            "likes": votes_data.get("upVotes", 0),
            "dislikes": votes_data.get("downVotes", 0),
            "passes": passes_data,
        }, None

    except Exception as e:
        return None, str(e)


# ============================================================
# Rolimons scraper logic
# ============================================================

GAME_DAU_XPATH = "/html/body/div[2]/div[2]/div[9]/div[4]/div/div[2]"

SERVER_USER_COUNT_XPATH = (
    "/html/body/div[2]/div[2]/div[4]/div/div[2]/div/div/div[2]"
    "/div[2]/div[1]/div[2]/div[2]"
)

SERVER_COUNT_XPATH = (
    "/html/body/div[2]/div[2]/div[4]/div/div[2]/div/div/div[2]"
    "/div[2]/div[2]/div[2]/div[2]"
)


def fetch_html(url: str):
    response = curl_requests.get(
        url,
        impersonate="chrome",
        timeout=30,
    )
    response.raise_for_status()
    return html.fromstring(response.text)


def clean_number(value: str):
    value = value.strip().replace(",", "")

    if "." in value:
        return float(value)

    return int(value)


def get_xpath_value(tree, xpath: str, field_name: str):
    elements = tree.xpath(xpath)

    if not elements:
        raise ValueError(f"{field_name} element not found. XPath may have changed.")

    raw_value = elements[0].text_content().strip()
    return clean_number(raw_value)


def scrape_rolimons_game(rolimons_id: str):
    game_url = f"https://www.rolimons.com/game/{rolimons_id}"
    servers_url = f"https://www.rolimons.com/gameservers/{rolimons_id}"

    game_tree = fetch_html(game_url)
    servers_tree = fetch_html(servers_url)

    dau = get_xpath_value(game_tree, GAME_DAU_XPATH, "DAU")
    user_count = get_xpath_value(servers_tree, SERVER_USER_COUNT_XPATH, "User_Count")
    servers = get_xpath_value(servers_tree, SERVER_COUNT_XPATH, "Servers")

    return {
        "Rolimons_ID": rolimons_id,
        "DAU": dau,
        "User_Count": user_count,
        "Servers": servers,
        "Game_URL": game_url,
        "Servers_URL": servers_url,
    }


# ============================================================
# Revenue calculation logic
# ============================================================

QGENRE_TABLE = {
    "pvp": {
        "low": 0.18,
        "high": 0.26,
        "mid": 0.22,
    },
    "horror": {
        "low": 0.15,
        "high": 0.22,
        "mid": 0.185,
    },
    "simulator": {
        "low": 0.12,
        "high": 0.20,
        "mid": 0.16,
    },
    "roleplay": {
        "low": 0.08,
        "high": 0.15,
        "mid": 0.115,
    },
    "obby": {
        "low": 0.03,
        "high": 0.07,
        "mid": 0.05,
    },
}


def detect_qgenre_from_roblox_genre(genre: str, qgenre_mode: str = "mid"):
    if not genre:
        return "unknown", 0

    genre_clean = genre.lower().strip()

    if "pvp" in genre_clean or "fighting" in genre_clean or "combat" in genre_clean or "battle" in genre_clean:
        matched = "pvp"
    elif "horror" in genre_clean:
        matched = "horror"
    elif "simulator" in genre_clean or "simulation" in genre_clean:
        matched = "simulator"
    elif "roleplay" in genre_clean or "role play" in genre_clean or "rp" == genre_clean:
        matched = "roleplay"
    elif "obby" in genre_clean or "obstacle" in genre_clean or "parkour" in genre_clean:
        matched = "obby"
    else:
        matched = "unknown"

    if matched == "unknown":
        return matched, 0

    return matched, QGENRE_TABLE[matched][qgenre_mode]


def get_dev_product_multiplier(visits):
    if visits > 1_000_000:
        return 4
    elif visits > 500_000:
        return 3
    elif visits > 300_000:
        return 2
    elif visits > 50_000:
        return 1
    else:
        return 0


def calculate_average_pass_price(passes):
    paid_passes = [
        p for p in passes
        if p.get("price") is not None
    ]

    if not paid_passes:
        return 0, 0

    average_price = sum(p["price"] for p in paid_passes) / len(paid_passes)
    return average_price, len(paid_passes)


def calculate_daily_revenue(roblox_data, rolimons_data, qgenre_mode="mid", manual_genre=None):
    dau = rolimons_data["DAU"]
    user_count = rolimons_data["User_Count"]
    servers = rolimons_data["Servers"]
    visits = roblox_data["visits"]

    roblox_genre = roblox_data["genre"]

    genre_to_use = manual_genre if manual_genre else roblox_genre

    matched_genre, qgenre = detect_qgenre_from_roblox_genre(
        genre_to_use,
        qgenre_mode=qgenre_mode,
    )

    avg_pass_price, paid_pass_count = calculate_average_pass_price(
        roblox_data["passes"]
    )

    engagement_revenue = dau * qgenre * 5

    pass_revenue = dau * avg_pass_price * 0.70 * qgenre

    multiplier = get_dev_product_multiplier(visits)

    dev_product_revenue = pass_revenue * multiplier

    if servers:
        players_per_server = user_count / servers
    else:
        players_per_server = 0

    server_revenue = servers * players_per_server * 100

    total_revenue = (
        engagement_revenue
        + pass_revenue
        + dev_product_revenue
        + server_revenue
    )

    return {
        "Roblox_Genre": roblox_genre,
        "Genre_Used": genre_to_use,
        "Matched_Genre": matched_genre,
        "Qgenre_Mode": qgenre_mode,
        "Qgenre": qgenre,
        "DAU": dau,
        "Visits": visits,
        "Average_Pass_Price": avg_pass_price,
        "Paid_Pass_Count": paid_pass_count,
        "User_Count": user_count,
        "Servers": servers,
        "Players_Per_Server": players_per_server,
        "Multiplier": multiplier,
        "Engagement_Revenue": engagement_revenue,
        "Pass_Revenue": pass_revenue,
        "Dev_Product_Revenue": dev_product_revenue,
        "Server_Revenue": server_revenue,
        "Total_Revenue": total_revenue,
    }


# ============================================================
# Helper formatting
# ============================================================

def robux(value):
    return f"{value:,.2f} R$"


def number(value):
    return f"{value:,.0f}"


def percent(value):
    return f"{value * 100:.2f}%"


def build_passes_dataframe(passes):
    rows = []

    for p in passes:
        price = p.get("price")

        rows.append(
            {
                "Game Pass Name": p.get("name", "Unknown"),
                "Price": "Off-sale" if price is None else f"{price} R$",
                "Raw Price": price,
                "ID": p.get("id"),
                "Description": p.get("description", ""),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# UI
# ============================================================

st.markdown('<div class="big-title">Roblox Revenue Calculator</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Scrape Roblox and Rolimons data, then estimate daily revenue in Robux.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Input")

    place_id_input = st.text_input(
        "Roblox Place ID",
        placeholder="Example: 123456789",
    )

    st.divider()

    st.header("Revenue Settings")

    qgenre_mode = st.selectbox(
        "Qgenre value",
        options=["mid", "low", "high"],
        index=0,
        help="Uses the Qgenre table: low, midpoint, or high.",
    )

    use_manual_genre = st.checkbox(
        "Override Roblox genre manually",
        value=False,
    )

    manual_genre = None

    if use_manual_genre:
        manual_genre = st.selectbox(
            "Manual genre",
            options=["pvp", "horror", "simulator", "roleplay", "obby"],
            index=2,
        )

    scrape_button = st.button(
        "Calculate Revenue",
        use_container_width=True,
        type="primary",
    )

    st.divider()

    st.caption("Formula")
    st.code(
        """
Engagement Revenue = DAU * Qgenre * 5

Pass Revenue = DAU * Avg Pass Price * 0.70 * Qgenre

Dev Product Revenue = Pass Revenue * Multiplier

Server Revenue = Server Count * Players Per Server * 100

Total Revenue = Sum of all revenue streams
        """.strip()
    )


if not scrape_button:
    st.info("Enter a Roblox Place ID in the sidebar and click Calculate Revenue.")
    st.stop()


if not place_id_input.strip().isdigit():
    st.error("Please enter a numeric Roblox Place ID.")
    st.stop()


place_id = int(place_id_input.strip())


with st.spinner("Fetching Roblox game data..."):
    roblox_data, roblox_error = get_game_and_passes(place_id)

if roblox_error:
    st.error(f"Roblox API error: {roblox_error}")
    st.stop()


with st.spinner("Scraping Rolimons data..."):
    try:
        rolimons_data = scrape_rolimons_game(place_id_input.strip())
    except Exception as e:
        st.error(f"Rolimons error: {e}")
        st.warning(
            "If this game works in the standalone Rolimons scraper, make sure the ID you enter here is the same ID you use on Rolimons."
        )
        st.stop()


revenue = calculate_daily_revenue(
    roblox_data=roblox_data,
    rolimons_data=rolimons_data,
    qgenre_mode=qgenre_mode,
    manual_genre=manual_genre,
)


# ============================================================
# Header summary
# ============================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)

left, right = st.columns([2, 1])

with left:
    st.subheader(roblox_data["name"] or "Unknown Game")
    st.write(f"**Place ID:** {roblox_data['place_id']}")
    st.write(f"**Universe ID:** {roblox_data['universe_id']}")
    st.write(f"**Roblox Genre:** {roblox_data['genre']}")
    st.write(f"**Matched Revenue Genre:** {revenue['Matched_Genre']}")

with right:
    st.markdown(
        f"""
        <div class="revenue-total">
            <p>Total Daily Revenue</p>
            <h1>{revenue['Total_Revenue']:,.2f} R$</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# Main metrics
# ============================================================

st.subheader("Game Metrics")

metric_cols = st.columns(5)

with metric_cols[0]:
    st.metric("DAU", number(revenue["DAU"]))

with metric_cols[1]:
    st.metric("Visits", number(revenue["Visits"]))

with metric_cols[2]:
    st.metric("Currently Playing", number(roblox_data["playing"]))

with metric_cols[3]:
    st.metric("Likes", number(roblox_data["likes"]))

with metric_cols[4]:
    st.metric("Favorites", number(roblox_data["favorites"]))


server_cols = st.columns(4)

with server_cols[0]:
    st.metric("Rolimons Users", number(revenue["User_Count"]))

with server_cols[1]:
    st.metric("Servers", number(revenue["Servers"]))

with server_cols[2]:
    st.metric("Players Per Server", f"{revenue['Players_Per_Server']:,.2f}")

with server_cols[3]:
    st.metric("Dev Product Multiplier", f"{revenue['Multiplier']}x")


# ============================================================
# Revenue breakdown
# ============================================================

st.subheader("Revenue Breakdown")

breakdown_df = pd.DataFrame(
    [
        {
            "Revenue Stream": "Engagement Revenue",
            "Formula": "DAU * Qgenre * 5",
            "Value": revenue["Engagement_Revenue"],
        },
        {
            "Revenue Stream": "Total Pass Revenue",
            "Formula": "DAU * Avg Pass Price * 0.70 * Qgenre",
            "Value": revenue["Pass_Revenue"],
        },
        {
            "Revenue Stream": "Daily Dev Product Revenue",
            "Formula": "Pass Revenue * Multiplier",
            "Value": revenue["Dev_Product_Revenue"],
        },
        {
            "Revenue Stream": "Daily Server Revenue",
            "Formula": "Server Count * Players Per Server * 100",
            "Value": revenue["Server_Revenue"],
        },
        {
            "Revenue Stream": "Total Revenue",
            "Formula": "Sum of all above revenue streams",
            "Value": revenue["Total_Revenue"],
        },
    ]
)

display_breakdown_df = breakdown_df.copy()
display_breakdown_df["Value"] = display_breakdown_df["Value"].map(robux)

st.dataframe(
    display_breakdown_df,
    use_container_width=True,
    hide_index=True,
)


chart_df = breakdown_df[
    breakdown_df["Revenue Stream"] != "Total Revenue"
].copy()

st.bar_chart(
    chart_df,
    x="Revenue Stream",
    y="Value",
    use_container_width=True,
)


# ============================================================
# Calculation inputs
# ============================================================

st.subheader("Calculation Inputs")

calc_cols = st.columns(4)

with calc_cols[0]:
    st.metric("Qgenre Mode", revenue["Qgenre_Mode"])

with calc_cols[1]:
    st.metric("Qgenre Used", percent(revenue["Qgenre"]))

with calc_cols[2]:
    st.metric("Average Pass Price", robux(revenue["Average_Pass_Price"]))

with calc_cols[3]:
    st.metric("Paid Pass Count", number(revenue["Paid_Pass_Count"]))


with st.expander("Show exact calculation details", expanded=False):
    st.code(
        f"""
Engagement Revenue
= {revenue['DAU']} * {revenue['Qgenre']} * 5
= {revenue['Engagement_Revenue']:,.2f} R$

Total Pass Revenue
= {revenue['DAU']} * {revenue['Average_Pass_Price']} * 0.70 * {revenue['Qgenre']}
= {revenue['Pass_Revenue']:,.2f} R$

Daily Dev Product Revenue
= {revenue['Pass_Revenue']:,.2f} * {revenue['Multiplier']}
= {revenue['Dev_Product_Revenue']:,.2f} R$

Daily Server Revenue
= {revenue['Servers']} * {revenue['Players_Per_Server']:.4f} * 100
= {revenue['Server_Revenue']:,.2f} R$

Total Revenue
= {revenue['Engagement_Revenue']:,.2f}
+ {revenue['Pass_Revenue']:,.2f}
+ {revenue['Dev_Product_Revenue']:,.2f}
+ {revenue['Server_Revenue']:,.2f}

= {revenue['Total_Revenue']:,.2f} R$
        """.strip()
    )


# ============================================================
# Game passes table
# ============================================================

st.subheader("Game Passes")

passes_df = build_passes_dataframe(roblox_data["passes"])

if passes_df.empty:
    st.info("No game passes found for this game.")
else:
    st.dataframe(
        passes_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# Links
# ============================================================

st.subheader("Source Links")

link_cols = st.columns(2)

with link_cols[0]:
    st.link_button(
        "Open Rolimons Game Page",
        rolimons_data["Game_URL"],
        use_container_width=True,
    )

with link_cols[1]:
    st.link_button(
        "Open Rolimons Servers Page",
        rolimons_data["Servers_URL"],
        use_container_width=True,
    )
