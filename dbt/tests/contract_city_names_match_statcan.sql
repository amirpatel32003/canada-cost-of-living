-- Data contract: the geography id we map to each city must still carry that city's name at Statistics Canada.
-- If they renumber the table, this fails instead of quietly showing Regina's rent under Toronto.
select c.city_id, c.statcan_name, m.member_name
from {{ ref('dim_city') }} c
left join {{ ref('stg_members') }} m
  on m.table_name = 'rent' and m.dimension_position = 1 and m.member_id = c.city_id
where m.member_name is null
   or not starts_with(m.member_name, c.statcan_name)
