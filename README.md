# Can I afford to live there?

**Live tool: https://amirpatel32003.github.io/canada-cost-of-living/**

Type in your income and household, pick one of 40 Canadian cities, and the page works out what rent and groceries take out of your month, which cities fit the 30% guideline at your income, and whether pay has kept up with rent since 2019.

You can also compare cities on the typical full-time pay for your industry in each province, see what is left after rent and groceries, work out the income you would need to move without losing ground, and download the table or the underlying data as CSV.

Behind it is a pipeline that checks Statistics Canada every day, reloads a table only when it has a new release, rebuilds the models in dbt, runs 47 data tests, and publishes the result.

[![CI](https://github.com/amirpatel32003/canada-cost-of-living/actions/workflows/ci.yml/badge.svg)](https://github.com/amirpatel32003/canada-cost-of-living/actions/workflows/ci.yml)
[![Refresh data and publish](https://github.com/amirpatel32003/canada-cost-of-living/actions/workflows/refresh.yml/badge.svg)](https://github.com/amirpatel32003/canada-cost-of-living/actions/workflows/refresh.yml)

## What the data says (November 2026 run)

- In 34 of 40 cities, asking rent for a one-bedroom has grown faster than the typical full-time wage in the province since 2019. Toronto, Vancouver, Victoria, Ottawa, Hamilton and Chilliwack are the six where pay grew faster.
- Toronto's one-bedroom asking rent is 5.6% above its 2019 average while Ontario's typical full-time wage is up 32%. In Trois-Rivières the same rent has doubled, from about $480 to $970.
- On the typical full-time wage, a one-bedroom takes more than 30% of income in 8 of 40 cities. Vancouver is highest at 37.5% and Trois-Rivières lowest at 17.1%.
- In Toronto, tenants already in a one-bedroom pay $1,840 on average. New listings ask $2,090.
- The pipeline loads 13.6 million rows, almost all of them from the wages table.

These figures come from the live run and will move as Statistics Canada publishes new quarters.

## The question

Rent reports give one number per city. That number does not tell a household of three on $72,000 whether Halifax or Calgary leaves them more at the end of the month. To answer that you need rent by unit size, food prices, and local pay in one place, kept current. Statistics Canada publishes all three, in three tables with different geographies, different frequencies and different release dates.

## What it does

| Step | Tool | What happens |
|---|---|---|
| Ingest | Python, DuckDB | Asks the Statistics Canada Web Data Service for each table's release time. Downloads the full table only when the release changed, and lands it as Parquet with every column kept as text. |
| Model | dbt (DuckDB) | Staging views type the data and turn unpublished values into nulls. Marts join rent (city, quarterly) to food prices and wages (province, monthly). |
| Test | dbt tests, pytest | 47 data tests on every build, including contract tests against Statistics Canada's own metadata. 14 pytest cases run the whole pipeline on offline fixtures. |
| Orchestrate | Airflow, GitHub Actions | The Airflow DAG is executed end to end in CI on every push. The daily production run uses GitHub Actions because it is free to host. Both call the same commands. |
| Serve | Static page | One JSON file and one HTML page with no framework. Every figure on the page comes from a dbt mart. |

```
Statistics Canada WDS
   rent 46-10-0092      food prices 18-10-0245      wages 14-10-0063
        |                        |                         |
        +---- ingest: new release? download : skip --------+
                                 |
                     bronze (Parquet, all text)
                                 |
              dbt staging (typed, nulls for unpublished)
                                 |
   dim_city  dim_product  dim_industry  fct_rent_quarterly
   fct_food_price_monthly  fct_wage_monthly  mart_basket_monthly
                                 |
                     mart_city_affordability
                                 |
                site/data/app.json  ->  the tool
```

## Decisions worth explaining

**Read ids from COORDINATE, not from column names.** Every Statistics Canada row carries a coordinate such as `27.3.1` (Toronto, two-bedroom apartment, asking rent). The models split that instead of matching on text columns, so they keep working when a column is renamed, as happened when "Sex" became "Gender" in the labour tables.

**Contract tests against the source's metadata.** City 27 is Toronto only as long as Statistics Canada says so. Three tests compare the ids in the seed files to the names in the table's live metadata. If the table is renumbered the build fails. Without the tests it would show Regina's rent under Toronto and nothing would look wrong.

**Unpublished is not zero.** About a third of the rent table is marked `..` (not available), `F` (too unreliable to publish) or `E` (use with caution). The first two become nulls and the page says no rent is published. `E` values are kept and labelled on the page.

**A missing food price is carried forward for three months at most, and flagged.** A basket with one product missing would otherwise drop by the price of that product and look like food got cheaper.

**Wages use a trailing 12-month average.** The source is not seasonally adjusted, so a single month would move the result for reasons that have nothing to do with pay.

**Incremental by release, not by date.** Statistics Canada revises history, so appending new rows is wrong. A table is reloaded in full when its release time changes and skipped otherwise. On most days nothing is downloaded.

**Airflow and dbt in separate environments.** The DAG shells out to the project's Python, so neither tool pins the other's dependencies.

## Run it yourself

```bash
pip install -r requirements.txt

# offline, on the fixtures in tests/fixtures (about 10 seconds)
COL_SOURCE_DIR=tests/fixtures python -m pipeline.run all

# against live Statistics Canada (downloads about 100 MB the first time)
python -m pipeline.run all

python -m http.server -d site 8000     # then open http://localhost:8000
python -m pytest -q tests
```

To run the DAG, point Airflow's `dags_folder` at `dags/` and set `COL_PYTHON` to the Python that has the requirements installed. CI does exactly this with `airflow dags test`.

The warehouse is DuckDB so anyone can run this without an account. `dbt/profiles.yml` also has a BigQuery target. I have not run the project on BigQuery yet, so treat that target as a starting point.

## Open data files

The publish job writes three files next to the page, rebuilt on every run:

- [`cities.csv`](https://amirpatel32003.github.io/canada-cost-of-living/data/cities.csv): one row per city with the latest rents, basket cost, typical pay and rent growth against wage growth.
- [`rent_quarterly.csv`](https://amirpatel32003.github.io/canada-cost-of-living/data/rent_quarterly.csv): asking and paid rent for every city, home type and quarter since 2019.
- [`app.json`](https://amirpatel32003.github.io/canada-cost-of-living/data/app.json): everything the page uses, including prices for 110 grocery items by province.

## Limits

- The rent table lists 42 metro areas. Saguenay and Drummondville have no published one-bedroom rent, so the tool shows 40.

- Rent is the average asking rent of online listings in a metro area. It says nothing about a specific neighbourhood, and people who have not moved in years pay less.
- Food prices and wages are provincial. A city inside a province gets that province's figures.
- The starting grocery basket is my own list of staples, not an official one. It is in `dbt/seeds/basket_items.csv` and anyone can change the quantities on the page.
- Income tax, utilities, transit and child care are left out. The page says so next to every total.
- The rent series is labelled experimental by Statistics Canada and starts in 2019.

## Data

Statistics Canada, tables 46-10-0092-01, 18-10-0245-01 and 14-10-0063-01. Contains information licensed under the Statistics Canada Open Licence. This project is not affiliated with Statistics Canada.

## Author

Amir Patel, Toronto. [Portfolio](https://amirpatel32003.github.io/) · [LinkedIn](https://www.linkedin.com/in/connect-amir)
