-- The 42 metro areas with rent data, each tied to the province whose food prices and wages apply to it.
select
    c.rent_geo_id                           as city_id,
    c.city,
    c.statcan_name,
    c.province_code,
    p.province,
    p.food_geo_id,
    p.wage_geo_id,
    c.lat,
    c.lon
from {{ ref('cities') }} c
join {{ ref('provinces') }} p using (province_code)
