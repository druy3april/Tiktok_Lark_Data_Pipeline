-- models/models/fct_kpi_progress.sql
WITH unique_videos AS (
    -- Bước 1: Lấy danh sách video duy nhất và ngày đăng của chúng
    SELECT DISTINCT 
        video_id, 
        channel_key, 
        editor_name, 
        published_date
    FROM {{ ref('stg_tiktok_stats') }}
    WHERE published_date IS NOT NULL
),

weekly_kpi AS (
    -- Bước 2: Tính theo tuần
    SELECT
        channel_key,
        editor_name,
        DATE_TRUNC('week', published_date) AS period_start,
        'WEEKLY' AS period_type,
        COUNT(video_id) AS actual_videos,
        4 AS target_videos
    FROM unique_videos
    GROUP BY 1, 2, 3
),

monthly_kpi AS (
    -- Bước 3: Tính theo tháng
    SELECT
        channel_key,
        editor_name,
        DATE_TRUNC('month', published_date) AS period_start,
        'MONTHLY' AS period_type,
        COUNT(video_id) AS actual_videos,
        16 AS target_videos
    FROM unique_videos
    GROUP BY 1, 2, 3
)

-- Bước 4: Gộp chung vào một bảng báo cáo
SELECT 
    *,
    CASE WHEN actual_videos >= target_videos THEN 'PASS' ELSE 'FAIL' END AS status
FROM weekly_kpi
UNION ALL
SELECT 
    *,
    CASE WHEN actual_videos >= target_videos THEN 'PASS' ELSE 'FAIL' END AS status
FROM monthly_kpi