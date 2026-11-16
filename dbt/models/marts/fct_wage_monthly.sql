-- Median wages by province, industry and type of work, all genders, ages 15 and over.
-- The source is not seasonally adjusted, so a trailing 12-month average is carried next to the raw month.
with base as (
    select
        month_start,
        wage_geo_id,
        industry_id,
        work_type_id,
        max(case when wage_measure_id = 4 then value end)       as median_hourly_wage,
        max(case when wage_measure_id = 5 then value end)       as median_weekly_wage
    from {{ ref('stg_wages') }}
    where gender_id = 1
      and age_group_id = 1
      and wage_measure_id in (4, 5)
      and work_type_id in (1, 2)
      and wage_geo_id in (select wage_geo_id from {{ ref('provinces') }})
    group by 1, 2, 3, 4
)
select
    *,
    case when count(median_weekly_wage) over w = 12 then avg(median_weekly_wage) over w end as median_weekly_wage_12m,
    case when count(median_hourly_wage) over w = 12 then avg(median_hourly_wage) over w end as median_hourly_wage_12m
from base
where median_hourly_wage is not null or median_weekly_wage is not null
window w as (partition by wage_geo_id, industry_id, work_type_id order by month_start rows between 11 preceding and current row)
