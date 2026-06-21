from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

with DAG(
    dag_id='lark_to_supabase_flow',
    start_date=datetime(2026, 4, 1),
    schedule='0 8,14,20 * * *',
    catchup=False
) as dag:

    # TASK 1: Kéo cả TikTok lẫn Instagram từ Lark về Supabase
    extract_task = BashOperator(
        task_id='extract_and_load_lark',
        bash_command='python /opt/airflow/dags/extract_lark.py'
    )

    # TASK 2: dbt transform (stg_biz_data giờ UNION cả 2 nguồn, không cần đổi gì)
    transform_task = BashOperator(
        task_id='dbt_transform',
        bash_command='cd /opt/airflow/dbt_project && dbt clean && dbt run --profiles-dir .',
    )

    extract_task >> transform_task
