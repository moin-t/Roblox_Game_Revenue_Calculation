# Roblox Daily Revenue Calculator

An interactive Streamlit app that estimates the **daily Robux revenue** of a Roblox game using:

- Roblox public API data
- Rolimons game/server data
- Game pass pricing
- Genre-based engagement revenue
- Visit-based developer product multiplier
- Private server revenue estimation

The final output is an estimated **Total Daily Revenue in Robux**.

---

## Features

- Fetches Roblox game information from a Place ID
- Converts Place ID to Universe ID using Roblox API
- Fetches:
  - Game name
  - Genre
  - Visits
  - Likes
  - Game passes and prices
- Scrapes Rolimons for:
  - DAU
  - Active user count
  - Server count
- Calculates:
  - Engagement revenue
  - Game pass revenue
  - Developer product revenue
  - Server revenue
  - Total daily revenue
- Provides pass-by-pass revenue breakdown
- Allows manual overrides for:
  - Genre
  - DAU
  - User count
  - Server count
- Exports game pass revenue breakdown as CSV

---

## Installation

### 1. Clone or download the project

Make sure your project folder contains:

```text
streamlit_app.py
requirements.txt
README.md
