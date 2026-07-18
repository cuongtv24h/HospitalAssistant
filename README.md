# Trợ lý Chăm sóc Khách hàng AI — Bệnh viện Tim Hà Nội

Trợ lý AI hỗ trợ bệnh nhân và người nhà tra cứu thông tin chính thức của Bệnh viện Tim Hà Nội, giải đáp FAQ, hỗ trợ đặt/tra cứu lịch hẹn và xử lý tình huống khẩn cấp.

## Tính năng chính

- Tra cứu thông tin theo 7 nhóm:
  - Đặt lịch hẹn
  - Quy trình khám / tái khám / nhập viện
  - BHYT
  - Giá dịch vụ
  - Giờ làm việc
  - Bác sĩ và chuyên khoa
  - Thông tin chính thức khác
- Hỗ trợ hội thoại tiếng Việt
- Gợi ý luồng thao tác nhanh bằng button
- Đặt lịch và tra cứu lịch hẹn qua Mock HIS
- Phát hiện tình huống khẩn cấp và hướng dẫn an toàn
- Phản hồi có căn cứ từ knowledge base, không bịa đặt

## Kiến trúc mức cao

- **Frontend:** React + Vite
- **Backend:** Python + FastAPI
- **AI:** LLM qua API, hỗ trợ nhiều provider và fallback
- **Knowledge Base:** Text/PDF đã chuẩn hóa, tìm kiếm bằng vector search
- **Database:** Supabase Postgres + pgvector
- **Appointment:** Mock HIS API

## Nguyên tắc sản phẩm

- AI là năng lực cốt lõi của sản phẩm
- Mọi phản hồi phải bám theo nguồn chính thức
- Không tư vấn y tế, không chẩn đoán bệnh
- Ưu tiên an toàn trong tình huống khẩn cấp
- Luôn có fallback hoặc hướng dẫn kênh hỗ trợ phù hợp

## Luồng chính

1. Người dùng mở chat trên website
2. Chọn một nhu cầu phổ biến hoặc nhập câu hỏi tự do
3. Hệ thống kiểm tra tình huống khẩn cấp
4. AI phân tích ý định và gọi công cụ phù hợp
5. Trả lời kèm nguồn tham chiếu hoặc hướng dẫn tiếp theo
6. Nếu cần, hỗ trợ đặt lịch hoặc tra cứu lịch hẹn

## Tài liệu

- `docs/requirement-analysis.md`
- `docs/product-definition.md`
- `docs/architecture-design.md`

## Lưu ý

Đây là phiên bản Hackathon / MVP định hướng demo và kiến trúc mở rộng.  
Một số dữ liệu tích hợp bệnh viện hiện được mô phỏng qua Mock HIS.

## Disclaimer

Sản phẩm này **không thay thế bác sĩ**.  
Trong trường hợp có dấu hiệu cấp cứu như đau ngực dữ dội, khó thở, ngất xỉu, hãy gọi cấp cứu hoặc đến cơ sở y tế ngay lập tức.