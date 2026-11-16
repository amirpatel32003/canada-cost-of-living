-- Every basket item must be a product Statistics Canada still publishes, under a name that still matches.
select b.product_id, b.item, p.product
from {{ ref('basket_items') }} b
left join {{ ref('dim_product') }} p using (product_id)
where p.product is null
   or lower(split_part(p.product, ',', 1)) not like '%' || lower(split_part(split_part(b.item, ' (', 1), ' ', 1)) || '%'
