# AI探索 - 人工智能主题网站

一个关于人工智能技术的综合性主题网站，展示AI技术的发展历程、应用场景、技术原理等内容。

## 🛠️ 技术栈

### 前端框架
- **Bootstrap 5.3.8** - 响应式CSS框架，用于构建现代化UI组件
- **Font Awesome 6.5.1** - 图标库，提供丰富的矢量图标

### 编程语言
- **HTML5** - 页面结构和内容
- **CSS3** - 样式设计，包含动画、渐变、阴影等效果
- **JavaScript (ES6+)** - 交互逻辑和动态效果

### AI API 集成
- **DeepSeek API** - 大语言模型接口，实现流式对话问答
- **Server-Sent Events (SSE)** - 流式数据传输协议
- **localStorage API** - 跨页面会话历史持久化

### 第三方库
- **jQuery 3.7.1** - 简化DOM操作和事件处理
- **Bootstrap Bundle** - Bootstrap JavaScript组件（模态框、轮播等）

### 设计特色
- **深色主题** - 现代化暗色配色方案
- **渐变效果** - 紫色(#6c5ce7)与青色(#00cec9)渐变
- **动画效果** - CSS动画和SVG动画
- **响应式设计** - 适配桌面端和移动端

## 📁 项目结构

```
├── index.html          # 首页
├── technology.html     # 技术介绍页
├── applications.html   # 应用场景页
├── trends.html         # 发展趋势页
├── ethics.html         # 伦理探讨页
├── agent.html          # Agent技术发展页
├── css/
│   └── style.css       # 自定义样式
└── js/
    ├── components.js   # 公共组件（导航栏、页脚、AI聊天窗）
    ├── main.js         # 页面交互逻辑（滚动动画、粒子、打字机等）
    └── ai-chat.js      # AI对话核心逻辑（DeepSeek API流式调用）
```

## 📄 页面介绍

### 1. 首页 (index.html)
- **功能**：网站入口，展示AI概览
- **技术特点**：
  - 粒子动画背景
  - 打字机效果标题
  - 数据统计卡片（数字滚动动画）
  - 导航栏固定定位
  - Hero区域渐变背景

### 2. 技术介绍页 (technology.html)
- **功能**：介绍AI核心技术原理
- **技术特点**：
  - 美化的表格展示（深色主题适配）
  - 斑马纹背景和悬停效果
  - 毛玻璃效果卡片
  - 响应式表格布局

### 3. 应用场景页 (applications.html)
- **功能**：展示AI在各领域的应用
- **技术特点**：
  - 卡片式布局展示各应用场景
  - 图标和描述组合
  - 悬停动画效果

### 4. 发展趋势页 (trends.html)
- **功能**：展示AI技术发展趋势数据
- **技术特点**：
  - CSS柱状图展示（渐变彩色）
  - 动画条形图
  - 光泽效果

### 5. 伦理探讨页 (ethics.html)
- **功能**：讨论AI伦理和社会影响
- **技术特点**：
  - 卡片式内容布局
  - "深入了解"按钮跳转至相关新闻链接
  - 响应式设计

### 6. Agent技术发展页 (agent.html)
- **功能**：介绍AI Agent技术发展历程
- **技术特点**：
  - SVG波浪线时间线
  - 动画绘制效果
  - 事件节点悬停交互
  - 未来节点脉冲动画
  - 品牌图标展示（GitHub Copilot、Claude Code等）

## 🤖 AI 辅助问答（答辩后新增）

在完成与老师的答辩后，进一步扩展了项目功能，接入了 DeepSeek 大语言模型 API，为网站增加了 AI 智能问答能力。

### 交互方式
- 右下角**浮动圆形按钮**（紫青渐变、带呼吸动画），点击弹出对话气泡窗
- 再次点击按钮或点击窗口头部关闭按钮收起

### 核心功能
- **上下文感知**：AI 自动读取用户当前浏览页面的标题和主要内容，作为对话背景
- **预设快捷问题**：每个页面根据主题自动生成 2~3 个推荐问题，点击即可发送
- **流式输出**：AI 回复逐字显示，使用 Fetch + ReadableStream 解析 SSE 响应
- **跨页面会话保持**：通过 localStorage 保存对话历史，切换页面不丢失
- **API Key 配置位**：在 `js/ai-chat.js` 顶部预留配置位置，用户自行填入密钥

### 方案选型
比较了两种交互方案：

| 方案 | 描述 | 结论 |
|------|------|------|
| 方案1 | 右下角浮动圆形按钮，点击弹出气泡对话框 | ✅ 采用 |
| 方案2 | 右侧固定窄条，悬停滑出侧边栏面板 | 未采用 |

方案1更符合在线客服式的轻量交互习惯，对页面内容干扰更小。

### 技术实现
- 使用 `getPageContext()` 提取页面 h1 和 section 文本作为 System Prompt
- 通过 `fetch()` + `ReadableStream` 实现 SSE 流式解析
- 消息数组通过 `JSON.stringify/parse` 存入 localStorage，key 为 `ai_chat_history`

## 🎨 设计规范

### 颜色变量
- `--primary`: #6c5ce7（紫色主色）
- `--secondary`: #00cec9（青色辅助色）
- `--dark`: #0f0f23（深色背景）
- `--dark-light`: #1a1a2e（浅色深色背景）
- `--dark-card`: rgba(30, 30, 58, 0.95)（卡片背景）

### 字体颜色
- 主文本：#ffffff
- 次要文本：#b8b8d0
- 渐变文本：紫色到青色渐变

### 组件样式
- **按钮**: `.btn-glow` 系列类，带发光效果
- **卡片**: `.card-custom`，带毛玻璃效果
- **导航栏**: `.navbar-custom`，固定顶部
- **页脚**: `.footer-section`，统一布局

## 🚀 快速开始

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd web期末设计
   ```

2. **本地运行**
   - 使用浏览器直接打开 `index.html`
   - 或使用本地服务器：
   ```bash
   python -m http.server 8000
   ```

3. **配置 AI 问答（可选）**
   打开 `js/ai-chat.js`，在顶部找到：
   ```js
   apiKey: 'YOUR_DEEPSEEK_API_KEY_HERE',
   ```
   替换为你的 DeepSeek API Key。如不配置，AI 问答功能不可用，其他功能不受影响。

4. **访问网站**
   - 打开浏览器访问 `http://localhost:8000`

## 📱 响应式支持

- **桌面端**: 完整功能展示
- **平板端**: 自适应布局
- **移动端**: 折叠导航栏，单列布局

## 🔗 外部链接

页脚包含以下外部链接：

### AI工具
- DeepSeek: https://www.deepseek.com/
- 豆包: https://www.doubao.com/
- 文心一言: https://yiyan.baidu.com/
- 讯飞星火: https://xinghuo.xfyun.cn/

### 更多内容
- Xiaomi MIMO Home: https://mimo.mi.com/
- 火山方舟: https://www.volcengine.com/product/ark

### 技术参考
- DeepSeek API 文档: https://platform.deepseek.com/api-docs/

## 🔧 代码重构（答辩优化）

### 导航栏与页脚组件化
- 导航栏和页脚原本在 6 个 HTML 文件中各重复约 80 行，总计约 480 行重复代码
- 重构为 `components.js` 中的 `renderNavbar(currentPage)` 和 `renderFooter()` 函数
- 通过数组遍历生成导航链接，根据 `currentPage` 参数高亮当前页面

### 样式冲突修复
- `agent.html` 内嵌 `<style>` 标签中的 `pulse` 动画与 `style.css` 同名动画冲突
- 将内嵌动画重命名为 `agentPulse` 避免覆盖
- 清理 `agent.html` 中与 `style.css` 重复的样式规则

### 死代码清理
- 删除 `style.css` 中三套从未被触发的规则：`.fade-left`、`.fade-right`、`.fade-up.visible`
- 原因：JS 仅添加 `animate-in` 类，而 CSS 监听的是 `visible` 类，两者不匹配

### 响应式断点统一
- `trends.html` 时间线断点为 991.98px，`agent.html` 时间线断点为 768px
- 统一为 991.98px，避免 768~991px 区间内两个页面的时间线形态不一致

### 其他修复
- 修复 `index.html` 计数器初始值闪烁问题
- 统一 README 年份标注为 ©2026

## 📝 注意事项

- 本网站仅供学习交流使用
- 所有外部链接均指向第三方网站
- 图片和图标使用CDN资源

---

**© 2026 AI探索 - 人工智能主题网站**