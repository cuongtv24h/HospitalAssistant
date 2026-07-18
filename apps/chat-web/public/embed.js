(function() {
  // Cấu hình URL của chatbot đã được deploy
  // Có thể ghi đè bằng cách set window.HospitalChatbotConfig trước khi load script
  var config = window.HospitalChatbotConfig || {};
  var BASE_URL = config.url || 'http://localhost:5173'; // Thay bằng URL production khi deploy
  var CHATBOT_URL = BASE_URL + (BASE_URL.includes('?') ? '&' : '?') + 'embed=1';
  var BUTTON_COLOR = config.buttonColor || '#0ea5e9'; // Màu primary của Bệnh viện Tim HN
  
  // Tạo container
  var container = document.createElement('div');
  container.id = 'hospital-chatbot-container';
  container.style.position = 'fixed';
  container.style.bottom = '24px';
  container.style.right = '24px';
  container.style.zIndex = '999999';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.alignItems = 'flex-end';
  container.style.fontFamily = 'system-ui, -apple-system, sans-serif';

  // Tạo iframe
  var iframe = document.createElement('iframe');
  iframe.src = CHATBOT_URL;
  iframe.id = 'hospital-chatbot-iframe';
  iframe.style.width = '400px';
  iframe.style.height = '600px';
  iframe.style.maxHeight = 'calc(100vh - 100px)';
  iframe.style.maxWidth = 'calc(100vw - 48px)';
  iframe.style.border = 'none';
  iframe.style.borderRadius = '16px';
  iframe.style.boxShadow = '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)';
  iframe.style.display = 'none';
  iframe.style.marginBottom = '16px';
  iframe.style.backgroundColor = 'transparent';
  iframe.style.opacity = '0';
  iframe.style.transform = 'translateY(10px) scale(0.95)';
  iframe.style.transformOrigin = 'bottom right';
  iframe.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
  iframe.allow = "microphone";

  // Tạo nút bấm toggle
  var toggleBtn = document.createElement('button');
  toggleBtn.id = 'hospital-chatbot-toggle';
  toggleBtn.style.width = '60px';
  toggleBtn.style.height = '60px';
  toggleBtn.style.borderRadius = '30px';
  toggleBtn.style.backgroundColor = BUTTON_COLOR;
  toggleBtn.style.color = '#ffffff';
  toggleBtn.style.border = 'none';
  toggleBtn.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
  toggleBtn.style.cursor = 'pointer';
  toggleBtn.style.display = 'flex';
  toggleBtn.style.alignItems = 'center';
  toggleBtn.style.justifyContent = 'center';
  toggleBtn.style.transition = 'transform 0.2s ease, background-color 0.2s ease';
  
  // Icon chat
  var chatIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>';
  // Icon close
  var closeIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
  
  toggleBtn.innerHTML = chatIcon;

  var isOpen = false;

  toggleBtn.addEventListener('click', function() {
    isOpen = !isOpen;
    if (isOpen) {
      iframe.style.display = 'block';
      // Trigger reflow cho animation
      void iframe.offsetWidth;
      iframe.style.opacity = '1';
      iframe.style.transform = 'translateY(0) scale(1)';
      toggleBtn.innerHTML = closeIcon;
      toggleBtn.style.transform = 'scale(1.1)';
      setTimeout(() => toggleBtn.style.transform = 'scale(1)', 200);
    } else {
      iframe.style.opacity = '0';
      iframe.style.transform = 'translateY(10px) scale(0.95)';
      toggleBtn.innerHTML = chatIcon;
      toggleBtn.style.transform = 'scale(0.9)';
      setTimeout(() => toggleBtn.style.transform = 'scale(1)', 200);
      setTimeout(function() {
        if (!isOpen) iframe.style.display = 'none';
      }, 300);
    }
  });

  // Hiệu ứng hover cho nút
  toggleBtn.addEventListener('mouseenter', function() {
    if(!isOpen) toggleBtn.style.transform = 'scale(1.05)';
  });
  toggleBtn.addEventListener('mouseleave', function() {
    if(!isOpen) toggleBtn.style.transform = 'scale(1)';
  });

  container.appendChild(iframe);
  container.appendChild(toggleBtn);
  document.body.appendChild(container);
})();
