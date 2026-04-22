-- models/int_tiktok_daily_diff.sql
WITH daily_logs AS (
    SELECT *,
        LAG(total_views) OVER (PARTITION BY video_id ORDER BY log_date) AS prev_views,
        LAG(total_likes) OVER (PARTITION BY video_id ORDER BY log_date) AS prev_likes,
        LAG(total_comments) OVER (PARTITION BY video_id ORDER BY log_date) AS prev_comments,
        LAG(total_shares) OVER (PARTITION BY video_id ORDER BY log_date) AS prev_shares,
        LAG(total_saves) OVER (PARTITION BY video_id ORDER BY log_date) AS prev_saves
    FROM {{ ref('stg_tiktok_stats') }}
)
SELECT
    *,
    -- Tính hiệu số tăng trưởng mỗi ngày cho từng loại chỉ số
    COALESCE(total_views - prev_views, total_views) AS daily_views,
    COALESCE(total_likes - prev_likes, total_likes) AS daily_likes,
    COALESCE(total_comments - prev_comments, total_comments) AS daily_comments,
    COALESCE(total_shares - prev_shares, total_shares) AS daily_shares,
    COALESCE(total_saves - prev_saves, total_saves) AS daily_saves
FROM daily_logs