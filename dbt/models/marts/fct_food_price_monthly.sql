-- Provincial price per product and month. A missing month is filled with the last published price,
-- up to three months back, and flagged so the basket can say how much of it is carried forward.
with spine as (
    select m.month_start, g.food_geo_id, p.product_id
    from (select distinct month_start from {{ ref('stg_food_prices') }}) m
    cross join (select distinct food_geo_id from {{ ref('provinces') }}) g
    cross join (select product_id from {{ ref('dim_product') }}) p
),
joined as (
    select s.*, f.price as published_price
    from spine s
    left join {{ ref('stg_food_prices') }} f using (month_start, food_geo_id, product_id)
),
filled as (
    select
        *,
        last_value(published_price ignore nulls) over w             as last_price,
        last_value(case when published_price is not null then month_start end ignore nulls) over w as last_price_month
    from joined
    window w as (partition by food_geo_id, product_id order by month_start rows between unbounded preceding and current row)
)
select
    month_start,
    food_geo_id,
    product_id,
    case when date_diff('month', last_price_month, month_start) <= 3 then last_price end as price,
    published_price is null                                           as is_carried_forward
from filled
where last_price is not null
  and date_diff('month', last_price_month, month_start) <= 3
