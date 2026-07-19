---
name: "Trợ lý Bệnh viện Tim Hà Nội"
description: "Một quầy hướng dẫn số đáng tin cậy, điềm tĩnh và gần gũi cho bệnh nhân và người nhà."
colors:
  guidance-blue: "#006BB6"
  guidance-blue-strong: "#00528D"
  reassurance-teal: "#007D78"
  reassurance-teal-strong: "#00635F"
  heart-red: "#C81E1E"
  heart-red-strong: "#A71919"
  heart-red-soft: "#FFF1F0"
  heart-red-border: "#EF9A95"
  guidance-blue-soft: "#EAF5FF"
  guidance-blue-on-dark: "#DFF2FF"
  guidance-blue-border: "#8FC5EE"
  reassurance-teal-soft: "#E8FAF7"
  reassurance-teal-border: "#76CFC7"
  cost-amber-soft: "#FFF7E8"
  cost-amber-strong: "#8A4B00"
  cost-amber-border: "#E5B86B"
  night-ink: "#0B2538"
  supporting-ink: "#355A6F"
  canvas: "#EEF7FA"
  surface: "#FFFFFF"
  surface-soft: "#F7FBFD"
  border: "#7AA6B8"
  focus: "#FFB020"
  success: "#008A4D"
  danger: "#B42318"
  danger-soft: "#FFF1F0"
  dark-canvas: "#061B28"
  dark-surface: "#0D2B3B"
  dark-text: "#F5FFFC"
typography:
  display:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, -apple-system, sans-serif"
    fontSize: "48px"
    fontWeight: 800
    lineHeight: 1.12
    letterSpacing: "-0.02em"
  display-compact:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, -apple-system, sans-serif"
    fontSize: "36px"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, -apple-system, sans-serif"
    fontSize: "20px"
    fontWeight: 800
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, -apple-system, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, -apple-system, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.55
  lead:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, -apple-system, sans-serif"
    fontSize: "18px"
    fontWeight: 400
    lineHeight: 1.65
  helper:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, -apple-system, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.35
  caption:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, -apple-system, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.4
rounded:
  xs: "4px"
  compact: "6px"
  sm: "8px"
  brand-mark: "10px"
  md: "12px"
  lg: "18px"
  shell: "24px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  xxl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.guidance-blue}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.guidance-blue-strong}"
    textColor: "{colors.surface}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.night-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "11px 15px"
    height: "44px"
  action-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.night-ink}"
    rounded: "{rounded.md}"
    padding: "16px"
  text-input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.night-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "11px 12px"
    height: "44px"
  assistant-message:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.night-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: "13px 16px"
  status-chip:
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.reassurance-teal-strong}"
    typography: "{typography.caption}"
    rounded: "{rounded.pill}"
    padding: "6px 10px"
---

# Design System: Trợ lý Bệnh viện Tim Hà Nội

## 1. Overview

**Creative North Star: "Quầy hướng dẫn bình tâm"**

Giao diện phải rõ ràng như một quầy tiếp đón bệnh viện được tổ chức tốt, nhưng riêng tư và gần gũi như một cuộc trò chuyện một-một. Mỗi màn hình dẫn người dùng đến một câu trả lời hoặc một bước hành động cụ thể; hệ thống không phô diễn AI và không yêu cầu người dùng học cách sử dụng nó.

Mật độ thông tin vừa phải, thứ bậc dễ quét và các điều khiển sử dụng affordance quen thuộc. Màu sắc và chuyển động chỉ diễn đạt trạng thái. Hệ thống tuyệt đối không được giống chatbot AI màu mè hoặc sáo rỗng, đồng thời không được lạnh lẽo, dày đặc hay máy móc như phần mềm quản trị bệnh viện.

**Key Characteristics:**

- Điềm tĩnh, sáng và có trật tự.
- Thân thiện với người lớn tuổi và người đang lo lắng.
- Hành động chính rõ nhưng không lấn át nội dung.
- Nguồn tham khảo, cảnh báo và bước xác nhận có phân cấp riêng.
- Responsive theo cấu trúc; chuyển động chỉ phản hồi trạng thái.

## 2. Colors

Bảng màu dùng xanh lam để chỉ dẫn, teal để củng cố cảm giác an tâm và các màu trung tính hơi lạnh để giữ không gian sạch, rõ, không mang cảm giác phòng điều khiển.

### Primary

- **Xanh chỉ dẫn:** Dành cho hành động chính, liên kết, lựa chọn hiện tại và các điểm điều hướng cần chú ý. Phiên bản đậm dùng cho hover và văn bản liên kết trên nền sáng.

### Secondary

- **Xanh an tâm:** Dành cho trạng thái tích cực, dấu hiệu đang hoạt động, icon hỗ trợ và điểm nhấn phụ. Không dùng cạnh tranh với hành động chính.

### Neutral

