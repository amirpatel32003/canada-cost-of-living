-- Warn when a city's latest one-bedroom rent is more than three quarters behind the newest quarter in the table.
{{ config(severity = 'warn') }}
select a.city, a.rent_quarter
from {{ ref('mart_city_affordability') }} a
where a.rent_quarter < (select max(quarter_start) from {{ ref('fct_rent_quarterly') }}) - interval 9 month
