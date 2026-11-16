"""Build small offline copies of the three Statistics Canada tables, in the exact published format.

The numbers are synthetic (seeded from real September 2026 Ontario prices and a few real rents) so tests and
CI can run the whole pipeline without calling Statistics Canada. Run: python tests/make_fixtures.py
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

OUT = Path(__file__).parent / "fixtures"

CITIES = """1=St. John's;2=Halifax;3=Fredericton;4=Moncton;5=Saint John;6=Drummondville;7=Montréal;8=Ottawa - Gatineau (Quebec part);9=Québec;10=Saguenay;11=Sherbrooke;12=Trois-Rivières;13=Barrie;14=Belleville - Quinte West;15=Brantford;16=Greater Sudbury;17=Guelph;18=Hamilton;19=Kingston;20=Kitchener - Cambridge - Waterloo;21=London;22=Oshawa;23=Ottawa - Gatineau (Ontario part);24=Peterborough;25=St. Catharines - Niagara;26=Thunder Bay;27=Toronto;28=Windsor;29=Winnipeg;30=Regina;31=Saskatoon;32=Calgary;33=Edmonton;34=Lethbridge;35=Red Deer;36=Abbotsford - Mission;37=Chilliwack;38=Kamloops;39=Kelowna;40=Nanaimo;41=Vancouver;42=Victoria"""
UNITS = {6: "House - 2 bedrooms", 7: "House - 3 or more bedrooms", 1: "Apartment - No bedroom", 2: "Apartment - 1 bedroom",
         3: "Apartment - 2 bedrooms", 4: "Apartment - 3 or more bedrooms", 5: "Room"}
UNIT_FACTOR = {1: 0.84, 2: 1.0, 3: 1.27, 4: 1.56, 5: 0.40, 6: 1.30, 7: 1.74}
ONE_BED_2026 = {27: 2090, 30: 1250, 41: 2400, 7: 1650, 32: 1700, 2: 1900, 23: 1950, 33: 1350, 29: 1300, 42: 2050}

