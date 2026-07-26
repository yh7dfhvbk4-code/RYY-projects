/* ========== AI 对话核心逻辑 ========== */

// ========== API 配置（请在此填入你的 Key）==========
var AI_CONFIG = {
  apiKey: 'YOUR_DEEPSEEK_API_KEY_HERE',  // 替换为你的 DeepSeek API Key
  apiUrl: 'https://api.deepseek.com/chat/completions',
  model: 'deepseek-chat'
};

// ========== 预设问题配置 ==========
var AI_PRESETS = {
  'index.html': [
    '什么是深度学习？',
    'AI会取代人类工作吗？',
    '人工智能有哪些应用？'
  ],
  'technology.html': [
    '神经网络是如何工作的？',
    'NLP和CV有什么区别？',
    '什么是大语言模型？'
  ],
  'applications.html': [
    'AI在医疗领域如何应用？',
    '自动驾驶技术发展到哪一步了？',
    'AI如何改变金融行业？'
  ],
  'trends.html': [
    'AGI什么时候能实现？',
    'AI市场规模有多大？',
    'AI发展趋势是什么？'
  ],
  'ethics.html': [
    'AI存在什么伦理风险？',
    'AI会产生偏见吗？',
    '如何确保AI安全？'
  ],
  'agent.html': [
    '什么是AI Agent？',
    'GitHub Copilot是什么？',
    'Agent技术发展到了什么阶段？'
  ]
};

// ========== 全局状态 ==========
var aiMessages = [];
var aiIsStreaming = false;

// ========== localStorage 读写 ==========
function aiLoadHistory() {
  try {
    var raw = localStorage.getItem('ai_chat_history');
    if (raw) {
      aiMessages = JSON.parse(raw);
    }
  } catch (e) {
    aiMessages = [];
  }
}

function aiSaveHistory() {
  try {
    localStorage.setItem('ai_chat_history', JSON.stringify(aiMessages));
  } catch (e) {
    // localStorage 满了或不可用，静默失败
  }
}

function aiClearHistory() {
  aiMessages = [];
  try {
    localStorage.removeItem('ai_chat_history');
  } catch (e) {}
}

// ========== 上下文感知 ==========
function getPageContext() {
  var parts = [];

  // 提取主标题
  var h1 = document.querySelector('h1');
  if (h1) {
    parts.push('页面标题：' + h1.textContent.trim());
  }

  // 提取主要 section 中的文本内容
  var sections = document.querySelectorAll('section');
  var maxChars = 2000;
  var collected = 0;
  for (var i = 0; i < sections.length && collected < maxChars; i++) {
    var text = sections[i].textContent.trim();
    // 跳过太短的 section（如仅含导航或空的）
    if (text.length < 30) continue;
    if (collected + text.length > maxChars) {
      text = text.substring(0, maxChars - collected) + '...';
    }
    parts.push(text);
    collected += text.length;
  }

  return parts.join('\n\n');
}

// ========== 获取当前页面的预设问题 ==========
function aiGetPresets() {
  var path = window.location.pathname.split('/').pop() || 'index.html';
  return AI_PRESETS[path] || AI_PRESETS['index.html'];
}

// ========== 消息渲染 ==========
function aiRenderMessages() {
  var container = document.getElementById('ai-chat-messages');
  if (!container) return;

  var html = '';
  // 欢迎消息（仅在无历史消息时显示）
  if (aiMessages.length === 0) {
    html += '<div class="ai-message ai-message-system">你好！我是AI探索网站的智能助手，正在阅读当前页面的内容。有什么不懂的随时问我！</div>';
  }

  for (var i = 0; i < aiMessages.length; i++) {
    var msg = aiMessages[i];
    if (msg.role === 'user') {
      html += '<div class="ai-message ai-message-user">' + aiEscapeHtml(msg.content) + '</div>';
    } else if (msg.role === 'assistant') {
      html += '<div class="ai-message ai-message-assistant">' + aiFormatContent(msg.content) + '</div>';
    }
  }

  container.innerHTML = html;
  aiScrollToBottom();
}

function aiEscapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>');
}

function aiFormatContent(text) {
  // 简单的 Markdown 渲染：代码块、加粗、换行
  var html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
  return html;
}

function aiScrollToBottom() {
  var container = document.getElementById('ai-chat-messages');
  if (container) {
    setTimeout(function () {
      container.scrollTop = container.scrollHeight;
    }, 50);
  }
}

// ========== 添加消息 ==========
function aiAddUserMessage(content) {
  aiMessages.push({ role: 'user', content: content });
  aiSaveHistory();
  aiRenderMessages();
}

function aiAddAssistantMessage(content) {
  aiMessages.push({ role: 'assistant', content: content });
  aiSaveHistory();
  aiRenderMessages();
}

