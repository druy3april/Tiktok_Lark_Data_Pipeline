{{ config(materialized='table') }}

WITH raw_sales AS (
    SELECT DISTINCT channel_name as sales_name
    FROM {{ source('lark_raw', 'business_performance') }}
)

SELECT
    MD5(sales_name) as channel_key,
    sales_name as display_name,
    
    CASE 
        WHEN sales_name ILIKE '%Cảnh%' THEN 'johnny.techguide'
        WHEN sales_name ILIKE '%Huy%'   THEN 'holden_genfarmer'
        WHEN sales_name ILIKE '%Jocelyn%' THEN 'jocelyn.genboxphone'
        WHEN sales_name ILIKE '%Litch%'   THEN 'licht_do1112' 
        WHEN sales_name ILIKE 'Tiktok %t' AND sales_name NOT LIKE '%Huy%' THEN 'pdat.genfarmer'
        WHEN sales_name ILIKE '%Thiên%' THEN 'vt.zerotrace'
        ELSE sales_name 
    END as target_name,

    CASE 
        WHEN sales_name ILIKE '%Cảnh%' THEN '@johnny.techguide'
        WHEN sales_name ILIKE '%Huy%'   THEN '@holden_genfarmer'
        WHEN sales_name ILIKE '%Jocelyn%' THEN '@jocelyn.genboxphone'
        WHEN sales_name ILIKE '%Litch%'   THEN '@licht_do1112'
        WHEN sales_name ILIKE 'Tiktok %t' AND sales_name NOT LIKE '%Huy%' THEN '@pdat.genfarmer'
        WHEN sales_name ILIKE '%Thiên%' THEN '@vt.zerotrace'
        ELSE sales_name 
    END as tiktok_stats_name

FROM raw_sales