- **Mực đêm:** Màu văn bản chính, giữ độ tương phản cao mà mềm hơn đen tuyệt đối.
- **Mực hỗ trợ:** Dành cho mô tả, metadata và nội dung phụ; không dùng cho nội dung quan trọng hoặc chữ nhỏ trên nền màu.
- **Nền trò chuyện:** Tách nhẹ vùng hội thoại khỏi bề mặt trắng mà không tạo thêm một card trang trí.
- **Bề mặt trắng và bề mặt dịu:** Dành cho vùng nhập, nội dung có cấu trúc và trạng thái hover nhẹ.
- **Đường phân cách:** Chỉ dùng khi khoảng trắng không đủ diễn đạt ranh giới.

### Semantic

- **Cam tập trung:** Chỉ dành cho focus ring có độ tương phản cao.
- **Xanh thành công:** Dành cho trạng thái trực tuyến, hoàn tất hoặc xác nhận thành công; luôn đi cùng nhãn chữ hoặc icon.
- **Đỏ nguy hiểm:** Dành cho lỗi và tình huống cần chú ý khẩn cấp; không dùng như màu trang trí.

### Named Rules

**The One Guidance Rule.** Xanh chỉ dẫn là accent chính và không được phủ quá 10% một màn hình; độ hiếm làm cho hành động chính dễ nhận biết.

**The No Decorative Gradient Rule.** Gradient trang trí bị cấm. Một trạng thái chỉ được dùng một màu nền có chủ đích, không trộn xanh lam và teal để tạo cảm giác “AI”.

**The Meaning Beyond Color Rule.** Mọi trạng thái thành công, cảnh báo, lỗi và lựa chọn đều phải có nhãn chữ, icon hoặc thay đổi hình dạng; màu không bao giờ là tín hiệu duy nhất.

## 3. Typography

**Display Font:** Be Vietnam Pro (với `ui-sans-serif`, `system-ui` và sans-serif hệ thống dự phòng)  
**Body Font:** Be Vietnam Pro (với `ui-sans-serif`, `system-ui` và sans-serif hệ thống dự phòng)

**Character:** Một họ chữ sans duy nhất tạo sự quen thuộc và nhất quán trong sản phẩm. Be Vietnam Pro giữ dấu tiếng Việt rõ ràng, có cấu trúc thân thiện và đủ trọng lượng để phân cấp mà không cần font trình diễn.

### Hierarchy

- **Headline:** Dành cho tiêu đề ứng dụng và tiêu đề bước chính; chỉ dùng một lần trong mỗi vùng tác vụ.
- **Title:** Dành cho tiêu đề card, lựa chọn và nhóm nội dung.
- **Body:** Dành cho câu trả lời và hướng dẫn; nội dung dài giới hạn khoảng 65–75 ký tự mỗi dòng khi bố cục cho phép.
- **Label:** Dành cho nút, nhãn trường và hành động; dùng sentence case, không viết hoa toàn bộ câu.
- **Caption:** Dành cho metadata, ngày hiệu lực, trạng thái phụ và mô tả ngắn; không được nhỏ hơn mức này.

### Named Rules

**The Vietnamese First Rule.** Không giảm cỡ chữ hoặc line-height để ép nội dung tiếng Việt vào card. Bố cục phải giãn ra trước khi khả năng đọc bị hy sinh.

**The Quiet Hierarchy Rule.** Phân cấp bằng trọng lượng, khoảng cách và màu chữ trước; cấm heading phóng đại hoặc display font trong giao diện tác vụ.

## 4. Elevation

Hệ thống phân lớp nhẹ và có tính cấu trúc. Bề mặt mặc định gần như phẳng; khoảng trắng, nền tonal và đường phân cách mảnh tạo chiều sâu trước khi dùng bóng. Bóng chỉ xuất hiện ở shell chính, bề mặt nổi thật sự và trạng thái tương tác cần phản hồi.

### Shadow Vocabulary

- **Shell ambient:** Bóng khuếch tán rộng, độ tương phản thấp để tách ứng dụng khỏi nền desktop; không dùng trên mobile toàn màn hình.
- **Raised surface:** Bóng nhỏ cho confirmation panel, tooltip hoặc menu nổi; không áp dụng đồng loạt cho mọi card.
- **Interactive lift:** Một thay đổi rất nhẹ khi hover trên thiết bị có con trỏ; bị vô hiệu khi người dùng bật reduced motion.

### Named Rules

**The Flat-by-Default Rule.** Card và nút phẳng ở trạng thái nghỉ. Nếu mọi phần tử đều có bóng, không phần tử nào thực sự có thứ bậc.

**The Structural Motion Rule.** Chuyển động kéo dài 150–250ms và chỉ diễn đạt hover, focus, mở/đóng hoặc thay đổi trạng thái. Animation trang trí và chuỗi xuất hiện dàn dựng bị cấm.

## 5. Components

### Buttons

Nút phải quen thuộc, vững chãi và dễ bấm.