// ========== 流式调用 DeepSeek API ==========
function aiSendMessage(userContent) {
  if (aiIsStreaming) return;
  if (!userContent || !userContent.trim()) return;

  aiAddUserMessage(userContent.trim());

  // 创建空的 AI 消息气泡
  aiMessages.push({ role: 'assistant', content: '' });
  aiSaveHistory();
  aiRenderMessages();
  aiIsStreaming = true;

  // 构建 messages 数组
  var apiMessages = [];

  // System prompt
  var pageContext = getPageContext();
  var systemPrompt = '你是AI探索网站的智能助手。用户正在浏览的页面内容如下：\n' +
    pageContext + '\n' +
    '请基于以上页面内容和你的知识，用中文简洁回答用户的问题。如果问题与页面内容无关，也可以自由回答。';
  apiMessages.push({ role: 'system', content: systemPrompt });

  // 历史消息（跳过最后一条空的 assistant 消息）
  for (var i = 0; i < aiMessages.length - 1; i++) {
    apiMessages.push({ role: aiMessages[i].role, content: aiMessages[i].content });
  }

  // 发起请求
  fetch(AI_CONFIG.apiUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + AI_CONFIG.apiKey
    },
    body: JSON.stringify({
      model: AI_CONFIG.model,
      messages: apiMessages,
      stream: true
    })
  }).then(function (response) {
    if (!response.ok) {
      return response.json().then(function (err) {
        throw new Error(err.error ? err.error.message : 'API 请求失败 (' + response.status + ')');
      });
    }

    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var accumulated = '';

    function readStream() {
      reader.read().then(function (result) {
        if (result.done) {
          // 流结束
          aiIsStreaming = false;
          aiSaveHistory();
          aiScrollToBottom();
          return;
        }

        var chunk = decoder.decode(result.value, { stream: true });
        var lines = chunk.split('\n');

        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim();
          if (!line || line === 'data: [DONE]') continue;
          if (line.startsWith('data: ')) {
            try {
              var json = JSON.parse(line.substring(6));
              var delta = json.choices && json.choices[0] && json.choices[0].delta;
              if (delta && delta.content) {
                accumulated += delta.content;
                // 更新最后一条 AI 消息
                aiMessages[aiMessages.length - 1].content = accumulated;
                aiSaveHistory();
                aiRenderMessagesStream();
              }
            } catch (e) {
              // 解析失败，跳过该行
            }
          }
        }

        readStream();
      }).catch(function (err) {
        aiIsStreaming = false;
        aiMessages[aiMessages.length - 1].content = accumulated || '请求失败：' + err.message;
        aiSaveHistory();
        aiRenderMessages();
      });
    }

    readStream();
  }).catch(function (err) {
    aiIsStreaming = false;
    aiMessages[aiMessages.length - 1].content = '网络错误：' + err.message;
    aiSaveHistory();
    aiRenderMessages();
  });
}

// 流式渲染（仅更新最后一条消息，避免整屏重绘）
function aiRenderMessagesStream() {
  var container = document.getElementById('ai-chat-messages');
  if (!container) return;
  var lastMsg = aiMessages[aiMessages.length - 1];
  var bubbles = container.querySelectorAll('.ai-message-assistant');
  var lastBubble = bubbles[bubbles.length - 1];
  if (lastBubble) {
    lastBubble.innerHTML = aiFormatContent(lastMsg.content);
  }
  aiScrollToBottom();
}

// ========== 渲染预设问题按钮 ==========
function aiRenderPresets() {
  var container = document.getElementById('ai-preset-questions');
  if (!container) return;

  var presets = aiGetPresets();
  var html = '';
  for (var i = 0; i < presets.length; i++) {
    html += '<button class="ai-preset-btn" data-question="' + aiEscapeHtml(presets[i]) + '">' + aiEscapeHtml(presets[i]) + '</button>';
  }
  container.innerHTML = html;
}

// ========== 初始化 ==========
function initAIChat() {
  aiLoadHistory();

  // 渲染预设问题
  aiRenderPresets();

  // 渲染历史消息
  aiRenderMessages();

  // 发送按钮
  var sendBtn = document.getElementById('ai-chat-send');
  if (sendBtn) {
    sendBtn.addEventListener('click', function () {
      var input = document.getElementById('ai-chat-input');
      if (input) {
        aiSendMessage(input.value);
        input.value = '';
        input.style.height = 'auto';
      }
    });
  }

  // 输入框回车发送
  var input = document.getElementById('ai-chat-input');
  if (input) {
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        aiSendMessage(input.value);
        input.value = '';
        input.style.height = 'auto';
      }
    });

    // 自动调整高度
    input.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
  }

  // 预设问题点击
  var presetContainer = document.getElementById('ai-preset-questions');
  if (presetContainer) {
    presetContainer.addEventListener('click', function (e) {
      var btn = e.target.closest('.ai-preset-btn');
      if (btn) {
        var question = btn.getAttribute('data-question');
        if (question) {
          aiSendMessage(question);
        }
      }
    });
  }

  // 关闭按钮
  var closeBtn = document.getElementById('ai-sidebar-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', function () {
      var panel = document.getElementById('ai-sidebar-panel');
      if (panel) {
        panel.classList.remove('ai-expanded');
      }
    });
  }

  // 侧边栏标签点击展开
  var tab = document.getElementById('ai-sidebar-tab');
  if (tab) {
    tab.addEventListener('click', function () {
      var panel = document.getElementById('ai-sidebar-panel');
      if (panel) {
        panel.classList.add('ai-expanded');
      }
    });

    // 悬停展开
    var sidebar = document.getElementById('ai-sidebar');
    if (sidebar) {
      sidebar.addEventListener('mouseenter', function () {
        var panel = document.getElementById('ai-sidebar-panel');
        if (panel) {
          panel.classList.add('ai-expanded');
        }
      });
      sidebar.addEventListener('mouseleave', function () {
        var panel = document.getElementById('ai-sidebar-panel');
        if (panel) {
          panel.classList.remove('ai-expanded');
        }
      });
    }
  }
}
