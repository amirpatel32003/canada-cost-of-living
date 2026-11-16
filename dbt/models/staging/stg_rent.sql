-- One row per metro area, unit type, estimate and quarter. Values Statistics Canada did not publish become null.
select
    {{ ref_month() }}                       as quarter_start,
    {{ coord(1) }}                          as rent_geo_id,
    {{ coord(2) }}                          as unit_type_id,
    {{ coord(3) }}                          as estimate_id,
    {{ value_or_null() }}                   as rent,
    coalesce("STATUS", '')                  as status,
    coalesce("STATUS", '') = 'E'            as use_with_caution,
    "_release_time"                         as release_time
from {{ source('bronze', 'rent') }}
