-- models/models/fct_instagram_performance.sql
-- Doanh thu Instagram — lấy TRỰC TIẾP từ instagram_performance (nguồn đã đúng).
-- KHÔNG qua stg_biz_data, KHÔNG map tên kênh, KHÔNG gộp dòng.
-- Mỗi dòng khớp 1-1 với bảng instagram_performance: đúng tên kênh, đúng ngày, đúng doanh thu.

SELECT
    log_date::DATE            AS log_date,
    TRIM(channel_name)        AS channel_name,   -- giữ nguyên: Cảnh, Quang Vũ, N.D.K.Linh
    'instagram'::text         AS platform,
    revenue::FLOAT            AS revenue,
    order_count::INT          AS orders,
    device_count::INT         AS device_count,
    week_label,
    month_label
FROM {{ source('lark_raw', 'instagram_performance') }}
