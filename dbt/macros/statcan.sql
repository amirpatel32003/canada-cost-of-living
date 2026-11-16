{# Statistics Canada puts every dimension's member id in COORDINATE, e.g. "27.3.1".
   Reading ids from it keeps the models working when a column gets renamed (as "Sex" became "Gender"). #}
{% macro coord(position) -%}
    cast(split_part("COORDINATE", '.', {{ position }}) as integer)
{%- endmacro %}

{% macro ref_month() -%}
    cast(strptime("REF_DATE" || '-01', '%Y-%m-%d') as date)
{%- endmacro %}

{# Status symbols: ".." not available, "F" too unreliable to publish, "x" suppressed, "E" use with caution. #}
{% macro value_or_null() -%}
    case when "STATUS" in ('..', 'F', 'x', '...') then null else try_cast("VALUE" as double) end
{%- endmacro %}
