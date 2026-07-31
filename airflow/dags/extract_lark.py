import re
import requests
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

import sys
import os
from dotenv import load_dotenv

load_dotenv()

HEADERS = {'Authorization': f"Bearer {os.getenv('LARK_API_TOKEN')}"}
URL_OLD = "https://media-admin.genfarmer.com/get_data?table_id=tblqy8l657mdlv9H"
URL_NEW = "https://media-admin.genfarmer.com/get_data?table_id=tblD19qpIzx3X9wS&base_id=Xfz8bJ3mOa6mgwsOZ4Au29iWsff"
DB_CONN = os.getenv('SUPABASE_DB_URL')


# ─────────────────────────────────────────────────────────────
# BƯỚC 1: Kéo toàn bộ data từ Lark
#   → Giữ lại record_id (khóa duy nhất) để dedup chính xác
# ─────────────────────────────────────────────────────────────
def get_lark_data(url):
    print(f"📡 Đang gọi API Lark: {url[:60]}...")
    response = requests.get(url, headers=HEADERS, timeout=60)
    if response.status_code != 200:
        print(f"❌ Lỗi API status code: {response.status_code}")
        return pd.DataFrame()

    data = response.json()
    all_records = []
    seen_ids = set()

    # Kiểm tra nếu response có dạng dict và chứa 'sources'
    if isinstance(data, dict) and 'sources' in data:
        sources = data.get('sources')
        
        # Nếu sources là dict (ví dụ: {'global': [...], 'sg': [...], 'vung_moi': [...]})
        if isinstance(sources, dict):
            # Duyệt qua TẤT CẢ các key trong sources thay vì chỉ 'global' và 'sg'
            for key, items in sources.items():
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        fields = dict(item.get('fields', item))
                        rid = item.get('record_id') or item.get('id')
                        if rid is not None:
                            if rid in seen_ids:
                                continue
                            seen_ids.add(rid)
                            fields['_lark_record_id'] = rid
                        all_records.append(fields)

        # Nếu sources trực tiếp là một list
        elif isinstance(sources, list):
            for item in sources:
                if not isinstance(item, dict):
                    continue
                fields = dict(item.get('fields', item))
                rid = item.get('record_id') or item.get('id')
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

    Trả về đúng 1 trong: 'tiktok', 'instagram', 'unknown'.
    'unknown' = không có tag rõ ràng → sẽ bị loại khỏi báo cáo.
    """
    s = str(nguon or '').strip()
    
    # 1. Kiểm tra bằng RE_STRIP_TAG ở đầu chuỗi (bắt tốt các trường hợp dính chữ như IGLynette)
    m = RE_STRIP_TAG.match(s)
    if m:
        prefix = m.group(0).lower()
        if any(k in prefix for k in ['ig', 'insta', 'instagram', 'reel']):
            return 'instagram'
        if any(k in prefix for k in ['tt', 'tiktok', 'tik', 'douyin']):
            return 'tiktok'

    # 2. Fallback: tìm kiếm tag ở bất kỳ đâu trong chuỗi
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
    
    if not cleaned:
        cleaned = s
        
    # Map tên kênh (alias) để đồng nhất giữa bảng mới và cũ
    # Map tên kênh (alias) để đồng nhất giữa bảng mới và cũ
    alias_map = {
        "rick": "Quang Vũ",
        "linh": "N.D.K.Linh",
        "lynette": "Lynette",   # Bắt chuẩn tên từ bảng Mới (IG Lynette)
        "instgaram lynette": "Lynette" # Bắt luôn cả lỗi gõ sai chính tả "Instgaram" ở bảng Cũ
    }
    
    lower_cleaned = cleaned.lower()
    if lower_cleaned in alias_map:
        return alias_map[lower_cleaned]
        
    return cleaned


# ─────────────────────────────────────────────────────────────
# BƯỚC 3: Chuẩn hóa toàn bộ DataFrame thô (1 lần, có cột platform)
# ─────────────────────────────────────────────────────────────
def normalize_all(df_raw):
    if df_raw.empty:
        return pd.DataFrame()

    def get_coalesced_series(kws):
        kws_lower = [k.lower() for k in kws]
        matched_cols = [c for c in df_raw.columns if any(k in str(c).lower() for k in kws_lower)]
        if not matched_cols:
            return pd.Series(pd.NA, index=df_raw.index)
        
        s = df_raw[matched_cols[0]].copy()
        for col in matched_cols[1:]:
            mask = s.isna() | (s == '')
            s.loc[mask] = df_raw[col].loc[mask]
        return s

    s_nguon  = get_coalesced_series(['nguồn khách', 'nguon khach', 'channel'])
    s_tien   = get_coalesced_series(['tổng tiền bán', 'revenue', 'số tiền'])
    s_box    = get_coalesced_series(['số box', 'so box'])
    s_router = get_coalesced_series(['số router', 'so router'])
    s_ngay   = get_coalesced_series(['ngày mua', 'log_date', 'ngày thanh toán'])
    s_week   = get_coalesced_series(['tuần'])
    s_month  = get_coalesced_series(['tháng', 'month'])
    s_ma_don = get_coalesced_series(['mã đơn hàng', 'bill id'])

    if s_nguon.isna().all() or (s_nguon == '').all():
        print("⚠️  Không tìm thấy dữ liệu 'Nguồn khách' trong data Lark.")
        return pd.DataFrame()

    s_nguon = s_nguon.fillna('').astype(str)

    final = pd.DataFrame()
    final['lark_record_id'] = df_raw.get('_lark_record_id', pd.Series(dtype=str))
    final['channel_raw']    = s_nguon                          # nguồn gốc (soi lỗi)
    final['channel_name']   = s_nguon.apply(clean_channel_name) # tên kênh sạch (bỏ tag)
    final['platform']       = s_nguon.apply(classify_platform)
    final['order_code']     = s_ma_don.fillna('').astype(str).str.strip()
    
    # --- FALLBACK PLATFORM ---
    # Nếu kênh không có tag nền tảng (bị phân loại là 'unknown')
    # nhưng chúng ta biết chắc chắn kênh đó thuộc nền tảng nào
    known_platform_map = {
        'lynette': 'instagram',
        # Có thể thêm các kênh khác vào đây nếu cần (tên viết thường)
    }
    mask_unknown = final['platform'] == 'unknown'
    if mask_unknown.any():
        fallback_platforms = final.loc[mask_unknown, 'channel_name'].str.lower().map(known_platform_map)
        final.loc[mask_unknown, 'platform'] = fallback_platforms.fillna('unknown')

    final['week_label']     = s_week.fillna('').astype(str)
    final['month_label']    = (
        s_month
        .fillna('').astype(str)
        .str.replace('Tháng ', 'T', regex=False)
    )
    # ── log_date lấy từ cột "Ngày mua" ──
    # Lark có thể trả 2 kiểu: (a) epoch mili-giây (số), hoặc (b) chuỗi ngày "dd/mm/yyyy".
    # Parse LINH HOẠT: số lớn → epoch ms; còn lại → ngày dạng chữ (dayfirst, giờ VN).
    def _parse_ngay_mua(series):
        raw = series.copy()
        num = pd.to_numeric(raw, errors='coerce')
        # Ngưỡng epoch ms hợp lệ (> 1_000_000_000_000). Epoch giây hợp lệ (> 1_000_000_000)
        is_epoch = num.notna() & (num > 1_000_000_000)
        is_ms = is_epoch & (num > 1_000_000_000_000)
        is_s = is_epoch & ~is_ms

        out = pd.Series(pd.NaT, index=raw.index, dtype='datetime64[ns, UTC]')
        # (a) epoch ms
        if is_ms.any():
            out.loc[is_ms] = pd.to_datetime(num[is_ms], unit='ms', errors='coerce', utc=True)
        # (a2) epoch s
        if is_s.any():
            out.loc[is_s] = pd.to_datetime(num[is_s], unit='s', errors='coerce', utc=True)
            
        # (b) chuỗi ngày "dd/mm/yyyy" (và các định dạng ngày thường), ưu tiên ngày trước
        mask_str = ~is_epoch
        if mask_str.any():
            svals = raw[mask_str].astype(str).str.strip()
            # ISO yyyy-mm-dd: để pandas tự nhận (không dayfirst)
            iso = svals.str.match(r'^\d{4}-\d{2}-\d{2}')
            parsed = pd.Series(pd.NaT, index=svals.index, dtype='datetime64[ns, UTC]')
            if iso.any():
                parsed.loc[iso] = pd.to_datetime(svals[iso], errors='coerce', utc=True)
            # Còn lại (dd/mm/yyyy...) → dayfirst
            if (~iso).any():
                parsed.loc[~iso] = pd.to_datetime(
                    svals[~iso], errors='coerce', dayfirst=True, utc=True
                )
            out.loc[mask_str] = parsed
        return out

    final['log_date'] = (
        _parse_ngay_mua(s_ngay)
        .dt.tz_convert('Asia/Ho_Chi_Minh')
        .dt.date
    )
    final['revenue'] = (
        pd.to_numeric(s_tien, errors='coerce')
        .fillna(0).astype(float)
    )

    # Số THIẾT BỊ (box + router) — giữ riêng, KHÔNG dùng làm số đơn
    b = pd.to_numeric(s_box,    errors='coerce').fillna(0)
    r = pd.to_numeric(s_router, errors='coerce').fillna(0)
    final['device_count'] = (b + r).astype(int)

    # Số ĐƠN = mỗi dòng trong Lark là 1 đơn hàng → đếm bằng 1
    final['order_count'] = 1

    final['created_at'] = datetime.now()

n_before = len(final)

    # ── DEDUP nhiều lớp (chống nhân đôi do region global/sg trùng hoặc trùng 2 bảng) ──
    # Lớp 0: Lọc trùng theo Mã đơn hàng (Loại bỏ triệt để đơn copy qua lại giữa 2 bảng)
    has_order_code = final['order_code'] != ''
    if has_order_code.any():
        final = final.drop_duplicates(subset=['order_code'], keep='last')

    # Lớp 1: theo record_id của Lark (nếu có giá trị)
    has_rid = final['lark_record_id'].notna() & (final['lark_record_id'].astype(str).str.len() > 0)
    if has_rid.any():
        with_id    = final[has_rid].drop_duplicates(subset=['lark_record_id'])
        # KHÔNG dedup mù quáng trên without_id chỉ với vài cột, dễ làm mất đơn trùng hợp (cùng ngày, kênh, tiền)
        without_id = final[~has_rid].drop_duplicates()
        final = pd.concat([with_id, without_id], ignore_index=True)
    else:
        # Không có record_id → dedup theo toàn bộ dòng để tránh mất đơn hợp lệ
        final = final.drop_duplicates()

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

    print("📥 Lấy dữ liệu bảng cũ...")
    df_raw_old = get_lark_data(URL_OLD)
    
    print("📥 Lấy dữ liệu bảng mới...")
    df_raw_new = get_lark_data(URL_NEW)
    print(f"👉 [DEBUG] Bảng mới lấy được {len(df_raw_new)} dòng dữ liệu từ API.")
    
    # Đổi tên cột cho bảng mới để khớp với logic hiện tại
    if not df_raw_new.empty:
        print(f"👉 [DEBUG] Tên các cột của bảng mới: {list(df_raw_new.columns)}")
        df_raw_new = df_raw_new.rename(columns={
            "Số tiền": "Tổng tiền bán",
            "Tuần": "Tuần ttrong tháng",
            "Ngày thanh toán": "Ngày mua"
        })
        
    dfs = []
    if not df_raw_old.empty: dfs.append(df_raw_old)
    if not df_raw_new.empty: dfs.append(df_raw_new)

    if not dfs:
        print("❌ API không trả về dữ liệu."); return
        sys.exit(1)

    df_raw = pd.concat(dfs, ignore_index=True)
    print(f"✅ Lark trả về {len(df_raw)} dòng tổng cộng.")
    print(f"👉 [DEBUG] Bảng cũ góp {len(df_raw_old)} dòng, bảng mới góp {len(df_raw_new)} dòng.")

    df_all = normalize_all(df_raw)
    if df_all.empty:
        print("❌ Không chuẩn hóa được dữ liệu."); return
        sys.exit(1)

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
