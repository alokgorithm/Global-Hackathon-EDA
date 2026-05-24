# Global Hackathon Landscape Analysis: Insights from 19,000+ Events

[![Dataset Size](https://img.shields.io/badge/Dataset-19%2C098_Records-blue.svg)](https://github.com/alokgorithm/Global-Hackathon-EDA)
[![Data Analysis](https://img.shields.io/badge/Analysis-EDA_%26_Statistics-brightgreen.svg)](https://github.com/alokgorithm/Global-Hackathon-EDA)
[![Language](https://img.shields.io/badge/Language-Python_3.12-yellow.svg)](https://github.com/alokgorithm/Global-Hackathon-EDA)
[![Status](https://img.shields.io/badge/Status-Complete-success.svg)](https://github.com/alokgorithm/Global-Hackathon-EDA)

A comprehensive data analysis of the global hackathon ecosystem exploring the economic drivers, participant engagement, thematic technology trends, and platform dynamics of **19,098 real hackathons** scraped from **Devpost** and **Unstop**.

---

## 🎯 Project Overview & Motivation

In modern tech, hackathons are the breeding grounds for product innovation. However, organizing them is expensive and participating requires massive effort. This project was built to demystify what makes a hackathon successful and attractive. 

We collect, clean, and analyze a highly normalized dataset to answer key strategic questions:
*   **The Power of Incentives:** Do hackathons with cash prizes attract significantly more participants, or do community and networking suffice?
*   **Thematic Leadership:** Which technologies actually dominate developer interest? (AI/ML vs. Web3 vs. Mobile vs. Cybersecurity)
*   **Platform Discrepancies:** How do Devpost (the Western/Global leader) and Unstop (the Indian market leader) compare in scale and audience behavior?
*   **Operational Formats:** Are online hackathons replacing physical, in-person events in terms of volume and engagement?

---

## 🛠️ Data Pipeline & Scraping

The dataset was collected using a custom-engineered Python web scraper (`collect_all_platforms.py`).

*   **Devpost Collection:** Extracted and cleaned historical records containing detailed prize distributions, exact participant counts, and thematic categorizations.
*   **Unstop Collection:** Programmatically queried the internal endpoint (`/api/public/opportunity/search-new`), bypassing a known platform bug where expired events are permanently marked as "LIVE" by comparing registration deadlines (`end_regn_dt`) directly to current dates in real-time.
*   **Filtering and Normalization:** Skip MLH and HackerEarth to focus on Devpost and Unstop. Standardized multi-currency prize structures by programmatically converting INR to USD (at 1 USD ~ 83 INR) to enable homogeneous prize analysis.

---

## 📊 Dataset Dictionary & Schema

The finalized dataset (`data/hackathon_multi_platform_dataset_v2.csv`) is highly structured and contains the following core features:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `id` | String | Unique record identifier (e.g., `unstop_12345` or `devpost_abc`) |
| `name` | String | Title of the hackathon event |
| `url` | String | Live hyperlink to the event's registration page |
| `platform` | String | Hosting platform (`devpost` or `unstop`) |
| `status` | String | Operational status (`open`, `upcoming`, `ended`) |
| `organizer` | String | Name of the hosting company, college, or community group |
| `organizer_type`| String | Categorized host type (`corporate`, `educational`, `community`, `startup`) |
| `location` | String | Physical location/city or marked as `online` |
| `is_online` | Boolean | True if the hackathon is entirely virtual |
| `participant_count`| Integer| Total registered developers / teams |
| `prize_amount_numeric`| Float | Total prize pool converted to USD |
| `prize_tier` | String | Categorized scale (`no_prize`, `micro`, `small`, `medium`, `large`, `mega`) |
| `themes` | String | Pipe-delimited technological tags (e.g., `ai|web|blockchain`) |
| `has_cash_prize` | Boolean | True if the total cash prize pool is greater than $0 |

---

## 📈 Key Findings (Exploratory Data Analysis)

### 1. Platform Dynamics: Devpost vs. Unstop
*   **Volume:** Devpost is the absolute leader in total events (13,298 records), hosting diverse corporate and independent hackathons globally.
*   **Engagement Scale:** Unstop (5,800 records) dominates the Indian student ecosystem. While hosting fewer events overall, Unstop events see massive enrollment spikes, with some university hackathons crossing **100,000+ registered participants** due to structured institutional integration.

### 2. Thematic Dominance: AI is King
*   **AI/ML** appears as one of the strongest themes by event volume and participant interest.
*   Meanwhile, blockchain/Web3 remains more prize-heavy but less broadly represented.

### 3. Prize Economics
*   Over **68%** of global hackathons offer some form of prize.
*   However, true "mega" prize pools (>$50,000) are rare, representing less than **4%** of the ecosystem, mostly backed by enterprise corporate sponsors (Google, Microsoft, Meta).

---

## 🔬 Statistical Hypothesis Testing

To scientifically prove whether offering a cash prize actually drives higher developer participation, we ran a statistical hypothesis test inside **`Hackathon_Analysis.ipynb`**.

### ⚖️ Methodology: Why the Mann-Whitney U Test?
Traditional parametric tests (like the Student's t-test) require the data to follow a normal (Gaussian) distribution. In our dataset, participant counts are **highly right-skewed** (a few massive events have 100k+ participants while the median is 92). 

Because the data is non-normal and heavily skewed, we used the non-parametric **Mann-Whitney U Test** (Wilcoxon rank-sum test) to compare the populations of hackathons *with* cash prizes vs. *without*.

*   **Null Hypothesis ($H_0$):** The distribution of participant counts is identical for hackathons with cash prizes and those without.
*   **Alternate Hypothesis ($H_1$):** Hackathons with cash prizes attract a significantly larger distribution of participants.

### 📊 Results & Conclusion
*   **Median Participants (With Cash Prize):** 89.0
*   **Median Participants (No Cash Prize):** 94.0
*   **p-value:** `0.12` (not statistically significant)

Since the $p$-value is **greater than the significance threshold of $\alpha = 0.05$**, we fail to reject the Null Hypothesis. Interestingly, the data reveals that **in this dataset, cash-prize hackathons did not show a practically stronger median turnout than no-prize/community-driven events, even after statistical testing.**

---

## 💻 How to Run & Reproduce

### 1. Prerequisites
Ensure you have Python 3.10+ installed. Clone the repository and install the unified dependencies:
```bash
git clone https://github.com/alokgorithm/Global-Hackathon-EDA.git
cd Global-Hackathon-EDA
pip install -r requirements.txt
```

### 2. (Optional) Run the Scraper Pipeline
To scrape and re-compile the dataset fresh from the Devpost and Unstop endpoints:
```bash
python collect_all_platforms.py
```

### 3. Open the Analysis Notebook
To view the charts, correlation matrices, and run the Mann-Whitney U test locally:
```bash
jupyter notebook Hackathon_Analysis.ipynb
```

---

## 🏆 Kaggle Integration
The cleaned dataset and analysis notebook are hosted publicly on Kaggle. You can explore the dataset or spin up a Kaggle Notebook directly:
👉 **[Global Hackathons Dataset on Kaggle](https://www.kaggle.com/datasets/new)** *(Kaggle link will be updated upon Sunday release)*

---
*Created as a pure Python & Data Science portfolio project.*
