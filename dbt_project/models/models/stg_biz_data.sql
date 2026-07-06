-- models/models/stg_biz_data.sql
-- Gộp doanh thu TikTok + Instagram từ 2 bảng nguồn.
--
-- ⚠ QUY TẮC MAP channel_key KHÁC NHAU GIỮA 2 NỀN TẢNG:
--   • TikTok    → map tên người sang HANDLE kênh TikTok (johnny.techguide,...)
--                 để JOIN được với stg_tiktok_stats trong fct_daily_performance.
--   • Instagram → GIỮ NGUYÊN tên kênh sạch từ instagram_performance
--                 (Cảnh, Quang Vũ, N.D.K.Linh...). KHÔNG map sang handle TikTok,
--                 vì Instagram là kênh độc lập, tên phải khớp 1-1 với bảng gốc.
--
-- platform gán CỨNG theo bảng nguồn (không lấy từ cột 'platform' cũ vì từng sai).
-- Mỗi dòng Lark = 1 đơn (orders = order_count); revenue/device giữ nguyên → khớp 1-1.

WITH tiktok_src AS (
    -- Nguồn TikTok: map tên người → handle kênh
    SELECT
        'tiktok'::text AS platform,
        LOWER(TRIM(channel_name)) AS raw_name,
        CASE
            WHEN LOWER(TRIM(channel_name)) LIKE '%huy%'     THEN 'holden_genfarmer'
            WHEN LOWER(TRIM(channel_name)) LIKE '%cảnh%'    THEN 'johnny.techguide'
            WHEN LOWER(TRIM(channel_name)) LIKE '%jocelyn%' THEN 'jocelyn.genboxphone'
            WHEN LOWER(TRIM(channel_name)) LIKE '%đạt%'     THEN 'pdat.genfarmer'
            WHEN LOWER(TRIM(channel_name)) LIKE '%thiên%'   THEN 'vt.zerotrace'
            WHEN LOWER(TRIM(channel_name)) LIKE '%litch%'
              OR LOWER(TRIM(channel_name)) LIKE '%licht%'   THEN 'licht_do1112'
            ELSE LOWER(TRIM(channel_name))   -- không khớp → giữ nguyên để soi lỗi
        END AS channel_key,
        revenue,
        order_count,
        device_count,
        log_date
    FROM {{ source('lark_raw', 'business_performance') }}
),

instagram_src AS (
    -- Nguồn Instagram: GIỮ NGUYÊN tên kênh sạch, khớp 1-1 với instagram_performance.
    -- Chỉ chuẩn hóa TRIM (không đổi tên) để tên hiển thị đúng như bảng gốc.
    SELECT
        'instagram'::text AS platform,
        LOWER(TRIM(channel_name)) AS raw_name,
        TRIM(channel_name) AS channel_key,   -- ví dụ: 'Cảnh', 'Quang Vũ', 'N.D.K.Linh'
        revenue,
        order_count,
        device_count,
        log_date
    FROM {{ source('lark_raw', 'instagram_performance') }}
),

unioned AS (
    SELECT platform, raw_name, channel_key, revenue, order_count, device_count, log_date
    FROM tiktok_src
    UNION ALL
    SELECT platform, raw_name, channel_key, revenue, order_count, device_count, log_date
    FROM instagram_src
)

SELECT
    platform,
    channel_key,
    revenue::FLOAT    AS revenue,
    0                 AS lead_count,
    order_count::INT  AS orders,        -- số ĐƠN thực (mỗi dòng = 1)
    device_count::INT AS device_count,  -- số thiết bị (box + router)
    log_date::DATE    AS log_date
FROM unioned
