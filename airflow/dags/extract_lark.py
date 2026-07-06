import re
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
# BƯỚC 1: Kéo toàn bộ data từ Lark
#   → Giữ lại record_id (khóa duy nhất) để dedup chính xác
# ─────────────────────────────────────────────────────────────
def get_lark_data(url):
    print("📡 Đang gọi API Lark...")
    response = requests.get(url, headers=HEADERS, timeout=60)
    if response.status_code != 200:
        return pd.DataFrame()

    data = response.json()
    if not (isinstance(data, dict) and 'sources' in data):
        return pd.DataFrame()

    all_records = []
    seen_ids = set()
    sources = data['sources']
    for region in ['global', 'sg']:
        if region in sources and isinstance(sources[region], list):
            for item in sources[region]:
                fields = dict(item.get('fields', item))
                rid = item.get('record_id') or item.get('id')
                # Dedup NGAY tại nguồn: cùng record_id ở global lẫn sg chỉ lấy 1 lần
                if rid is not None:
                    if rid in seen_ids:
                        continue
                    seen_ids.add(rid)
                fields['_lark_record_id'] = rid
                all_records.append(fields)
    return pd.DataFrame(all_records)


# ─────────────────────────────────────────────────────────────
# BƯỚC 2: Gán platform ĐỘC QUYỀN cho từng dòng
#   Mỗi dòng chỉ thuộc đúng 1 platform. Không dùng contains
#   trùng lặp khiến 1 dòng lọt vào cả 2 bảng.
# ─────────────────────────────────────────────────────────────
# Từ khóa nhận diện TikTok. Chỉ dùng token TƯỜNG MINH, có ranh giới từ (\b)
#   để tránh bắt nhầm "tt"/"ig" nằm lẫn trong chữ khác.
#   'tt' chỉ khớp khi đứng độc lập (vd "tt huy"), KHÔNG khớp "attitude".
RE_TIKTOK = re.compile(
    r'\btiktok\b|\btik[\s\-_.]?tok\b|\btt\b|\bdouyin\b',
    re.IGNORECASE
)
# Từ khóa Instagram. 'ig'/'insta' chỉ khớp khi là token độc lập.
RE_INSTAGRAM = re.compile(
    r'\binstagram\b|\binsta\b|\big\b|\breels?\b',
    re.IGNORECASE
)

# Platform mặc định cho các dòng KHÔNG match được keyword nào.
#   Đổi thành 'Instagram' nếu nguồn mặc định của team là IG.
#   Đặt None nếu muốn để riêng nhóm 'Unknown' (không gộp vào nền tảng nào).
DEFAULT_PLATFORM = 'Tiktok'


def classify_platform(nguon: str) -> str:
    """Phân loại nền tảng ĐỘC QUYỀN cho mỗi dòng.

    Trả về đúng 1 trong: 'Tiktok', 'Instagram', 'Unknown'.
    KHÔNG bao giờ trả 'AMBIGUOUS'/'' để tránh làm mất doanh thu.
    """
    s = str(nguon or '')
    is_tt = bool(RE_TIKTOK.search(s))
    is_ig = bool(RE_INSTAGRAM.search(s))

    # Khớp cả hai → ưu tiên token XUẤT HIỆN TRƯỚC trong chuỗi nguồn
    if is_tt and is_ig:
        pos_tt = RE_TIKTOK.search(s).start()
        pos_ig = RE_INSTAGRAM.search(s).start()
        return 'Tiktok' if pos_tt <= pos_ig else 'Instagram'
    if is_tt:
        return 'Tiktok'
    if is_ig:
        return 'Instagram'
    # Không khớp gì → gán mặc định (vẫn được nạp, không bị rớt khỏi 2 bảng)
    return DEFAULT_PLATFORM if DEFAULT_PLATFORM else 'Unknown'


