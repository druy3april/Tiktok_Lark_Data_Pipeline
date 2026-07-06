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
# BƯỚC 2: Tách TAG NỀN TẢNG khỏi "Nguồn khách"
#   Quy ước Lark: mỗi nguồn ghi dạng "<Platform> <Tên kênh>"
#       vd "Tiktok Cảnh", "Instagram Cảnh", "Tiktok Litch".
#   → Chữ ĐẦU là platform, phần còn lại là tên kênh sạch.
#   → Dòng KHÔNG có tag tiktok/ig → 'Unknown' → BỊ LOẠI khỏi báo cáo.
# ─────────────────────────────────────────────────────────────
# Token nền tảng, có ranh giới từ (\b) để không bắt nhầm chữ lẫn bên trong.
RE_TIKTOK = re.compile(
    r'\btiktok\b|\btik[\s\-_.]?tok\b|\btt\b|\bdouyin\b',
    re.IGNORECASE
)
RE_INSTAGRAM = re.compile(
    r'\binstagram\b|\binsta\b|\big\b|\breels?\b',
    re.IGNORECASE
)

# Pattern để CẮT tag platform ra khỏi đầu chuỗi (lấy phần tên kênh).
RE_STRIP_TAG = re.compile(
    r'^\s*(?:tiktok|tik[\s\-_.]?tok|tt|douyin|instagram|insta|ig|reels?)'
    r'[\s\-_.:|]*',
    re.IGNORECASE
)


def classify_platform(nguon: str) -> str:
    """Phân loại nền tảng theo TAG trong nguồn khách.

    Trả về đúng 1 trong: 'Tiktok', 'Instagram', 'Unknown'.
    'Unknown' = không có tag rõ ràng → sẽ bị loại khỏi báo cáo.
    """
    s = str(nguon or '')
    is_tt = bool(RE_TIKTOK.search(s))
    is_ig = bool(RE_INSTAGRAM.search(s))

    # Khớp cả hai → ưu tiên tag XUẤT HIỆN TRƯỚC (thường là chữ đầu)
    if is_tt and is_ig:
        pos_tt = RE_TIKTOK.search(s).start()
        pos_ig = RE_INSTAGRAM.search(s).start()
        return 'tiktok' if pos_tt <= pos_ig else 'instagram'
    if is_tt:
        return 'tiktok'
    if is_ig:
        return 'instagram'
    return 'unknown'   # không có tag → loại khỏi báo cáo ở bước split


def clean_channel_name(nguon: str) -> str:
    """Bỏ tag platform ở đầu, trả về TÊN KÊNH sạch.

    'Tiktok Cảnh'    -> 'Cảnh'
    'Instagram Cảnh' -> 'Cảnh'
    'Tiktok Litch'   -> 'Litch'
    Nếu sau khi bỏ tag mà rỗng → giữ nguyên chuỗi gốc để soi tay.
    """
    s = str(nguon or '').strip()
    cleaned = RE_STRIP_TAG.sub('', s).strip()
    return cleaned if cleaned else s


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
    final['channel_raw']    = df_raw[c_nguon]                          # nguồn gốc (soi lỗi)
    final['channel_name']   = df_raw[c_nguon].apply(clean_channel_name) # tên kênh sạch (bỏ tag)
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
            subset=['platform', 'channel_name', 'log_date', 'revenue', 'device_count']
        )
        final = pd.concat([with_id, without_id], ignore_index=True)
    else:
        # Không có record_id → dedup theo tổ hợp khóa nghiệp vụ
        final = final.drop_duplicates(
            subset=['platform', 'channel_name', 'log_date', 'revenue', 'device_count']
        )

    # Báo cáo dòng bất thường để soi tay
    print(f"   🔁 Dedup: {n_before} → {len(final)} dòng (loại {n_before - len(final)} trùng).")
    # Báo cáo phân bố platform để soi tay
    dist = final['platform'].value_counts().to_dict()
    print(f"   📊 Phân bố nền tảng: {dist}")
    n_unknown = (final['platform'] == 'unknown').sum()
    if n_unknown:
        mau = final.loc[final['platform'] == 'unknown', 'channel_raw'].unique()[:10]
        print(f"   🗑  {n_unknown} dòng KHÔNG có tag tiktok/ig → SẼ BỊ LOẠI khỏi báo cáo.")
        print(f"      Ví dụ nguồn bị loại: {list(mau)}")

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
            EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS channel_raw    TEXT', t);
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

    # LOẠI dòng không rõ nền tảng khỏi báo cáo (theo yêu cầu).
    n_all = len(df_all)
    df_known = df_all[df_all['platform'].isin(['tiktok', 'instagram'])].copy()
    n_dropped = n_all - len(df_known)
    if n_dropped:
        print(f"\n🗑  Đã loại {n_dropped} dòng 'unknown' khỏi báo cáo.")

    # Tách chặt theo nền tảng — mỗi bảng chỉ chứa đúng platform của nó.
    df_tiktok    = df_known[df_known['platform'] == 'tiktok'].copy()
    df_instagram = df_known[df_known['platform'] == 'instagram'].copy()

    # Bất biến: không mất, không đếm 2 lần trong phần đã-biết-nền-tảng
    assert len(df_tiktok) + len(df_instagram) == len(df_known), (
        f"Mất/nhân đôi dòng khi tách: tiktok={len(df_tiktok)} + "
        f"insta={len(df_instagram)} != known={len(df_known)}"
    )

    print(f"\n[1/2] TikTok:    {len(df_tiktok)} dòng")
    print(f"[2/2] Instagram: {len(df_instagram)} dòng")
    print(f"   Σ revenue TikTok:    {df_tiktok['revenue'].sum():,.0f}")
    print(f"   Σ revenue Instagram: {df_instagram['revenue'].sum():,.0f}")
    print(f"   Σ revenue (đã lọc):  {df_known['revenue'].sum():,.0f} "
          f"(= TikTok + Instagram, KHÔNG gồm Unknown)")

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
