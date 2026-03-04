# MCP Server Test Questions

Real natural-language questions to verify the full tool chain works end-to-end.
Each question is tagged with what it exercises.

---

## Basic lookups

**1. Drug overdose deaths by substance and state**
> "How many provisional drug overdose deaths involved cocaine in Texas in 2022?"

- Dataset: `xkb8-kh2a` (VSRR Provisional Drug Overdose Death Counts)
- Exercises: `cdc_search_datasets` → `cdc_query_dataset` with `where` on state + year + indicator

---

**2. COVID-19 total death count**
> "What were total COVID-19 deaths in the United States across all age groups?"

- Dataset: `9bhg-hcku` (Provisional COVID-19 Deaths by Sex and Age)
- Exercises: filtering on `state = 'United States'` and `age_group = 'All Ages'`

---

## Aggregation and ranking

**3. Obesity rates by state**
> "Which states had the highest obesity rates among adults in 2019?"

- Dataset: `hn4x-zwk7` (Nutrition, Physical Activity, and Obesity — BRFSS)
- Exercises: `group_by`, `order_by DESC`, filter on `yearstart` and `question`

---

**4. Flu vaccination trends over time**
> "Compare flu vaccination rates among adolescents (13–17) across different years — which year had the highest coverage?"

- Dataset: `ee48-w5t6` (Vaccination Coverage among Adolescents)
- Exercises: multi-year aggregation, `order_by`

---

## Schema discovery required

**5. Smoking rates by race in New Jersey**
> "What percentage of high school students smoked cigarettes in New Jersey by race in recent years?"

- Dataset: `3b6i-ndew`
- Exercises: `cdc_get_dataset_schema` required before querying (non-obvious column names), filter on `race`

---

**6. Childhood lead testing by geography**
> "Show me childhood blood lead testing results — how many children were tested in zip codes in New York?"

- Dataset: `d54z-enu8` (Childhood Blood Lead Testing)
- Exercises: schema inspection on a geography-heavy dataset with computed region columns

---

## Pagination

**7. All national drug overdose indicators for 2023**
> "List all drug overdose indicators tracked nationally (not by state) for 2023, ordered by death count."

- Dataset: `xkb8-kh2a`
- Exercises: large result set, `has_more` / `next_offset` handling

---

## Multi-dataset reasoning

**8. Obesity vs. heart disease across states**
> "Is there a relationship between obesity rates and heart disease mortality across US states?"

- Datasets: `hn4x-zwk7` (obesity) + `jiwm-ppbh` (heart disease mortality)
- Exercises: agent must query two datasets independently and reason across them

---

## Suggested test order

Start simple and build up:

1. Question 2 (COVID deaths) — confirms basic connectivity, obvious filter values
2. Question 1 (drug overdose) — adds a string enum filter
3. Question 3 (obesity ranking) — first aggregation test
4. Question 5 (NJ smoking) — forces schema lookup
5. Question 7 (pagination) — confirms pagination metadata
6. Question 8 (multi-dataset) — end-to-end stress test
