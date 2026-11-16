-- Dimension members for every table, from the Statistics Canada metadata. Used for labels and contract tests.
select 'rent' as table_name, * from {{ source('bronze', 'rent_members') }}
union all
select 'food_prices' as table_name, * from {{ source('bronze', 'food_prices_members') }}
union all
select 'wages' as table_name, * from {{ source('bronze', 'wages_members') }}
