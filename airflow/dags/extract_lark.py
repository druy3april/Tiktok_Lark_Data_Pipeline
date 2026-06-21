import requests
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

import os
from dotenv import load_dotenv

load_dotenv()

HEADERS = {'Authorization': f"Bearer {os.getenv('LARK_API_TOKEN')}"}
URL_ACTUAL = "https://media-admin.genfarmer.com/get_data?table_id=tblqy8l657mdlv9H"
DB_CONN = os.getenv('SUPABASE_DB_URL')


# ─────────────────────────────────────────────────────────────
# BƯỚC 1: Kéo toàn bộ data từ Lark (giữ nguyên, không đổi)
# ─────────────────────────────────────────────────────────────
def get_lark_data(url):
    print(f"📡 Đang gọi API Lark...")
    response = requests.get(url, headers=HEADERS, timeout=60)
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, dict) and 'sources' in data:
            all_records = []
            sources = data['sources']
            for region in ['global', 'sg']:
                if region in sources and isinstance(sources[region], list):
                    for item in sources[region]:
                        all_records.append(item.get('fields', item))
            return pd.DataFrame(all_records)
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# BƯỚC 2: Chuẩn hóa một DataFrame thô thành format chuẩn DB
#         Dùng chung cho cả TikTok lẫn Instagram
# ─────────────────────────────────────────────────────────────
def normalize_df(df_raw, platform_tag):
    """
    platform_tag: 'Tiktok' hoặc 'Instagram' — dùng để lọc cột Nguồn khách
    """
    if df_raw.empty:
        return pd.DataFrame()

    def find_col(kws):
        return next((c for c in df_raw.columns if any(k in str(c) for k in kws)), None)

    c_nguon  = find_col(['Nguồn khách'])
    c_tien   = find_col(['Đã thu Tổng cộng', 'revenue'])
    c_box    = find_col(['Số Box'])
    c_router = find_col(['Số Router'])
    c_ngay   = find_col(['Ngày mua', 'log_date'])
    c_week   = find_col(['Tuần ttrong tháng'])
    c_month  = find_col(['Tháng'])

    if not c_nguon:
        print(f"⚠️  Không tìm thấy cột 'Nguồn khách' trong data Lark.")
        return pd.DataFrame()

    # Lọc theo tag platform (Tiktok / Instagram)
    df_raw[c_nguon] = df_raw[c_nguon].fillna('')
    df_filtered = df_raw[
        df_raw[c_nguon].str.contains(platform_tag, na=False, case=False)
    ].copy()

    if df_filtered.empty:
        print(f"⚠️  Không có dòng nào với tag '{platform_tag}' trong Lark.")
        return pd.DataFrame()

    final = pd.DataFrame()
    final['channel_name'] = df_filtered[c_nguon].astype(str)
    final['week_label']   = df_filtered.get(c_week, pd.Series(dtype=str)).fillna('').astype(str)
    final['month_label']  = (
        df_filtered.get(c_month, pd.Series(dtype=str))
        .fillna('').astype(str)
        .str.replace('Tháng ', 'T', regex=False)
    )
    final['log_date'] = (
        pd.to_datetime(df_filtered[c_ngay], unit='ms', errors='coerce', utc=True)
        .dt.tz_convert('Asia/Ho_Chi_Minh')
        .dt.date
    )
    final['revenue'] = (
        pd.to_numeric(df_filtered.get(c_tien, 0), errors='coerce')
        .fillna(0).astype(float)
    )
    b = pd.to_numeric(df_filtered.get(c_box, 0),    errors='coerce').fillna(0)
    r = pd.to_numeric(df_filtered.get(c_router, 0), errors='coerce').fillna(0)
    final['order_count'] = (b + r).astype(int)
    final['created_at']  = datetime.now()

    return final.drop_duplicates()


# ─────────────────────────────────────────────────────────────
# BƯỚC 3: Load vào một bảng Supabase
# ─────────────────────────────────────────────────────────────
def load_to_db(engine, df, table_name):
    if df.empty:
        print(f"   ⏭  Bỏ qua '{table_name}' — không có dữ liệu.")
        return

    with engine.connect() as conn:
        print(f"   🧹 TRUNCATE {table_name}...")
        conn.execute(text(f"TRUNCATE TABLE {table_name}"))
        conn.commit()

    print(f"   📤 Nạp {len(df)} dòng vào '{table_name}'...")
    df.to_sql(table_name, engine, if_exists='append', index=False, method='multi')
    print(f"   ✅ '{table_name}' hoàn tất.")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    print("--- 🚀 ĐANG TRIỂN KHAI CHIẾN DỊCH CHỐT HẠ ---")

    df_raw = get_lark_data(URL_ACTUAL)
    if df_raw.empty:
        print("❌ API không trả về dữ liệu."); return

    print(f"✅ Lark trả về {len(df_raw)} dòng tổng cộng.")

    # ── TikTok (giữ nguyên như cũ) ──────────────────────────
    print("\n[1/2] Xử lý dữ liệu TIKTOK...")
    df_tiktok = normalize_df(df_raw, platform_tag='Tiktok')
    print(f"      → {len(df_tiktok)} dòng TikTok")

    # ── Instagram (mới) ─────────────────────────────────────
    print("\n[2/2] Xử lý dữ liệu INSTAGRAM...")
    df_instagram = normalize_df(df_raw, platform_tag='Instagram')
    print(f"      → {len(df_instagram)} dòng Instagram")

    # ── Đẩy lên Supabase ────────────────────────────────────
    try:
        engine = create_engine(DB_CONN)
        print("\n📦 Đang nạp vào Supabase...")
        load_to_db(engine, df_tiktok,   'business_performance')
        load_to_db(engine, df_instagram, 'instagram_performance')
        print("\n--- ✅ KẾT THÚC CÔNG VIỆC! DỮ LIỆU ĐÃ SẴN SÀNG ---")
    except Exception as e:
        print(f"❌ LỖI RỒI CHÚ ƠI: {str(e)}")


if __name__ == "__main__":
    main()
