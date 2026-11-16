-- One row per city: the latest rent, the grocery basket, the typical full-time wage in the province,
-- and how rent has moved against wages since 2019.
with latest_q as (
    select city_id, max(quarter_start) as quarter_start
    from {{ ref('fct_rent_quarterly') }}
    where unit_type_id = 2 and asking_rent is not null
    group by 1
),
rent_now as (
    select
        r.city_id,
        l.quarter_start,
        max(case when r.unit_type_id = 5 then r.asking_rent end)    as rent_room,
        max(case when r.unit_type_id = 1 then r.asking_rent end)    as rent_studio,
        max(case when r.unit_type_id = 2 then r.asking_rent end)    as rent_1bed,
        max(case when r.unit_type_id = 3 then r.asking_rent end)    as rent_2bed,
        max(case when r.unit_type_id = 4 then r.asking_rent end)    as rent_3bed,
        max(case when r.unit_type_id = 2 then r.asking_rent_year_ago end) as rent_1bed_year_ago
    from {{ ref('fct_rent_quarterly') }} r
    join latest_q l on l.city_id = r.city_id and l.quarter_start = r.quarter_start
    group by 1, 2
),
rent_2019 as (
    select city_id, avg(asking_rent) as rent_1bed_2019
    from {{ ref('fct_rent_quarterly') }}
    where unit_type_id = 2 and year(quarter_start) = 2019
    group by 1
    having count(asking_rent) >= 2
),
wage as (
    select wage_geo_id, month_start, median_weekly_wage_12m, median_hourly_wage_12m
    from {{ ref('fct_wage_monthly') }}
    where industry_id = 1 and work_type_id = 2 and median_weekly_wage_12m is not null
),
wage_now as (
    select * from wage
    qualify row_number() over (partition by wage_geo_id order by month_start desc) = 1
),
wage_2019 as (
    select wage_geo_id, median_weekly_wage_12m as weekly_wage_2019
    from wage
    where month_start = date '2019-12-01'
),
basket_now as (
    select food_geo_id, month_start as basket_month, basket_per_adult
    from {{ ref('mart_basket_monthly') }}
    qualify row_number() over (partition by food_geo_id order by month_start desc) = 1
)
select
    c.city_id,
    c.city,
    c.province_code,
    c.province,
    r.quarter_start                                             as rent_quarter,
    r.rent_room,
    r.rent_studio,
    r.rent_1bed,
    r.rent_2bed,
    r.rent_3bed,
    b.basket_month,
    b.basket_per_adult,
    w.month_start                                               as wage_month,
    round(w.median_hourly_wage_12m, 2)                          as median_hourly_wage,
    round(w.median_weekly_wage_12m * 52)                        as median_annual_wage,
    round(r.rent_1bed / (w.median_weekly_wage_12m * 52 / 12), 4) as rent_share_of_median_wage,
    round(r.rent_1bed * 12 / {{ var('affordability_threshold') }}) as income_needed_1bed,
    round(r.rent_1bed / nullif(r.rent_1bed_year_ago, 0) - 1, 4) as rent_change_1y,
    round(r.rent_1bed / nullif(r19.rent_1bed_2019, 0) - 1, 4)   as rent_change_since_2019,
    round(w.median_weekly_wage_12m / nullif(w19.weekly_wage_2019, 0) - 1, 4) as wage_change_since_2019
from {{ ref('dim_city') }} c
join rent_now r using (city_id)
left join rent_2019 r19 using (city_id)
left join wage_now w on w.wage_geo_id = c.wage_geo_id
left join wage_2019 w19 on w19.wage_geo_id = c.wage_geo_id
left join basket_now b on b.food_geo_id = c.food_geo_id
