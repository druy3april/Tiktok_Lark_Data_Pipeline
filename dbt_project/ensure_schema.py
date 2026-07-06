"""
Đảm bảo schema Supabase trước khi dbt chạy.
- Tạo bảng instagram_performance (nếu chưa có), clone cấu trúc từ business_performance.
- Thêm các cột mới (platform, device_count, order_count, lark_record_id,
  week_label, month_label) cho cả 2 bảng. Idempotent — chạy lại không lỗi.
Chạy độc lập trong CI, dùng cùng biến SUPABASE_DB_URL như extract_lark.py.
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_CONN = os.getenv('SUPABASE_DB_URL')

DDL = """
CREATE TABLE IF NOT EXISTS public.instagram_performance
    (LIKE public.business_performance INCLUDING ALL);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['business_performance','instagram_performance'] LOOP
        EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS platform       TEXT', t);
        EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS device_count   INTEGER DEFAULT 0', t);
        EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS order_count    INTEGER DEFAULT 1', t);
        EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS lark_record_id TEXT', t);
        EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS week_label     TEXT', t);
        EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS month_label    TEXT', t);
    END LOOP;
END $$;
"""


def main():
    if not DB_CONN:
        print("❌ Thiếu SUPABASE_DB_URL"); return
    engine = create_engine(DB_CONN)
    with engine.connect() as conn:
        print("🛠  Đảm bảo schema (tạo bảng IG + thêm cột mới)...")
        conn.execute(text(DDL))
        conn.commit()
    print("✅ Schema sẵn sàng.")


if __name__ == "__main__":
    main()
