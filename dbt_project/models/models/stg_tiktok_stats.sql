-- models/models/stg_tiktok_stats.sql
WITH clean_tiktok AS (
    SELECT 
        *,
        LOWER(TRIM(REGEXP_REPLACE(channel_name, 'https?://(www\.)?tiktok\.com/@?|^@', ''))) AS cleaned_handle
    FROM {{ source('lark_raw', 'tiktok_video_stats') }}
)
SELECT
    video_id,
    CASE 
        WHEN cleaned_handle IN ('tiktok huy', 'huy') THEN 'holden_genfarmer'
        -- Thêm các trường hợp khác nếu cần, hoặc nếu cleaned_handle đã chuẩn rồi thì thôi
        ELSE cleaned_handle 
    END AS channel_key,
    editor_name,
    view_count::BIGINT AS total_views,
    like_count::BIGINT AS total_likes,
    comment_count::BIGINT AS total_comments,
    share_count::BIGINT AS total_shares,
    save_count::BIGINT AS total_saves,
    follower_count::BIGINT AS follower_count,
    log_date::DATE AS log_date,
    published_date::DATE AS published_date
FROM clean_tiktok