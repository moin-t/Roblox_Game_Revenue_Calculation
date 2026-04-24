import streamlit as st
import requests
from curl_cffi import requests as curl_requests
from lxml import html
import pandas as pd


# =========================
# Page setup
# =========================

st.set_page_config(
    page_title="Roblox Revenue Calculator",
    page_icon="💰",
    layout="wide",
)


# =========================
# Responsive UI helpers
# =========================

st.markdown(
    """
    <style>
        /* Make built-in Streamlit metric values scale down instead of clipping. */
        [data-testid="stMetric"] {
            overflow: visible;
        }

        [data-testid="stMetricValue"] {
            white-space: normal;
            overflow: visible;
        }

        [data-testid="stMetricValue"] div {
            font-size: clamp(1rem, 2.2vw, 1.75rem) !important;
            line-height: 1.15 !important;
            white-space: normal !important;
            overflow-wrap: anywhere;
            word-break: break-word;
        }

        [data-testid="stMetricLabel"] {
            white-space: normal;
        }

        /* Revenue result cards: auto-fit prevents the 5 revenue cards from becoming too narrow. */
        .revenue-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
            gap: 0.85rem;
            margin-top: 0.35rem;
            margin-bottom: 1rem;
        }

        .revenue-card {
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 0.75rem;
            padding: 0.9rem 1rem;
            background: rgba(128, 128, 128, 0.06);
            min-width: 0;
        }

        .revenue-label {
            font-size: 0.9rem;
            opacity: 0.72;
            line-height: 1.2;
            margin-bottom: 0.4rem;
            overflow-wrap: anywhere;
        }

        .revenue-value {
            font-size: clamp(1.05rem, 3vw, 1.65rem);
            font-weight: 700;
            line-height: 1.15;
            white-space: normal;
            overflow-wrap: anywhere;
            word-break: break-word;
        }

        @media (max-width: 700px) {
            .revenue-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def format_robux(value):
    """Format Robux values compactly for cards while preserving useful precision."""
    if value is None:
        return "N/A"

    abs_value = abs(value)

    if abs_value >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:,.2f}T R$"

    if abs_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:,.2f}B R$"

    if abs_value >= 1_000_000:
        return f"{value / 1_000_000:,.2f}M R$"

    if abs_value >= 1_000:
        return f"{value / 1_000:,.2f}K R$"

    return f"{value:,.2f} R$"


def render_revenue_cards(items):
    cards_html = "".join(
        f"""
        <div class="revenue-card">
            <div class="revenue-label">{label}</div>
            <div class="revenue-value" title="{full_value}">{display_value}</div>
        </div>
        """
        for label, display_value, full_value in items
    )

    st.markdown(
        f"<div class=\"revenue-grid\">{cards_html}</div>",
        unsafe_allow_html=True,
    )


# =========================
# Roblox API scraper logic
# =========================

def get_game_and_passes(place_id):
    universe_url = f"https://apis.roblox.com/universes/v1/places/{place_id}/universe"

    try:
        u_resp = requests.get(universe_url, timeout=30)
        u_resp.raise_for_status()
        universe_id = u_resp.json().get("universeId")

        if not universe_id:
            return None, "❌ Invalid Place ID."

        game_url = f"https://games.roblox.com/v1/games?universeIds={universe_id}"
        votes_url = f"https://games.roblox.com/v1/games/votes?universeIds={universe_id}"

        game_resp = requests.get(game_url, timeout=30)
        votes_resp = requests.get(votes_url, timeout=30)

        game_resp.raise_for_status()
        votes_resp.raise_for_status()

        game_json = game_resp.json()
        votes_json = votes_resp.json()

        if not game_json.get("data"):
            return None, "❌ No game data found."

        game_data = game_json["data"][0]
        votes_data = votes_json["data"][0] if votes_json.get("data") else {}

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
            "genre": game_data.get("genre"),
            "visits": game_data.get("visits"),
            "likes": votes_data.get("upVotes"),
            "passes": passes_data,
        }, None

    except Exception as e:
        return None, f"⚠️ Roblox API Error: {e}"


# =========================
# Rolimons scraper logic
# =========================

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
    try:
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
        }, None

    except Exception as e:
        return None, f"⚠️ Rolimons Error: {e}"


# =========================
# Revenue calculation logic
# =========================

QGENRE_TABLE = {
    "pvp": 0.26,
    "horror": 0.22,
    "simulator": 0.20,
    "roleplay": 0.15,
    "obby": 0.07,
}


def normalize_genre(genre):
    if not genre:
        return None

    genre_lower = genre.lower()

    if "pvp" in genre_lower or "fighting" in genre_lower or "battle" in genre_lower:
        return "pvp"

    if "horror" in genre_lower:
        return "horror"

    if "simulator" in genre_lower or "sim" in genre_lower:
        return "simulator"

    if "roleplay" in genre_lower or "role" in genre_lower or "rp" in genre_lower:
        return "roleplay"

    if "obby" in genre_lower or "obstacle" in genre_lower or "parkour" in genre_lower:
        return "obby"

    return None


def get_qgenre(roblox_genre, manual_genre=None):
    if manual_genre and manual_genre != "auto":
        return manual_genre, QGENRE_TABLE[manual_genre]

    matched_genre = normalize_genre(roblox_genre)

    if matched_genre and matched_genre in QGENRE_TABLE:
        return matched_genre, QGENRE_TABLE[matched_genre]

    return "simulator", QGENRE_TABLE["simulator"]


def get_dev_product_multiplier(visits):
    if visits is None:
        return 0

    if visits > 1_000_000:
        return 4

    if visits > 500_000:
        return 3

    if visits > 300_000:
        return 2

    if visits > 50_000:
        return 1

    return 0


def calculate_pass_conversion_rates(passes):
    paid_passes = [
        p for p in passes
        if p.get("price") is not None
    ]

    if not paid_passes:
        return []

    prices = [p["price"] for p in paid_passes]
    min_price = min(prices)
    max_price = max(prices)

    pass_results = []

    for p in paid_passes:
        price = p["price"]

        if min_price == max_price:
            conversion_rate = 0.02
        else:
            conversion_rate = 0.02 - (
                (price - min_price) / (max_price - min_price)
            ) * (0.02 - 0.001)

        pass_results.append({
            "name": p.get("name", "Unknown"),
            "price": price,
            "conversion_rate": conversion_rate,
        })

    return pass_results


def calculate_daily_revenue(
    roblox_data,
    rolimons_data,
    manual_genre=None,
    custom_dau=None,
    custom_user_count=None,
    custom_servers=None,
):
    dau = custom_dau if custom_dau is not None else rolimons_data["DAU"]
    user_count = custom_user_count if custom_user_count is not None else rolimons_data["User_Count"]
    servers = custom_servers if custom_servers is not None else rolimons_data["Servers"]

    visits = roblox_data["visits"]
    roblox_genre = roblox_data.get("genre")

    matched_genre, qgenre = get_qgenre(roblox_genre, manual_genre)

    engagement_revenue = dau * qgenre * 5

    pass_results = calculate_pass_conversion_rates(roblox_data["passes"])

    total_pass_revenue = 0

    for p in pass_results:
        pass_revenue = dau * p["price"] * 0.70 * p["conversion_rate"]
        p["daily_revenue"] = pass_revenue
        total_pass_revenue += pass_revenue

    multiplier = get_dev_product_multiplier(visits)
    dev_product_revenue = total_pass_revenue * multiplier

    if servers:
        players_per_server = user_count / servers
    else:
        players_per_server = 0

    server_revenue = servers * players_per_server * 100

    total_revenue = (
        engagement_revenue
        + total_pass_revenue
        + dev_product_revenue
        + server_revenue
    )

    return {
        "DAU": dau,
        "User_Count": user_count,
        "Servers": servers,
        "Players_Per_Server": players_per_server,
        "Visits": visits,
        "Roblox_Genre": roblox_genre,
        "Matched_Genre": matched_genre,
        "Qgenre": qgenre,
        "Engagement_Revenue": engagement_revenue,
        "Passes": pass_results,
        "Total_Pass_Revenue": total_pass_revenue,
        "Dev_Product_Multiplier": multiplier,
        "Dev_Product_Revenue": dev_product_revenue,
        "Server_Revenue": server_revenue,
        "Total_Revenue": total_revenue,
    }


# =========================
# Streamlit UI
# =========================

st.title("💰 Roblox Daily Revenue Calculator")
st.caption("Calculates estimated daily Robux revenue using Roblox API, Rolimons data, game passes, DAU, servers, and genre-based Qgenre.")

with st.sidebar:
    st.header("Input")

    place_id_input = st.text_input(
        "Roblox Place ID",
        placeholder="Example: 920587237",
    )

    st.divider()

    st.subheader("Genre Override")

    manual_genre = st.selectbox(
        "Revenue genre",
        options=["auto", "pvp", "horror", "simulator", "roleplay", "obby"],
        index=0,
        help="Auto tries to map Roblox API genre to your Qgenre table. You can override it here.",
    )

    st.divider()

    st.subheader("Manual Overrides")

    use_manual_metrics = st.checkbox(
        "Override Rolimons DAU / users / servers",
        value=False,
    )

    custom_dau = None
    custom_user_count = None
    custom_servers = None

    if use_manual_metrics:
        custom_dau = st.number_input(
            "Manual DAU",
            min_value=0.0,
            value=0.0,
            step=100.0,
        )

        custom_user_count = st.number_input(
            "Manual User Count",
            min_value=0.0,
            value=0.0,
            step=10.0,
        )

        custom_servers = st.number_input(
            "Manual Server Count",
            min_value=0.0,
            value=0.0,
            step=1.0,
        )

    st.divider()

    calculate_button = st.button(
        "Calculate Revenue",
        type="primary",
        use_container_width=True,
    )


st.markdown(
    """
    ### Revenue formulas

    **Engagement Revenue** = `DAU * Qgenre * 5`

    **Pass Revenue of each pass** = `DAU * Pass Price * 0.70 * Conversion %`

    **Total Pass Revenue** = `sum(all pass revenues)`

    **Daily Dev Product Revenue** = `Total Pass Revenue * Multiplier`

    **Daily Server Revenue** = `Server Count * Players Per Server * 100`

    **Total Revenue** = `Engagement + Pass + Dev Product + Server`
    """
)


if calculate_button:
    if not place_id_input.strip().isdigit():
        st.error("Please enter a numeric Roblox Place ID.")
        st.stop()

    place_id = int(place_id_input.strip())

    with st.spinner("Fetching Roblox game data..."):
        roblox_data, roblox_error = get_game_and_passes(place_id)

    if roblox_error:
        st.error(roblox_error)
        st.stop()

    with st.spinner("Fetching Rolimons DAU and server data..."):
        rolimons_data, rolimons_error = scrape_rolimons_game(place_id_input.strip())

    if rolimons_error and not use_manual_metrics:
        st.error(rolimons_error)
        st.info("Tip: enable manual overrides in the sidebar if Rolimons fails for this ID.")
        st.stop()

    if rolimons_error and use_manual_metrics:
        st.warning(rolimons_error)
        rolimons_data = {
            "Rolimons_ID": place_id_input.strip(),
            "DAU": custom_dau,
            "User_Count": custom_user_count,
            "Servers": custom_servers,
            "Game_URL": f"https://www.rolimons.com/game/{place_id_input.strip()}",
            "Servers_URL": f"https://www.rolimons.com/gameservers/{place_id_input.strip()}",
        }

    revenue = calculate_daily_revenue(
        roblox_data=roblox_data,
        rolimons_data=rolimons_data,
        manual_genre=manual_genre,
        custom_dau=custom_dau if use_manual_metrics else None,
        custom_user_count=custom_user_count if use_manual_metrics else None,
        custom_servers=custom_servers if use_manual_metrics else None,
    )

    st.success("Revenue calculation complete.")

    # =========================
    # Game summary
    # =========================

    st.header("🎮 Game Data")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Game", roblox_data["name"] or "Unknown")

    with col2:
        st.metric("Visits", f"{roblox_data['visits']:,}" if roblox_data["visits"] else "N/A")

    with col3:
        st.metric("Likes", f"{roblox_data['likes']:,}" if roblox_data["likes"] is not None else "N/A")

    with col4:
        st.metric("Genre", roblox_data["genre"] or "Unknown")

    col5, col6 = st.columns(2)

    with col5:
        st.write(f"**Place ID:** `{roblox_data['place_id']}`")
        st.write(f"**Universe ID:** `{roblox_data['universe_id']}`")

    with col6:
        st.write(f"**Rolimons Game URL:** {rolimons_data['Game_URL']}")
        st.write(f"**Rolimons Servers URL:** {rolimons_data['Servers_URL']}")

    # =========================
    # Rolimons summary
    # =========================

    st.header("📊 Rolimons Metrics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("DAU", f"{revenue['DAU']:,.0f}")

    with col2:
        st.metric("User Count", f"{revenue['User_Count']:,.0f}")

    with col3:
        st.metric("Servers", f"{revenue['Servers']:,.0f}")

    with col4:
        st.metric("Players / Server", f"{revenue['Players_Per_Server']:,.2f}")

    # =========================
    # Revenue summary
    # =========================

    st.header("💰 Daily Revenue Estimate")

    revenue_cards = [
        (
            "Engagement Revenue",
            format_robux(revenue["Engagement_Revenue"]),
            f"{revenue['Engagement_Revenue']:,.2f} R$",
        ),
        (
            "Pass Revenue",
            format_robux(revenue["Total_Pass_Revenue"]),
            f"{revenue['Total_Pass_Revenue']:,.2f} R$",
        ),
        (
            "Dev Product Revenue",
            format_robux(revenue["Dev_Product_Revenue"]),
            f"{revenue['Dev_Product_Revenue']:,.2f} R$",
        ),
        (
            "Server Revenue",
            format_robux(revenue["Server_Revenue"]),
            f"{revenue['Server_Revenue']:,.2f} R$",
        ),
        (
            "Total Revenue",
            format_robux(revenue["Total_Revenue"]),
            f"{revenue['Total_Revenue']:,.2f} R$",
        ),
    ]

    render_revenue_cards(revenue_cards)

    st.subheader("Calculation Settings")

    settings_df = pd.DataFrame([
        {
            "Setting": "Roblox Genre",
            "Value": revenue["Roblox_Genre"],
        },
        {
            "Setting": "Matched Revenue Genre",
            "Value": revenue["Matched_Genre"],
        },
        {
            "Setting": "Qgenre",
            "Value": f"{revenue['Qgenre'] * 100:.2f}%",
        },
        {
            "Setting": "Dev Product Multiplier",
            "Value": f"{revenue['Dev_Product_Multiplier']}x",
        },
    ])

    st.dataframe(settings_df, use_container_width=True, hide_index=True)

    # =========================
    # Pass revenue table
    # =========================

    st.header("🎟️ Game Pass Revenue Breakdown")

    if revenue["Passes"]:
        pass_df = pd.DataFrame(revenue["Passes"])

        pass_df["conversion_percent"] = pass_df["conversion_rate"] * 100

        display_pass_df = pass_df.rename(columns={
            "name": "Pass Name",
            "price": "Price R$",
            "conversion_percent": "Conversion %",
            "daily_revenue": "Daily Revenue R$",
        })[
            [
                "Pass Name",
                "Price R$",
                "Conversion %",
                "Daily Revenue R$",
            ]
        ]

        st.dataframe(
            display_pass_df,
            use_container_width=True,
            hide_index=True,
        )

        csv = display_pass_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download pass revenue CSV",
            data=csv,
            file_name="pass_revenue_breakdown.csv",
            mime="text/csv",
        )

    else:
        st.info("No paid game passes found.")

    # =========================
    # Formula detail
    # =========================

    st.header("🧮 Formula Breakdown")

    st.code(
        f"""
Engagement Revenue
= DAU * Qgenre * 5
= {revenue['DAU']:,.0f} * {revenue['Qgenre']} * 5
= {revenue['Engagement_Revenue']:,.2f} R$

Total Pass Revenue
= Sum of each pass: DAU * Pass Price * 0.70 * Conversion %
= {revenue['Total_Pass_Revenue']:,.2f} R$

Dev Product Revenue
= Total Pass Revenue * Multiplier
= {revenue['Total_Pass_Revenue']:,.2f} * {revenue['Dev_Product_Multiplier']}
= {revenue['Dev_Product_Revenue']:,.2f} R$

Server Revenue
= Server Count * Players Per Server * 100
= {revenue['Servers']:,.0f} * {revenue['Players_Per_Server']:,.2f} * 100
= {revenue['Server_Revenue']:,.2f} R$

Total Revenue
= Engagement + Pass + Dev Product + Server
= {revenue['Engagement_Revenue']:,.2f}
+ {revenue['Total_Pass_Revenue']:,.2f}
+ {revenue['Dev_Product_Revenue']:,.2f}
+ {revenue['Server_Revenue']:,.2f}
= {revenue['Total_Revenue']:,.2f} R$
        """,
        language="text",
    )

else:
    st.info("Enter a Roblox Place ID in the sidebar and click **Calculate Revenue**.")
