/* ========== 公共组件：导航栏 + 页脚 ========== */

/**
 * 动态渲染导航栏
 * @param {string} currentPage - 当前页面文件名，如 "index.html"
 */
function renderNavbar(currentPage) {
  var pages = [
    { href: 'index.html', label: '首页' },
    { href: 'technology.html', label: '技术介绍' },
    { href: 'applications.html', label: '应用场景' },
    { href: 'trends.html', label: '发展趋势' },
    { href: 'ethics.html', label: '伦理探讨' },
    { href: 'agent.html', label: 'Agent技术' }
  ];

  var linksHtml = '';
  pages.forEach(function(page) {
    var activeClass = (page.href === currentPage) ? ' active' : '';
    linksHtml += '<li class="nav-item"><a class="nav-link' + activeClass + '" href="' + page.href + '">' + page.label + '</a></li>';
  });

  var navbarHtml =
    '<nav class="navbar navbar-expand-lg navbar-custom fixed-top">' +
    '  <div class="container">' +
    '    <a class="navbar-brand" href="index.html"><i class="fas fa-brain"></i> AI探索</a>' +
    '    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">' +
    '      <span class="navbar-toggler-icon"></span>' +
    '    </button>' +
    '    <div class="collapse navbar-collapse" id="navbarNav">' +
    '      <ul class="navbar-nav ms-auto">' +
    linksHtml +
    '      </ul>' +
    '    </div>' +
    '  </div>' +
    '</nav>';

  document.getElementById('navbar-container').innerHTML = navbarHtml;
}

/**
 * 动态渲染页脚
 */
function renderFooter() {
  var footerHtml =
    '<footer class="footer-section">' +
    '  <div class="container">' +
    '    <div class="row">' +
    '      <div class="col-md-4 mb-4 mb-md-0">' +
    '        <h5><i class="fas fa-brain me-2"></i>AI探索</h5>' +
    '        <p>人工智能主题综合网站，致力于科普AI技术、应用与发展趋势。</p>' +
    '      </div>' +
    '      <div class="col-md-4 mb-4 mb-md-0">' +
    '        <h5>联系我们</h5>' +
    '        <p><i class="fas fa-envelope me-2"></i>15160073716@163.com</p>' +
    '        <p><i class="fas fa-map-marker-alt me-2"></i>福建省福州市闽侯县上街镇学园路3号</p>' +
    '      </div>' +
    '      <div class="col-md-4">' +
    '        <h5>外部链接</h5>' +
    '        <ul class="footer-links">' +
    '          <li><a href="https://www.deepseek.com/" target="_blank">DeepSeek</a></li>' +
    '          <li><a href="https://www.doubao.com/" target="_blank">豆包</a></li>' +
    '          <li><a href="https://yiyan.baidu.com/" target="_blank">文心一言</a></li>' +
    '          <li><a href="https://xinghuo.xfyun.cn/" target="_blank">讯飞星火</a></li>' +
    '          <li><a href="https://mimo.mi.com/" target="_blank">Xiaomi MIMO Home</a></li>' +
    '          <li><a href="https://www.volcengine.com/product/ark" target="_blank">火山方舟</a></li>' +
    '        </ul>' +
    '      </div>' +
    '    </div>' +
    '    <div class="footer-bottom">' +
    '      <p>&copy; 2026 AI探索 - 人工智能主题网站</p>' +
    '    </div>' +
    '  </div>' +
    '</footer>';

  document.getElementById('footer-container').innerHTML = footerHtml;
}

/**
 * 动态渲染 AI 辅助问答浮动按钮 + 弹窗
 */
function renderAIChatWidget() {
  var widgetHtml =
    '<div id="ai-chat-btn" title="AI助手">' +
    '  <i class="fas fa-robot"></i>' +
    '</div>' +
    '<div id="ai-chat-popup" style="display:none;">' +
    '  <div id="ai-chat-popup-header">' +
    '    <i class="fas fa-robot"></i> AI 智能助手' +
    '    <button id="ai-chat-popup-close"><i class="fas fa-times"></i></button>' +
    '  </div>' +
    '  <div id="ai-preset-questions"></div>' +
    '  <div id="ai-chat-messages">' +
    '    <div class="ai-message ai-message-system">' +
    '      你好！我是AI探索网站的智能助手，正在阅读当前页面的内容。有什么不懂的随时问我！' +
    '    </div>' +
    '  </div>' +
    '  <div id="ai-chat-input-area">' +
    '    <textarea id="ai-chat-input" placeholder="输入你的问题..." rows="1"></textarea>' +
    '    <button id="ai-chat-send" title="发送"><i class="fas fa-paper-plane"></i></button>' +
    '  </div>' +
    '</div>';

  document.body.insertAdjacentHTML('beforeend', widgetHtml);

  // 渲染完成后自动初始化 AI 对话
  if (typeof initAIChat === 'function') {
    initAIChat();
  }

  // 浮动按钮与关闭按钮的弹窗切换
  var btn = document.getElementById('ai-chat-btn');
  var popup = document.getElementById('ai-chat-popup');
  var closeBtn = document.getElementById('ai-chat-popup-close');

  if (btn && popup) {
    btn.addEventListener('click', function () {
      if (popup.style.display === 'none' || popup.style.display === '') {
        popup.style.display = 'flex';
      } else {
        popup.style.display = 'none';
      }
    });
  }

  if (closeBtn && popup) {
    closeBtn.addEventListener('click', function () {
      popup.style.display = 'none';
    });
  }
}
