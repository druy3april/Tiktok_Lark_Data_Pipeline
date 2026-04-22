import requests
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# --- CẤU HÌNH ---
import os
from dotenv import load_dotenv

load_dotenv()

HEADERS = {'Authorization': f"Bearer {os.getenv('LARK_API_TOKEN')}"}
URL_ACTUAL = "https://media-admin.genfarmer.com/get_data?table_id=tblqy8l657mdlv9H"
DB_CONN = os.getenv('SUPABASE_DB_URL')

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

def main():
    print("--- 🚀 ĐANG TRIỂN KHAI CHIẾN DỊCH CHỐT HẠ ---")
    df_raw = get_lark_data(URL_ACTUAL)
    
    if df_raw.empty:
        print("❌ API không trả về dữ liệu."); return

    # 1. TÌM CỘT THÔNG MINH
    def find_col(kws):
        return next((c for c in df_raw.columns if any(k in str(c) for k in kws)), None)

    c_nguon = find_col(['Nguồn khách'])
    c_tien = find_col(['Đã thu Tổng cộng', 'revenue'])
    c_box = find_col(['Số Box'])
    c_router = find_col(['Số Router'])
    c_ngay = find_col(['Ngày mua', 'log_date'])
    c_week = find_col(['Tuần ttrong tháng'])
    c_month = find_col(['Tháng'])

    # 2. LỌC DỮ LIỆU TIKTOK
    df_raw[c_nguon] = df_raw[c_nguon].fillna('')
    df_tk = df_raw[df_raw[c_nguon].str.contains('Tiktok', na=False, case=False)].copy()

    # 3. CHUẨN HÓA DATA FRAME (KHỚP 100% VỚI DATABASE)
    final = pd.DataFrame()
    
    final['channel_name'] = df_tk[c_nguon].astype(str)
    final['week_label'] = df_tk.get(c_week, '').fillna('').astype(str)
    
    # FIX THÁNG: Biến 'Tháng 4/2026' thành 'T4/2026' luôn
    final['month_label'] = df_tk.get(c_month, '').fillna('').astype(str).str.replace('Tháng ', 'T', regex=False)
    
    # FIX NGÀY: Chuyển ms sang YYYY-MM-DD
    final['log_date'] = pd.to_datetime(df_tk[c_ngay], unit='ms', errors='coerce').dt.date
    
    # FIX DOANH THU & SỐ LƯỢNG
    final['revenue'] = pd.to_numeric(df_tk.get(c_tien, 0), errors='coerce').fillna(0).astype(float)
    b = pd.to_numeric(df_tk.get(c_box, 0), errors='coerce').fillna(0)
    r = pd.to_numeric(df_tk.get(c_router, 0), errors='coerce').fillna(0)
    final['order_count'] = (b + r).astype(int)
    
    # QUAN TRỌNG: Thêm cột created_at để dbt dùng ROW_NUMBER
    final['created_at'] = datetime.now()

    # 4. ĐẨY LÊN SUPABASE
    try:
        engine = create_engine(DB_CONN)
        with engine.connect() as conn:
            print("🧹 Đang dọn dẹp bảng thô...")
            conn.execute(text("TRUNCATE TABLE business_performance"))
            conn.commit()

        print(f"📤 Đang nạp {len(final)} dòng 'sạch' vào bảng...")
        # Chèn dòng này vào trước khi to_sql
        final = final.drop_duplicates()
        final.to_sql('business_performance', engine, if_exists='append', index=False, method='multi')
        print("--- ✅ KẾT THÚC CÔNG VIỆC! DỮ LIỆU ĐÃ SẴN SÀNG ---")
        
    except Exception as e:
        print(f"❌ LỖI RỒI CHÚ ƠI: {str(e)}")

if __name__ == "__main__":
    main()