PRODUCTS = """1=Beef stewing cuts, per kilogram [27.36]; 2=Beef striploin cuts, per kilogram [39.56]; 3=Beef top sirloin cuts, per kilogram [33.40]; 41=Beef rib cuts, per kilogram [32.57]; 4=Ground beef, per kilogram [17.23]; 5=Pork loin cuts, per kilogram [8.26]; 6=Pork rib cuts, per kilogram [8.84]; 42=Pork shoulder cuts, per kilogram [9.43]; 7=Whole chicken, per kilogram [8.05]; 8=Chicken breasts, per kilogram [13.58]; 9=Chicken thigh, per kilogram [13.15]; 43=Chicken drumsticks, per kilogram [7.92]; 10=Bacon, 500 grams [6.26]; 11=Wieners, 400 grams [4.74]; 78=Salmon, per kilogram [27.84]; 79=Shrimp, 300 grams [7.34]; 44=Canned salmon, 213 grams [5.68]; 12=Canned tuna, 170 grams [1.69]; 80=Meatless burgers, 226 grams [6.85]; 13=Milk, 1 litre [3.96]; 14=Milk, 2 litres [5.93]; 15=Milk, 4 litres [6.93]; 81=Soy milk, 1.89 litres [4.32]; 82=Nut milk, 1.89 litres [4.32]; 16=Cream, 1 litre [4.63]; 17=Butter, 454 grams [5.48]; 83=Margarine, 907 grams [5.64]; 18=Block cheese, 500 grams [6.87]; 19=Yogurt, 500 grams [3.84]; 20=Eggs, 1 dozen [5.02]; 21=Apples, per kilogram [4.54]; 22=Oranges, per kilogram [4.29]; 23=Oranges, 1.36 kilograms [5.27]; 24=Bananas, per kilogram [1.69]; 25=Pears, per kilogram [5.45]; 26=Lemons, unit [1.05]; 45=Limes, unit [0.71]; 27=Grapes, per kilogram [6.31]; 28=Cantaloupe, unit [2.60]; 84=Strawberries, 454 grams [4.89]; 29=Avocado, unit [1.95]; 30=Potatoes, 4.54 kilograms [3.56]; 46=Potatoes, per kilogram [5.38]; 47=Sweet potatoes, per kilogram [3.73]; 31=Tomatoes, per kilogram [4.43]; 32=Cabbage, per kilogram [2.34]; 33=Carrots, 1.36 kilograms [3.34]; 34=Onions, per kilogram [5.59]; 35=Onions, 1.36 kilograms [4.66]; 36=Celery, unit [2.60]; 37=Cucumber, unit [1.36]; 38=Mushrooms, 227 grams [2.54]; 48=Iceberg lettuce, unit [2.73]; 49=Romaine lettuce, unit [2.94]; 39=Broccoli, unit [2.41]; 40=Peppers, per kilogram [6.52]; 85=Squash, per kilogram [3.30]; 86=Salad greens, 142 grams [4.26]; 50=Frozen french fried potatoes, 750 grams [3.22]; 51=Frozen green beans, 750 grams [4.34]; 52=Frozen broccoli, 500 grams [3.83]; 53=Frozen corn, 750 grams [3.59]; 54=Frozen mixed vegetables, 750 grams [4.03]; 55=Frozen peas, 750 grams [3.65]; 87=Frozen pizza, 390 grams [4.64]; 88=Frozen spinach, 300 grams [2.16]; 89=Frozen strawberries, 600 grams [5.20]; 56=White bread, 675 grams [3.26]; 90=Flatbread and pita, 500 grams [3.20]; 91=Crackers and crisp breads, 200 grams [2.63]; 92=Cookies and sweet biscuits, 300 grams [3.40]; 57=Dry or fresh pasta, 500 grams [3.34]; 93=Brown rice, 900 grams [5.85]; 94=White rice, 2 kilograms [9.06]; 58=Cereal, 400 grams [4.08]; 59=Wheat flour, 2.5 kilograms [5.13]; 60=White sugar, 2 kilograms [2.63]; 61=Apple juice, 2 litres [3.76]; 62=Orange juice, 2 litres [5.98]; 63=Roasted or ground coffee, 340 grams [9.18]; 64=Tea (20 bags) [4.34]; 65=Ketchup, 1 litre [4.68]; 66=Vegetable oil, 3 litres [8.38]; 95=Canola oil, 3 litres [10.40]; 96=Olive oil, 1 litre [10.25]; 67=Baby food, 128 millilitres [1.53]; 97=Infant formula, 900 grams [50.76]; 68=Peanut butter, 1 kilogram [6.01]; 69=Mayonnaise, 890 millilitres [6.73]; 70=Canned baked beans, 398 millilitres [1.67]; 71=Canned tomatoes, 796 millilitres [2.15]; 72=Canned soup, 284 millilitres [1.29]; 73=Canned beans and lentils, 540 millilitres [1.72]; 98=Canned corn, 341 millilitres [1.65]; 99=Canned peach, 398 millilitres [2.45]; 100=Canned pear, 398 millilitres [2.71]; 74=Dried lentils, 900 grams [3.56]; 101=Dry beans and legumes, 900 grams [3.57]; 102=Tofu, 350 grams [2.79]; 103=Hummus, 227 grams [3.71]; 104=Salsa, 418 millilitres [5.27]; 105=Pasta sauce, 650 millilitres [3.27]; 106=Salad dressing, 475 millilitres [3.62]; 107=Almonds, 200 grams [5.27]; 108=Peanuts, 450 grams [4.16]; 109=Sunflower seeds, 400 grams [4.86]; 75=Deodorant, 85 grams [8.31]; 76=Toothpaste, 100 millilitres [4.41]; 77=Shampoo, 400 millilitres [7.31]; 110=Laundry detergent, 4.43 litres [14.00]"""
FOOD_GEO = {11: "Canada", 1: "Newfoundland and Labrador", 2: "Prince Edward Island", 3: "Nova Scotia", 4: "New Brunswick",
            5: "Quebec", 6: "Ontario", 7: "Manitoba", 8: "Saskatchewan", 9: "Alberta", 10: "British Columbia",
            12: "Whitehorse, Yukon", 13: "Yellowknife, Northwest Territories"}
FOOD_FACTOR = {11: 1.0, 1: 1.08, 2: 1.04, 3: 1.05, 4: 1.03, 5: 0.96, 6: 1.0, 7: 0.99, 8: 1.01, 9: 1.02, 10: 1.06}
WAGE_GEO = {1: "Canada", 2: "Newfoundland and Labrador", 3: "Prince Edward Island", 4: "Nova Scotia", 5: "New Brunswick",
            6: "Quebec", 7: "Ontario", 8: "Manitoba", 9: "Saskatchewan", 10: "Alberta", 11: "British Columbia"}
WAGE_BASE = {1: 30.0, 2: 28.0, 3: 25.5, 4: 26.5, 5: 26.0, 6: 29.5, 7: 31.0, 8: 27.5, 9: 29.5, 10: 33.0, 11: 32.0}
INDUSTRIES = ["Total employees, all industries", "Goods-producing sector", "Agriculture",
              "Forestry, fishing, mining, quarrying, oil and gas", "Utilities", "Construction", "Manufacturing",
              "Services-producing sector", "Wholesale and retail trade", "Transportation and warehousing",
              "Finance, insurance, real estate, rental and leasing", "Professional, scientific and technical services",
              "Business, building and other support services", "Educational services", "Health care and social assistance",
              "Information, culture and recreation", "Accommodation and food services",
              "Other services (except public administration)", "Public administration"]
