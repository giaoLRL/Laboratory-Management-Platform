'use strict';

// 智能体页面独立状态：不依赖 db workspace snapshot
let _agentConvs = []; // [{id, title, created, updated}]
let _agentActiveId = null;
let _agentMessages = []; // [{role, content}] 无会话时用临时 id

async function _agentLoadConvs() {
  _agentConvs = await API.request('/agent/conversations');
  _agentConvs.sort((a, b) => Date.parse(b.updated) - Date.parse(a.updated));
}
async function _agentLoadConv(cid) {
  const data = await API.request(`/agent/conversations/${cid}`);
  _agentMessages = data.messages || [];
  _agentActiveId = cid;
}

function agentMarkdown(text) {
  // 极简 markdown：```code```、**bold**、`code`、\n → <br>
  const escaped = esc(text);
  return escaped
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="agent-pre"><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code class="agent-inline">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

function agentPage() {
  if (!_agentConvs || _agentConvs._loading) {
    return `${heading('智能体助手', '正在加载…', '', 'AGENT / AI 助手')}<section class="panel"><div class="empty">${icon('chat')}<strong>加载中…</strong>如果长时间卡住，请检查后端是否配置了 LAB_LLM_API_KEY</div></section>`;
  }
  if (_agentConvs._error) {
    return `${heading('智能体助手', '还没配置 LLM，设置 LAB_LLM_API_KEY 后即可使用。', '', 'AGENT / AI 助手')}<section class="panel"><div class="empty">${icon('chat')}<strong>智能体未配置</strong>${esc(_agentConvs._error)}</div></section>`;
  }
  if (_agentActiveId && !_agentConvs.find((c) => c.id === _agentActiveId)) {
    _agentActiveId = null;
    _agentMessages = [];
  }
  const activeConv = _agentConvs.find((c) => c.id === _agentActiveId);
  return `${heading('智能体助手', '问它实验室任何事——库存、借用、成员、任务。', btn(`${icon('plus')} 新对话`, 'agent-new', 'primary'), 'AGENT / AI 助手')}<section class="agent-shell"><aside class="agent-sidebar"><header class="agent-sidebar-head"><div>${icon('chat')}<strong>对话历史</strong></div><button class="text-btn" data-action="agent-new">+ 新对话</button></header><div class="agent-conv-list">${
    _agentConvs.length
      ? _agentConvs.map((c) => `<button class="agent-conv-item ${c.id === _agentActiveId ? 'active' : ''}" data-action="agent-open" data-id="${esc(c.id)}"><strong>${esc(c.title)}</strong><small>${fmt(c.updated, true)}</small></button>`).join('')
      : empty('还没有对话', '点击上方新对话开始吧。')
  }</div></aside><main class="agent-main">${activeConv ? `<div class="agent-chat-head"><strong>${esc(activeConv.title)}</strong><small class="mono muted">${esc(activeConv.id)}</small></div>` : '<div class="agent-chat-head"><strong>新对话</strong></div>'}<div class="agent-messages" id="agent-messages">${
    _agentMessages.length
      ? _agentMessages
          .map((m) => `<div class="agent-bubble ${m.role}"><div class="agent-bubble-head">${m.role === 'user' ? icon('user') : icon('chat')}${m.role === 'user' ? '你' : '智能体'}</div><div class="agent-bubble-body">${agentMarkdown(m.content)}</div></div>`)
          .join('')
      : `<div class="agent-welcome">${icon('chat')}<h3>你好！我是实验室智能体</h3><p>可以问我：</p><ul><li>📊 实验室有多少件空闲模块？</li><li>👤 XX 的归还时间是什么时候？</li><li>📋 今天有哪些待办任务？</li><li>🏢 实验室整体使用率如何？</li></ul></div>`
  }</div><form class="agent-input" id="agent-input-form"><textarea id="agent-input" name="message" placeholder="输入消息，Enter 发送 / Shift+Enter 换行" rows="2"></textarea><button type="submit" class="btn primary" id="agent-send">${icon('arrow')} 发送</button></form></main></section>`;
}

async function agentOpen(cid) {
  await _agentLoadConv(cid);
  render();
  requestAnimationFrame(() => {
    const el = document.querySelector('#agent-messages');
    if (el) el.scrollTop = el.scrollHeight;
  });
}

async function agentNew() {
  _agentActiveId = null;
  _agentMessages = [];
  render();
}

async function agentSend(form) {
  const input = document.querySelector('#agent-input');
  const message = (form?.get?.('message') || input?.value || '').trim();
  requirePermission(message, '请输入消息');
  _agentMessages.push({ role: 'user', content: message });
  render();
  const msgsEl = document.querySelector('#agent-messages');
  if (msgsEl) msgsEl.scrollTop = msgsEl.scrollHeight;
  const sendBtn = document.querySelector('#agent-send');
  if (sendBtn) {
    sendBtn.disabled = true;
    sendBtn.innerHTML = '思考中…';
  }
  try {
    const payload = { message };
    if (_agentActiveId) payload.conversationId = _agentActiveId;
    const resp = await API.request('/agent/chat', { method: 'POST', body: JSON.stringify(payload) });
    _agentActiveId = resp.conversationId;
    _agentMessages = resp.messages || _agentMessages;
    await _agentLoadConvs();
    render();
    const el2 = document.querySelector('#agent-messages');
    if (el2) el2.scrollTop = el2.scrollHeight;
  } catch (e) {
    _agentMessages.push({ role: 'assistant', content: '❌ ' + (e.message || '请求失败') });
    render();
  } finally {
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.innerHTML = `${icon('arrow')} 发送`;
    }
  }
}

// 注册到 FORM_ACTIONS 和 handleAction
window.agentPage = agentPage;
window.AGENT_ACTIONS = {
  'agent-new': agentNew,
  'agent-open': async (id) => { await agentOpen(id); return null; },
};

// init() 完成后自动预加载 agent 会话（等 API.load() 完成）
(async () => {
  // 等 init 的 DOMContentLoaded 执行完
  await new Promise((r) => setTimeout(r, 500));
  if (!me()) return;
  _agentConvs = { _loading: true };
  try {
    const list = await API.request('/agent/conversations');
    list.sort((a, b) => Date.parse(b.updated) - Date.parse(a.updated));
    _agentConvs = list;
  } catch (e) {
    _agentConvs = { _error: e.message || '加载失败' };
  }
  // 如果当前正在 agent 页面，刷新渲染
  if (view === 'agent') render();
})();

// 绑定 submit
document.addEventListener('submit', (e) => {
  if (e.target.id !== 'agent-input-form') return;
  e.preventDefault();
  agentSend(new FormData(e.target)).catch((err) => toast(err.message, true));
  e.target.reset();
});
// Enter 发送 / Shift+Enter 换行
document.addEventListener('keydown', (e) => {
  const t = e.target;
  if (t.id !== 'agent-input') return;
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    document.querySelector('#agent-input-form')?.requestSubmit();
  }
});
