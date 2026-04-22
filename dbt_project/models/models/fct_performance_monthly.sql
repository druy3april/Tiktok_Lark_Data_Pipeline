{{ config(materialized='table') }}

WITH monthly_sales AS (
    -- 1. Gom doanh thu thực tế theo tháng và kênh
    SELECT 
        -- Đảm bảo tháng luôn là định dạng T4/2026 để khớp với Target
        REPLACE(month_label, 'Tháng ', 'T') as month_label,
        channel_name,
        SUM(revenue) as actual_revenue,
        SUM(order_count) as actual_orders
    FROM {{ source('lark_raw', 'business_performance') }}
    GROUP BY 1, 2
),

monthly_target AS (
    -- 2. Lấy chỉ tiêu từ bảng Target
    SELECT 
        month_label,
        channel_name as target_channel_name,
        CAST(target_revenue AS NUMERIC) as target_revenue,
        CAST(target_leads AS NUMERIC) as target_leads
    FROM {{ source('lark_raw', 'stg_lark_target') }}
),

clean_dim AS (
    -- 3. Làm sạch bảng DIM để tránh làm nhân đôi doanh thu khi JOIN
    SELECT DISTINCT 
        channel_key,
        display_name,
        target_name
    FROM {{ ref('dim_channels') }}
)

SELECT 
    s.month_label,
    dim.channel_key,
    s.channel_name as sales_display_name,
    s.actual_revenue,
    t.target_revenue,
    
    -- Tính % hoàn thành doanh thu
    CASE 
        WHEN t.target_revenue > 0 THEN (s.actual_revenue / t.target_revenue) * 100 
        ELSE 0 
    END as revenue_achievement_rate,
    
    s.actual_orders,
    t.target_leads

FROM monthly_sales s
-- Join với DIM để lấy 'tên đã ánh xạ' (target_name)
JOIN clean_dim dim ON s.channel_name = dim.display_name
-- Left Join với Target dựa trên tên đã ánh xạ và tháng
LEFT JOIN monthly_target t 
    ON s.month_label = t.month_label 
    AND dim.target_name = t.target_channel_name