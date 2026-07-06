-- models/models/stg_biz_data.sql
-- Gộp doanh thu TikTok + Instagram từ 2 bảng nguồn.
-- Mỗi dòng Lark = 1 đơn (orders = SUM(order_count)); device tách riêng.
-- Chọn cột tường minh để tránh trùng cột 'platform' khi UNION.

WITH unioned AS (
    SELECT
        platform,
        channel_name,
        revenue,
        order_count,
        device_count,
        log_date
    FROM {{ source('lark_raw', 'business_performance') }}

    UNION ALL

    SELECT
        platform,
        channel_name,
        revenue,
        order_count,
        device_count,
        log_date
    FROM {{ source('lark_raw', 'instagram_performance') }}
),

raw_biz AS (
    SELECT
        platform,
        LOWER(TRIM(channel_name)) AS raw_name,
        revenue,
        order_count,
        device_count,
        log_date
    FROM unioned
)

SELECT
    platform,
    CASE
        WHEN raw_name LIKE '%huy%'     THEN 'holden_genfarmer'
        WHEN raw_name LIKE '%cảnh%'    THEN 'johnny.techguide'
        WHEN raw_name LIKE '%jocelyn%' THEN 'jocelyn.genboxphone'
        WHEN raw_name LIKE '%đạt%'     THEN 'pdat.genfarmer'
        WHEN raw_name LIKE '%thiên%'   THEN 'vt.zerotrace'
        WHEN raw_name LIKE '%litch%' OR raw_name LIKE '%licht%' THEN 'licht_do1112'
        ELSE raw_name -- Không khớp thì giữ nguyên để soi lỗi
    END AS channel_key,
    revenue::FLOAT    AS revenue,
    0                 AS lead_count,
    order_count::INT  AS orders,        -- số ĐƠN thực (mỗi dòng = 1)
    device_count::INT AS device_count,  -- số thiết bị (box + router)
    log_date::DATE    AS log_date
FROM raw_biz
