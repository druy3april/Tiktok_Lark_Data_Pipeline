# TikTok Lark Data Pipeline & Automation Scraper

Hệ thống pipeline tự động thu thập, xử lý dữ liệu chỉ số video, hiệu suất kênh và đồng bộ luồng dữ liệu doanh thu từ nền tảng TikTok về hệ thống quản trị tập trung Lark Base (Lark Suite).

## 📌 Tổng Quan Dự Án
Dự án được xây dựng nhằm giải quyết bài toán quản trị và theo dõi hiệu suất kinh doanh đa kênh TikTok cho doanh nghiệp. Thay vì phải kiểm tra thủ công từng tài khoản, hệ thống tự động hóa toàn bộ luồng trích xuất dữ liệu và đồng bộ theo thời gian thực, giúp đội ngũ vận hành dễ dàng theo dõi biến động doanh thu và phát hiện nhanh các lỗi phát sinh.

## 🛠 Cấu Trúc Hệ Thống & Công Nghệ
* **Data Scraper (Python):** Tự động thu thập dữ liệu chỉ số tương tác kênh, lượt xem, và thông tin video từ các trang đích TikTok.
* **Workflow Scheduling (Apache Airflow):** Lập lịch, quản lý và vận hành tự động toàn bộ luồng công việc (DAGs) theo chu kỳ định sẵn một cách ổn định.
* **Data Integration (API & Webhooks):** Kết nối, truyền tải và đồng bộ luồng dữ liệu doanh thu, trạng thái đơn hàng thô trực tiếp về hệ thống Lark Base.
* **Giao diện hiển thị:** Sử dụng công cụ Lark Base (Lark Suite) để làm dashboard giao diện web, trực quan hóa toàn bộ chỉ số vận hành và doanh thu thực tế.

## 🚀 Tính Năng Cốt Lõi
1. **Thu thập dữ liệu tự động:** Khai thác dữ liệu động từ nguồn TikTok, tích hợp cơ chế bắt lỗi hệ thống (Error handling) đảm bảo luồng dữ liệu thô luôn toàn vẹn.
2. **Lập lịch tự động bằng Airflow:** Tối ưu hóa chu kỳ chạy của các task dữ liệu, đảm bảo dữ liệu luôn cập nhật mới nhất cho báo cáo ngày/tuần.
3. **Theo dõi doanh thu & Đơn hàng:** Tập trung hóa dữ liệu đa kênh để tự động hóa báo cáo doanh số, giúp phát hiện sớm các đơn hàng lỗi và tối ưu chi phí phân phối nội dung kịp thời.
