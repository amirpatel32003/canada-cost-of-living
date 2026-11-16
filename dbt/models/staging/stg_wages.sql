-- One row per province, wage measure, type of work, industry, gender, age group and month.
select
    {{ ref_month() }}                       as month_start,
    {{ coord(1) }}                          as wage_geo_id,
    {{ coord(2) }}                          as wage_measure_id,
    {{ coord(3) }}                          as work_type_id,
    {{ coord(4) }}                          as industry_id,
    {{ coord(5) }}                          as gender_id,
    {{ coord(6) }}                          as age_group_id,
    {{ value_or_null() }}                   as value,
    coalesce("STATUS", '')                  as status,
    "_release_time"                         as release_time
from {{ source('bronze', 'wages') }}
