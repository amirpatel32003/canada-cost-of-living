select
    member_id                               as industry_id,
    member_name                             as industry,
    member_id = 1                           as is_all_industries
from {{ ref('stg_members') }}
where table_name = 'wages'
  and dimension_position = 4
