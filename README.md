
# Roblox Daily Revenue Calculator

A methodology-focused guide and model for estimating the daily Robux revenue of a Roblox game using activity metrics, monetization assumptions, and server data.

---

## 📌 Overview
The **Roblox Daily Revenue Calculator** provides a directional estimate of a game’s daily earnings. It is designed for developers, analysts, and researchers to compare game performance and understand monetization drivers without requiring private analytics access.

The model aggregates four primary revenue streams:
1.  **Engagement Revenue:** Value derived from active player time.
2.  **Game Pass Revenue:** Sales from one-time purchases.
3.  **Developer Product Revenue:** Income from consumables and repeat purchases.
4.  **Server Revenue:** Estimated value based on active server population.

---

## 🧮 The Core Formula

The total daily revenue is the sum of all individual streams:

$$Total\ Revenue = Engagement + Game\ Pass + Dev\ Product + Server$$

---

## 📊 Methodology & Components

### 1. Engagement Revenue
Estimates the baseline value of your Daily Active Users (DAU), adjusted by genre.
* **Formula:** `DAU * Qgenre * 5`
* **Genre Quality Factors (Qgenre):**
    | Genre | Qgenre | Monetization Profile |
    | :--- | :--- | :--- |
    | **PvP** | 0.26 | Highest (Upgrades, Cosmetics, Boosts) |
    | **Horror** | 0.22 | High (Items, Revives, Access) |
    | **Simulator** | 0.20 | Medium-High (Progression, Pets) |
    | **Roleplay** | 0.15 | Medium (Premium Roles, Vehicles) |
    | **Obby** | 0.07 | Low (Simple purchase paths) |

### 2. Game Pass Revenue
Calculated per pass based on price-sensitive conversion rates.
* **Formula:** `DAU * Price * 0.70 * Conversion Rate`
* **Conversion Scaling:**
    * **Cheapest Pass:** 2.0% conversion.
    * **Most Expensive Pass:** 0.1% conversion.
    * *Intermediate prices are scaled linearly between these two points.*

### 3. Developer Product Revenue
Estimates income from repeat purchases (currency, crates, revives) using a multiplier based on total game visits.
* **Formula:** `Total Pass Revenue * Multiplier`
* **Multipliers:**
    * **> 1M Visits:** 4x
    * **> 500k Visits:** 3x
    * **> 300k Visits:** 2x
    * **< 50k Visits:** 0x (Assumes minimal repeat monetization)

### 4. Server Revenue
Estimates value from active server density and count.
* **Formula:** `User Count (Avg per server) * Server Count * 100`
* **Note:** This treats "User Count" as the average density per server rather than total unique users.

---

## ⚙️ Data Requirements
To run a full calculation, the following inputs are required:

| Data Point | Description |
| :--- | :--- |
| **DAU** | Daily Active Users. |
| **Visits** | Total lifetime visits of the game. |
| **Server Data** | Average users per server and total active server count. |
| **Game Passes** | List of all paid game pass prices. |
| **Genre** | The game's primary category (PvP, Simulator, etc.). |

---

## 🚀 Example Calculation
**Scenario:** A Simulator with 100k DAU, 750k Visits, and 10k R$ in estimated base Pass Revenue.

1.  **Engagement:** `100,000 * 0.20 * 5` = **100,000 R$**
2.  **Passes:** (Sum of scaled conversions) = **10,000 R$**
3.  **Dev Products:** `10,000 * 3x (Visits Multiplier)` = **30,000 R$**
4.  **Server:** `20 (Avg) * 250 (Servers) * 100` = **500,000 R$**

**Total Estimated Daily Revenue: 640,000 R$**

---

*Created for Roblox researchers to better understand the mechanics of game monetization.*