IND_FACTOR = [1.0, 1.1, 0.72, 1.45, 1.5, 1.15, 1.0, 0.97, 0.72, 0.98, 1.2, 1.4, 0.75, 1.3, 1.02, 0.85, 0.58, 0.8, 1.4]
STD = ["UOM", "UOM_ID", "SCALAR_FACTOR", "SCALAR_ID", "VECTOR", "COORDINATE", "VALUE", "STATUS", "SYMBOL", "TERMINATED", "DECIMALS"]


def wobble(*key) -> float:
    """Deterministic value in [-1, 1] from the key, so fixtures are stable across runs."""
    h = 2166136261
    for ch in "|".join(map(str, key)):
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h / 0xFFFFFFFF * 2 - 1


def months(start: tuple[int, int], end: tuple[int, int], step: int = 1):
    y, m = start
    while (y, m) <= end:
        yield y, m
        m += step
        if m > 12:
            y, m = y + 1, m - 12


def write_zip(pid: int, header: list[str], rows: list[list], meta: dict) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    with zipfile.ZipFile(OUT / f"{pid}-eng.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{pid}.csv", buf.getvalue())
        zf.writestr(f"{pid}_MetaData.csv", "Cube Title,Product Id\n")
    (OUT / f"{pid}-meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def dim(pos: int, name: str, members: dict[int, str], parent: int | None = None) -> dict:
    return {"dimensionPositionId": pos, "dimensionNameEn": name,
            "member": [{"memberId": k, "memberNameEn": v, "parentMemberId": parent if k != parent else None, "terminated": 0}
                       for k, v in members.items()]}


def rent() -> None:
    cities = {int(k): v for k, v in (c.split("=") for c in CITIES.split(";"))}
    geo = {43: "All census metropolitan areas", **{k: f"{v}, Census metropolitan area (CMA)" for k, v in cities.items()}}
    rows = []
    quarters = list(months((2019, 1), (2026, 4), 3))
    for g, gname in geo.items():
        base_now = ONE_BED_2026.get(g, 1730 if g == 43 else round(1100 + 500 * (wobble("city", g) + 1) / 2, -1))
        growth = 0.045 + 0.02 * wobble("growth", g)
        for u, uname in UNITS.items():
            for i, (y, m) in enumerate(quarters):
                years_back = (len(quarters) - 1 - i) / 4
                val = base_now * UNIT_FACTOR[u] / (1 + growth) ** years_back * (1 + 0.01 * wobble(g, u, i))
                status = ""
                if u in (6, 7) and y < 2022:
                    status = ".."            # houses were added to the program later
                elif g in (10, 12) and u in (4, 5):
                    status = "F"             # small markets: too unreliable to publish
                elif g in (6, 35, 37) and u == 4:
                    status = "E"
                value = "" if status in ("..", "F") else str(int(round(val, -1)))
                rows.append([f"{y}-{m:02d}", gname, "" if g == 43 else f"2021S0503{g:03d}", uname, "Average asking rent",
                             "Dollars", "81", "units", "0", f"v{1000000 + g * 100 + u}", f"{g}.{u}.1", value, status, "", "", "0"])
                if u in (2, 3) and g in (27, 41, 7, 30, 32, 43) and y >= 2024:
                    paid = str(int(round(val * 0.86, -1)))
                    rows.append([f"{y}-{m:02d}", gname, "", uname, "Average paid rent", "Dollars", "81", "units", "0",
                                 f"v{2000000 + g * 100 + u}", f"{g}.{u}.2", paid, "E" if g == 30 else "", "", "", "0"])
    meta = {"productId": "46100092", "cubeTitleEn": "Asking rent and paid rent prices, by rental unit type and number of bedrooms, experimental estimates",
            "cubeStartDate": "2019-01-01", "cubeEndDate": "2026-04-01", "releaseTime": "2026-09-09T08:30", "frequencyCode": 9,
            "dimension": [dim(1, "Geography", geo, 43), dim(2, "Rental unit type", UNITS),
                          dim(3, "Estimates", {1: "Average asking rent", 2: "Average paid rent"})]}
    write_zip(46100092, ["REF_DATE", "GEO", "DGUID", "Rental unit type", "Estimates"] + STD, rows, meta)


def food() -> None:
    products, price = {}, {}
    for part in PRODUCTS.split("; "):
        left, p = part.rsplit(" [", 1)
        pid, name = left.split("=", 1)
        products[int(pid)] = name
        price[int(pid)] = float(p.rstrip("]"))
    rows = []
    all_months = list(months((2024, 1), (2026, 9)))
    for g, gname in FOOD_GEO.items():
        if g not in FOOD_FACTOR:
            continue
        for pid, name in products.items():
            for i, (y, m) in enumerate(all_months):
                back = (len(all_months) - 1 - i) / 12
                val = price[pid] * FOOD_FACTOR[g] / 1.035 ** back * (1 + 0.02 * wobble(g, pid, i))
                status, value = "", f"{val:.2f}"
                if g == 6 and i == len(all_months) - 1:
                    value = f"{price[pid]:.2f}"     # the real Ontario price for September 2026
                if g == 2 and pid in (78, 49) and i >= len(all_months) - 2:
                    status, value = "..", ""       # exercises the carry-forward rule
                rows.append([f"{y}-{m:02d}", gname, f"2021A0002{g:02d}", name, "Dollars", "81", "units", "0",
                             f"v{3000000 + g * 1000 + pid}", f"{g}.{pid}", value, status, "", "", "2"])
    meta = {"productId": "18100245", "cubeTitleEn": "Monthly average retail prices for selected products",
            "cubeStartDate": "2017-01-01", "cubeEndDate": "2026-09-01", "releaseTime": "2026-11-04T08:30", "frequencyCode": 6,
            "dimension": [dim(1, "Geography", FOOD_GEO), dim(2, "Products", products)]}
    write_zip(18100245, ["REF_DATE", "GEO", "DGUID", "Products"] + STD, rows, meta)


def wages() -> None:
    measures = {1: "Total employees, all wages", 2: "Average hourly wage rate", 3: "Average weekly wage rate",
                4: "Median hourly wage rate", 5: "Median weekly wage rate"}
    work = {1: "Both full- and part-time employees", 2: "Full-time employees", 3: "Part-time employees"}
    industries = {i + 1: n for i, n in enumerate(INDUSTRIES)}
    rows = []
    all_months = list(months((2018, 1), (2026, 10)))
    for g, gname in WAGE_GEO.items():
        for ind in industries:
            for wt in (1, 2):
                for i, (y, m) in enumerate(all_months):
                    back = (len(all_months) - 1 - i) / 12
                    hourly = WAGE_BASE[g] * IND_FACTOR[ind - 1] * (1.06 if wt == 2 else 1.0) / 1.04 ** back
                    hourly *= 1 + 0.015 * wobble(g, ind, wt, m)      # a seasonal pattern that repeats each year
                    weekly = hourly * (39.5 if wt == 2 else 35.0)
                    for meas, val in ((4, hourly), (5, weekly)):
                        rows.append([f"{y}-{m:02d}", gname, "", measures[meas], work[wt], industries[ind], "Total - Gender",
                                     "15 years and over", "Current dollars", "75", "units", "0",
                                     f"v{4000000 + g * 10000 + ind * 100 + wt * 10 + meas}", f"{g}.{meas}.{wt}.{ind}.1.1",
                                     f"{val:.2f}", "", "", "", "2"])
    # a few rows the models must filter out: one gender split and one age split
    rows.append(["2026-10", "Ontario", "", measures[4], work[2], industries[1], "Women+", "15 years and over", "Current dollars",
                 "75", "units", "0", "v4999001", "7.4.2.1.3.1", "29.00", "", "", "", "2"])
    rows.append(["2026-10", "Ontario", "", measures[4], work[2], industries[1], "Total - Gender", "15 to 24 years", "Current dollars",
                 "75", "units", "0", "v4999002", "7.4.2.1.1.2", "19.00", "", "", "", "2"])
    meta = {"productId": "14100063", "cubeTitleEn": "Employee wages by industry, monthly, unadjusted for seasonality",
            "cubeStartDate": "1997-01-01", "cubeEndDate": "2026-10-01", "releaseTime": "2026-11-06T08:30", "frequencyCode": 6,
            "dimension": [dim(1, "Geography", WAGE_GEO), dim(2, "Wages", measures), dim(3, "Type of work", work),
                          dim(4, "North American Industry Classification System (NAICS)", industries),
                          dim(5, "Gender", {1: "Total - Gender", 2: "Men+", 3: "Women+"}),
                          dim(6, "Age group", {1: "15 years and over", 2: "15 to 24 years", 3: "25 to 54 years", 4: "55 years and over"})]}
    write_zip(14100063, ["REF_DATE", "GEO", "DGUID", "Wages", "Type of work", "North American Industry Classification System (NAICS)",
                         "Gender", "Age group"] + STD, rows, meta)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    rent()
    food()
    wages()
    for f in sorted(OUT.iterdir()):
        print(f.name, f.stat().st_size)