# ─────────────────────────────────────────────────────────────
# BƯỚC 3: Chuẩn hóa toàn bộ DataFrame thô (1 lần, có cột platform)
# ─────────────────────────────────────────────────────────────
def normalize_all(df_raw):
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
        print("⚠️  Không tìm thấy cột 'Nguồn khách' trong data Lark.")
        return pd.DataFrame()

    df_raw[c_nguon] = df_raw[c_nguon].fillna('').astype(str)

    final = pd.DataFrame()
    final['lark_record_id'] = df_raw.get('_lark_record_id', pd.Series(dtype=str))
    final['channel_name']   = df_raw[c_nguon]
    final['platform']       = df_raw[c_nguon].apply(classify_platform)
    final['week_label']     = df_raw.get(c_week, pd.Series(dtype=str)).fillna('').astype(str)
    final['month_label']    = (
        df_raw.get(c_month, pd.Series(dtype=str))
        .fillna('').astype(str)
        .str.replace('Tháng ', 'T', regex=False)
    )
    final['log_date'] = (
        pd.to_datetime(df_raw[c_ngay], unit='ms', errors='coerce', utc=True)
        .dt.tz_convert('Asia/Ho_Chi_Minh')
        .dt.date
    )
    final['revenue'] = (
        pd.to_numeric(df_raw.get(c_tien, 0), errors='coerce')
        .fillna(0).astype(float)
    )

    # Số THIẾT BỊ (box + router) — giữ riêng, KHÔNG dùng làm số đơn
    b = pd.to_numeric(df_raw.get(c_box, 0),    errors='coerce').fillna(0)
    r = pd.to_numeric(df_raw.get(c_router, 0), errors='coerce').fillna(0)
    final['device_count'] = (b + r).astype(int)

    # Số ĐƠN = mỗi dòng trong Lark là 1 đơn hàng → đếm bằng 1
    final['order_count'] = 1

    final['created_at'] = datetime.now()

    n_before = len(final)
    # ── DEDUP nhiều lớp (chống nhân đôi do region global/sg trùng) ──
    # Lớp 1: theo record_id của Lark (nếu có giá trị)
    has_rid = final['lark_record_id'].notna() & (final['lark_record_id'].astype(str).str.len() > 0)
    if has_rid.any():
        with_id    = final[has_rid].drop_duplicates(subset=['lark_record_id'])
        without_id = final[~has_rid].drop_duplicates(
            subset=['channel_name', 'log_date', 'revenue', 'device_count']
        )
        final = pd.concat([with_id, without_id], ignore_index=True)
    else:
        # Không có record_id → dedup theo tổ hợp khóa nghiệp vụ
        final = final.drop_duplicates(
            subset=['channel_name', 'log_date', 'revenue', 'device_count']
        )

    # Báo cáo dòng bất thường để soi tay
    print(f"   🔁 Dedup: {n_before} → {len(final)} dòng (loại {n_before - len(final)} trùng).")
    # Báo cáo phân bố platform để soi tay
    dist = final['platform'].value_counts().to_dict()
    print(f"   📊 Phân bố nền tảng: {dist}")
    n_unknown = (final['platform'] == 'Unknown').sum()
    if n_unknown:
        print(f"   ⚠️  {n_unknown} dòng KHÔNG nhận diện được nền tảng "
              f"(đang để nhóm 'Unknown', cần bổ sung keyword/alias).")

    return final


# ─────────────────────────────────────────────────────────────
# BƯỚC 3.5: Đảm bảo schema — tạo bảng instagram + thêm cột mới
#   Idempotent: chạy lại nhiều lần không lỗi.
# ─────────────────────────────────────────────────────────────
def ensure_schema(engine):
    ddl = """
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
    with engine.connect() as conn:
        print("   🛠  Đảm bảo schema (tạo bảng IG + thêm cột mới)...")
        conn.execute(text(ddl))
        conn.commit()
    print("   ✅ Schema sẵn sàng.")


# ─────────────────────────────────────────────────────────────
# BƯỚC 4: Load vào một bảng Supabase
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

    df_all = normalize_all(df_raw)
    if df_all.empty:
        print("❌ Không chuẩn hóa được dữ liệu."); return

    # Tách theo nền tảng. Dòng 'Unknown' (nếu có) GỘP vào bảng TikTok
    #   để không mất doanh thu — thay vì bị loại khỏi cả hai bảng như trước.
    df_tiktok    = df_all[df_all['platform'].isin(['Tiktok', 'Unknown'])].copy()
    df_instagram = df_all[df_all['platform'] == 'Instagram'].copy()

    # Kiểm tra bất biến: KHÔNG dòng nào bị mất, KHÔNG dòng nào bị đếm 2 lần
    assert len(df_tiktok) + len(df_instagram) == len(df_all), (
        f"Mất/nhân đôi dòng khi tách: tiktok={len(df_tiktok)} + "
        f"insta={len(df_instagram)} != tổng={len(df_all)}"
    )

    print(f"\n[1/2] TikTok:    {len(df_tiktok)} dòng")
    print(f"[2/2] Instagram: {len(df_instagram)} dòng")
    print(f"   Σ revenue TikTok:    {df_tiktok['revenue'].sum():,.0f}")
    print(f"   Σ revenue Instagram: {df_instagram['revenue'].sum():,.0f}")
    print(f"   Σ revenue TỔNG:      {df_all['revenue'].sum():,.0f} "
          f"(phải = TikTok + Instagram)")

    try:
        engine = create_engine(DB_CONN)
        print("\n📦 Đang nạp vào Supabase...")
        ensure_schema(engine)
        load_to_db(engine, df_tiktok,    'business_performance')
        load_to_db(engine, df_instagram, 'instagram_performance')
        print("\n--- ✅ KẾT THÚC CÔNG VIỆC! DỮ LIỆU ĐÃ SẴN SÀNG ---")
    except Exception as e:
        print(f"❌ LỖI RỒI CHÚ ƠI: {str(e)}")


if __name__ == "__main__":
    main()
