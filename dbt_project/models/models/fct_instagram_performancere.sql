-- models/models/fct_instagram_performance.sql
-- Doanh thu Instagram, gom theo NGÀY + TÊN KÊNH (khớp 1-1 instagram_performance).
-- Tách hoàn toàn khỏi luồng TikTok; channel_key = tên kênh sạch (Cảnh, Quang Vũ...).

SELECT
    log_date,
    channel_key,
    'instagram'::text AS platform,
    SUM(revenue)      AS revenue,
    SUM(orders)       AS orders,
    SUM(device_count) AS device_count,
    SUM(lead_count)   AS leads
FROM {{ ref('stg_biz_data') }}
WHERE platform = 'instagram'
GROUP BY 1, 2
