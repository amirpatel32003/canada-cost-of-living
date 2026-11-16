-- Every product in the food price table, flagged when it is part of the reference basket.
select
    m.member_id                             as product_id,
    m.member_name                           as product,
    b.item                                  as basket_label,
    b.category                              as basket_category,
    coalesce(b.qty_per_adult_month, 0)      as qty_per_adult_month,
    b.product_id is not null                as in_reference_basket
from {{ ref('stg_members') }} m
left join {{ ref('basket_items') }} b on b.product_id = m.member_id
where m.table_name = 'food_prices'
  and m.dimension_position = 2
