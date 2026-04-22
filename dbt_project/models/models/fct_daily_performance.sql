-- models/models/fct_daily_performance.sql
WITH daily_tiktok AS (
    -- Gom dữ liệu Tiktok về mức Ngày + Kênh để tránh bị nhân bản
    SELECT
        log_date,
        channel_key,
        editor_name,
        SUM(daily_views) AS total_views,
        SUM(daily_likes + daily_comments + daily_shares + daily_saves) AS total_engagement,
        SUM(daily_likes) AS total_likes,
        SUM(daily_comments) AS total_comments,
        SUM(daily_shares) AS total_shares,
        SUM(daily_saves) AS total_saves,
        COUNT(DISTINCT CASE WHEN log_date = published_date THEN video_id END) AS new_videos
    FROM {{ ref('int_tiktok_daily_diff') }}
    GROUP BY 1, 2, 3
),

daily_biz AS (
    -- Gom dữ liệu Doanh thu (phòng trường hợp 1 ngày có nhiều dòng đơn hàng lẻ)
    SELECT
        log_date,
        channel_key,
        SUM(revenue) AS revenue,
        SUM(lead_count) AS leads
    FROM {{ ref('stg_biz_data') }}
    GROUP BY 1, 2
)

SELECT
    t.log_date,
    t.channel_key,
    t.editor_name,
    t.total_views,
    t.total_engagement,
    t.total_likes,
    t.total_comments,
    t.total_shares,
    t.total_saves,
    -- Tính Viral Score dựa trên số đã gom
    t.total_views + (t.total_engagement * 5) AS viral_score,
    t.new_videos,
    COALESCE(b.revenue, 0) AS revenue,
    COALESCE(b.leads, 0) AS leads
FROM daily_tiktok t
LEFT JOIN daily_biz b 
    ON t.log_date = b.log_date AND t.channel_key = b.channel_key