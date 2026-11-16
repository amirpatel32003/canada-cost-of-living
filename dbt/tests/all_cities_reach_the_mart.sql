-- At least 35 of the 42 cities must make it to the final table, so a broken join cannot ship an empty tool.
select count(*) as n
from {{ ref('mart_city_affordability') }}
having count(*) < {{ var('min_cities', 35) }}
