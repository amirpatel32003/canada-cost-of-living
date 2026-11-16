-- Same contract for the province ids used to join food prices and wages.
select p.province, 'food_prices' as table_name, m.member_name
from {{ ref('provinces') }} p
left join {{ ref('stg_members') }} m
  on m.table_name = 'food_prices' and m.dimension_position = 1 and m.member_id = p.food_geo_id
where m.member_name is distinct from p.province
union all
select p.province, 'wages', m.member_name
from {{ ref('provinces') }} p
left join {{ ref('stg_members') }} m
  on m.table_name = 'wages' and m.dimension_position = 1 and m.member_id = p.wage_geo_id
where m.member_name is distinct from p.province
