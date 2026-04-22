import requests
import pandas as pd
from sqlalchemy import create_engine

# 1. THÔNG TIN CẤU HÌNH
import os
from dotenv import load_dotenv

load_dotenv()

HEADERS = {'Authorization': f"Bearer {os.getenv('LARK_API_TOKEN')}"}
URL_TARGET = 'https://media-admin.genfarmer.com/get_data?table_id=tbl8mKnHM4G8CTkv'
DB_CONN = os.getenv('SUPABASE_DB_URL')

def load_target_final():
    print("🎯 Bắt đầu quy trình nạp Target...")
    
    response = requests.get(URL_TARGET, headers=HEADERS)
    if response.status_code != 200:
        print("❌ Lỗi API Lark"); return
    
    data = response.json()
    sources = data.get('sources', {})
    all_rows = []

    # 2. PHÁ KÉN (Xử lý đa vùng global/sg để không bị lặp)
    for region in sources:
        for item in sources[region]:
            all_rows.append(item.get('fields', item))
    
    df = pd.DataFrame(all_rows)
    
    # --- CÚ CHỐT: LỌC TRÙNG TUYỆT ĐỐI ---
    df = df.drop_duplicates()
    
    print(f"📊 Đã lọc sạch rác, còn lại {len(df)} dòng chỉ tiêu.")

    # 3. ĐẨY LÊN SUPABASE
    try:
        engine = create_engine(DB_CONN)
        # Sếp dùng 'replace' để nó tự tạo bảng mới sạch sẽ
        df.to_sql('stg_lark_target', engine, if_exists='replace', index=False)
        print("✅ THÀNH CÔNG! Bảng 'stg_lark_target' đã sẵn sàng.")
        print(df.head(3)) # Xem thử 3 dòng đầu
    except Exception as e:
        print(f"❌ Lỗi nạp Database: {e}")

if __name__ == "__main__":
    load_target_final()