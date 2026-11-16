-- Asking and paid rent side by side, one row per city, unit type and quarter.
with pivoted as (
    select
        rent_geo_id                                             as city_id,
        unit_type_id,
        quarter_start,
        max(case when estimate_id = 1 then rent end)            as asking_rent,
        max(case when estimate_id = 2 then rent end)            as paid_rent,
        bool_or(estimate_id = 1 and use_with_caution)           as asking_use_with_caution
    from {{ ref('stg_rent') }}
    where rent_geo_id in (select city_id from {{ ref('dim_city') }})
    group by 1, 2, 3
)
select
    *,
    lag(asking_rent, 4) over (partition by city_id, unit_type_id order by quarter_start) as asking_rent_year_ago
from pivoted
where asking_rent is not null or paid_rent is not null
