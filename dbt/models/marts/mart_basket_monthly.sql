-- Cost of the reference grocery basket for one adult, per province and month.
-- A month is kept only when at least 90% of the basket has a price, so a thin month cannot pass as a cheap one.
select
    f.month_start,
    f.food_geo_id,
    round(sum(f.price * p.qty_per_adult_month), 2)              as basket_per_adult,
    count(*)                                                    as items_priced,
    (select count(*) from {{ ref('basket_items') }})            as items_in_basket,
    sum(case when f.is_carried_forward then 1 else 0 end)       as items_carried_forward
from {{ ref('fct_food_price_monthly') }} f
join {{ ref('dim_product') }} p using (product_id)
where p.in_reference_basket
group by 1, 2
having count(*) >= 0.9 * (select count(*) from {{ ref('basket_items') }})