- **Shape:** Góc bo vừa phải; nút chữ nhật dùng bán kính trung bình, nút icon đơn lẻ có thể dùng hình tròn.
- **Primary:** Nền Xanh chỉ dẫn đặc, chữ trắng, chiều cao tối thiểu 44px; mỗi vùng tác vụ chỉ có một primary action.
- **Hover / Focus:** Hover chuyển sang sắc đậm hơn, không dùng gradient hoặc nhảy quá 1px. Focus dùng vòng Cam tập trung rõ ràng, không thay thế bằng bóng mờ.
- **Secondary / Ghost:** Nền trắng hoặc trong suốt, chữ Mực đêm hoặc Xanh chỉ dẫn và có border khi cần affordance. Link action không giả làm nút nếu không thực hiện một hành động tức thời.
- **Disabled / Loading:** Giữ nguyên kích thước và nhãn ngữ cảnh; trạng thái loading không làm layout dịch chuyển.

### Chips

Chip chỉ dùng cho trạng thái ngắn hoặc lựa chọn compact, không thay thế nút hành động quan trọng. Dùng nền dịu, chữ teal đậm, bán kính pill và luôn có nhãn rõ ràng; selected state cần thêm icon hoặc border ngoài thay đổi màu.

### Cards / Containers

Card là nhóm nội dung có quan hệ, không phải vật trang trí.

- **Corner Style:** Bo góc vừa cho action card và bo lớn hơn cho panel dẫn luồng; không trộn nhiều bán kính trong cùng một nhóm.
- **Background:** Chủ yếu là trắng trên nền trò chuyện dịu; dùng tonal surface thay vì gradient.
- **Shadow Strategy:** Phẳng mặc định, tham chiếu nguyên tắc elevation phía trên.
- **Border:** Một đường ranh giới rõ là đủ; cấm border dày kết hợp đồng thời với bóng đậm.
- **Internal Padding:** 16px trên mobile, 16–24px trên màn hình rộng tùy mật độ nội dung.

### Inputs / Fields

Trường nhập phải trông và hoạt động như điều khiển form quen thuộc.

- **Style:** Nền trắng, border rõ, góc bo trung bình, chữ body 16px và vùng bấm tối thiểu 44px.
- **Focus:** Border chuyển sang Xanh chỉ dẫn và có focus ring Cam tập trung; không dịch chuyển trường nhập.
- **Error / Disabled:** Lỗi có thông báo cụ thể cạnh trường và icon khi phù hợp. Disabled vẫn đọc được, không chỉ giảm opacity đến mức mất tương phản.

### Navigation

Header gọn, giữ avatar/nhận diện, trạng thái trực tuyến và các utility action. Tác vụ chính nằm trong nội dung, không đặt cạnh nút đổi theme hoặc bắt đầu cuộc trò chuyện mới. Trên mobile, nhãn utility có thể rút gọn nhưng vùng bấm phải giữ tối thiểu 44px.

### Conversation and Booking Flow

Tin nhắn trợ lý dùng bề mặt sáng, độ rộng đọc thoải mái và Markdown có phân cấp rõ. Trích dẫn là phần hỗ trợ có thể quét, không cạnh tranh với câu trả lời. Luồng đặt lịch dùng một vùng tác vụ liên tục với chỉ báo bước, lựa chọn chuyên khoa, bác sĩ, thời gian, thông tin bệnh nhân và một màn xác nhận human-in-the-loop trước khi gửi.

## 6. Do's and Don'ts

### Do:

- **Do** dùng Xanh chỉ dẫn cho một hành động chính hoặc lựa chọn hiện tại trong mỗi vùng tác vụ.
- **Do** giữ chữ nội dung ở 16px khi có thể và mọi vùng tương tác tối thiểu 44px.
- **Do** dùng khoảng trắng, nền tonal và đường phân cách trước khi thêm bóng.
- **Do** hiển thị nguồn, trạng thái, lỗi và bước tiếp theo bằng ngôn ngữ tiếng Việt trực tiếp.
- **Do** tôn trọng `prefers-reduced-motion` và loại bỏ mọi chuyển động không cần thiết khi tùy chọn này được bật.
- **Do** giữ bước xác nhận đặt lịch rõ ràng, tách biệt khỏi nội dung RAG và không tự động gửi thay người dùng.

### Don't:

- **Don't** làm giao diện giống một chatbot AI màu mè hoặc sáo rỗng.
- **Don't** dùng gradient trang trí, hiệu ứng chuyển động không phục vụ trạng thái hoặc chi tiết cố tạo cảm giác “công nghệ tương lai”.
- **Don't** tạo cảm giác lạnh lẽo, dày đặc hoặc máy móc như phần mềm quản trị bệnh viện.
- **Don't** đặt bóng, border dày và nền màu lên mọi card cùng lúc; nếu mọi thứ đều nổi, thứ bậc đã thất bại.
- **Don't** truyền đạt thành công, cảnh báo, lỗi hoặc lựa chọn chỉ bằng màu sắc.
- **Don't** dùng animation quay, nảy hoặc pulse cho icon utility khi hành động không thay đổi trạng thái hệ thống.
- **Don't** ẩn nội dung cần thiết của chuyên khoa, bác sĩ hoặc bước xác nhận chỉ để giữ card thấp hơn.
