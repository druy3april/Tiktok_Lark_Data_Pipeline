from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime
from airflow.operators.bash import BashOperator

with DAG(
    dag_id='lark_to_supabase_flow', 
    start_date=datetime(2026, 4, 1),
    # 0: Phút thứ 0
    # 8,14,20: Các giờ chạy (8h, 14h, 20h)
    schedule='0 8,14,20 * * *', 
    catchup=False
) as dag:

    # TASK 1: Chạy file Python để bốc data từ Lark về Supabase
    extract_task = BashOperator(
        task_id='extract_and_load_lark',
        # Đường dẫn bên trong Docker luôn bắt đầu bằng /opt/airflow/dags/
        bash_command='python /opt/airflow/dags/extract_lark.py'
    )

    # TASK 2: Chạy dbt để biến đổi và khớp Target
    transform_task = BashOperator(
        task_id='dbt_transform',
        # Chú nhớ kiểm tra folder dbt_project có đúng nằm ở /opt/airflow/ không nhé
        bash_command='cd /opt/airflow/dbt_project && dbt clean && dbt run --profiles-dir .',
    )

    # Thứ tự: Kéo xong mới Biến đổi
    extract_task >> transform_task