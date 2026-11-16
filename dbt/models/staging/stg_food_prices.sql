-- One row per province, product and month.
select
    {{ ref_month() }}                       as month_start,
    {{ coord(1) }}                          as food_geo_id,
    {{ coord(2) }}                          as product_id,
    {{ value_or_null() }}                   as price,
    coalesce("STATUS", '')                  as status,
    "_release_time"                         as release_time
from {{ source('bronze', 'food_prices') }}
