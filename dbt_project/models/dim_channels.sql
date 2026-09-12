{{ config(materialized='table') }}

WITH raw_sales AS (
    SELECT DISTINCT channel_name as sales_name
    FROM {{ source('lark_raw', 'business_performance') }}
)

SELECT
    MD5(sales_name) as channel_key,
    sales_name as display_name,
    
    CASE 
        WHEN sales_name ILIKE '%Cảnh%' THEN 'johnny.techguide'
        WHEN sales_name ILIKE '%Huy%'   THEN 'holden_genfarmer'
        WHEN sales_name ILIKE '%Jocelyn%' THEN 'jocelyn.genboxphone'
        WHEN sales_name ILIKE '%Litch%'   THEN 'licht_do1112' 
        WHEN sales_name ILIKE 'Tiktok %t' AND sales_name NOT LIKE '%Huy%' THEN 'pdat.genfarmer'
        WHEN sales_name ILIKE '%Thiên%' THEN 'vt.zerotrace'
        ELSE sales_name 
    END as target_name,

    CASE 
        WHEN sales_name ILIKE '%Cảnh%' THEN '@johnny.techguide'
        WHEN sales_name ILIKE '%Huy%'   THEN '@holden_genfarmer'
        WHEN sales_name ILIKE '%Jocelyn%' THEN '@jocelyn.genboxphone'
        WHEN sales_name ILIKE '%Litch%'   THEN '@licht_do1112'
        WHEN sales_name ILIKE 'Tiktok %t' AND sales_name NOT LIKE '%Huy%' THEN '@pdat.genfarmer'
        WHEN sales_name ILIKE '%Thiên%' THEN '@vt.zerotrace'
        ELSE sales_name 
    END as tiktok_stats_name

    CASE 
        -- Các kênh đã được map chuẩn hóa:
        WHEN sales_name ILIKE '%Cảnh%' THEN 'https://xaxqebblrstsaazrqowb.supabase.co/storage/v1/object/public/avatars/20260909-153623.webp'
        WHEN sales_name ILIKE '%Huy%'   THEN 'https://xaxqebblrstsaazrqowb.supabase.co/storage/v1/object/public/avatars/20260909-153604.webp'
        WHEN sales_name ILIKE '%Jocelyn%' THEN 'https://xaxqebblrstsaazrqowb.supabase.co/storage/v1/object/public/avatars/20260909-153523.webp'
        WHEN sales_name ILIKE 'Tiktok %t' AND sales_name NOT LIKE '%Huy%' THEN 'URL_ẢNH_CỦA_ĐẠT_GENFARMER'
        WHEN sales_name ILIKE '%Thiên%' THEN 'https://xaxqebblrstsaazrqowb.supabase.co/storage/v1/object/public/avatars/20260909-153556.webp'
        
        -- Các kênh Insta và kênh lẻ khác đang có trong Supabase:
        WHEN sales_name ILIKE '%N.D.K.L%' THEN 'https://xaxqebblrstsaazrqowb.supabase.co/storage/v1/object/public/avatars/20260909-153523.webp'
        WHEN sales_name ILIKE '%Quang Vũ%' THEN 'https://xaxqebblrstsaazrqowb.supabase.co/storage/v1/object/public/avatars/20260909-153709.webp'
        WHEN sales_name ILIKE '%Lynette%' THEN 'https://xaxqebblrstsaazrqowb.supabase.co/storage/v1/object/public/avatars/20260909-153652.webp'
        WHEN sales_name ILIKE '%genboxphone%' THEN 'https://xaxqebblrstsaazrqowb.supabase.co/storage/v1/object/public/avatars/20260909-153652.webp'
        WHEN sales_name ILIKE '%Việt%' THEN 'https://xaxqebblrstsaazrqowb.supabase.co/storage/v1/object/public/avatars/20260909-153612.webp'
        ELSE NULL 
    END as avatar_url

FROM raw_sales
