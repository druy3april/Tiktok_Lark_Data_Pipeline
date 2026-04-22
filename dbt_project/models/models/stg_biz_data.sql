-- models/models/stg_biz_data.sql
WITH raw_biz AS (
    SELECT 
        LOWER(TRIM(channel_name)) AS raw_name,
        revenue,
        order_count,
        log_date
    FROM {{ source('lark_raw', 'business_performance') }}
)
SELECT
    CASE 
        WHEN raw_name LIKE '%huy%' THEN 'holden_genfarmer'
        WHEN raw_name LIKE '%cảnh%' THEN 'johnny.techguide'
        WHEN raw_name LIKE '%jocelyn%' THEN 'jocelyn.genboxphone'
        WHEN raw_name LIKE '%đạt%' THEN 'pdat.genfarmer'
        WHEN raw_name LIKE '%thiên%' THEN 'vt.zerotrace'
        WHEN raw_name LIKE '%litch%' OR raw_name LIKE '%licht%' THEN 'licht_do1112'
        ELSE raw_name -- Nếu không khớp thì giữ nguyên để soi lỗi
    END AS channel_key,
    revenue::FLOAT AS revenue,
    0 AS lead_count,
    order_count::INT AS orders,
    log_date::DATE AS log_date
FROM raw_biz