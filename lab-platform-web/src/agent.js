'use strict';

// 智能体页面独立状态：不依赖 db workspace snapshot
let _agentConvs = []; // [{id, title, created, updated}]
let _agentActiveId = null;
let _agentMessages = []; // [{role, content}] 无会话时用临时 id
let _agentPending = null; // {name, summary} 待确认写操作
let _agentMemory = null; // [{key, value, updated}]

async function _agentLoadConvs() {
  _agentConvs = await API.request('/agent/conversations');
  _agentConvs.sort((a, b) => Date.parse(b.updated) - Date.parse(a.updated));
}
async function _agentLoadConv(cid) {
  const data = await API.request(`/agent/conversations/${cid}`);
  _agentMessages = data.messages || [];
  _agentActiveId = cid;
  _agentPending = data.pendingOp || null;
}
async function _agentLoadMemory() {
  if (!me()) return;
  try {
    _agentMemory = await API.request('/agent/memory');
  } catch (e) {
    _agentMemory = [];
  }
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
  const pending = _agentPending ? `<div class="agent-pending">${icon('shield')}<div><strong>待确认操作</strong><small>${esc(_agentPending.summary)}</small></div><div class="row" style="gap:8px">${btn('确认执行', 'agent-confirm', 'primary small')}${btn('取消', 'agent-cancel', 'small')}</div></div>` : '';
  const memoryBlock = `<section class="agent-memory"><header><strong>我的记忆</strong><button class="text-btn" data-action="memory-new">+ 添加</button></header><div class="agent-memory-list">${
    _agentMemory && _agentMemory.length
      ? _agentMemory
          .map((m) => `<span class="memory-chip" title="${esc(m.value)}">${esc(m.key)}<button class="icon-btn" data-action="memory-del" data-id="${esc(m.key)}" aria-label="删除 ${esc(m.key)}">${icon('close')}</button></span>`)
          .join('')
      : '<small class="muted">AI 可记住你的偏好。</small>'
  }</div></section>`;
  return `<div class="page-fit">${heading('智能体助手', `${can('action:agent.operate') ? '可查询，也能在你的确认下代建任务。' : '问它实验室任何事——库存、借用、成员、任务。'}`, btn(`${icon('plus')} 新对话`, 'agent-new', 'primary'), 'AGENT / AI 助手')}<section class="agent-shell"><aside class="agent-sidebar"><header class="agent-sidebar-head"><div>${icon('chat')}<strong>对话历史</strong></div><button class="text-btn" data-action="agent-new">+ 新对话</button></header><div class="agent-conv-list">${
    _agentConvs.length
      ? _agentConvs.map((c) => `<button class="agent-conv-item ${c.id === _agentActiveId ? 'active' : ''}" data-action="agent-open" data-id="${esc(c.id)}"><strong>${esc(c.title)}</strong><small>${fmt(c.updated, true)}</small></button>`).join('')
      : empty('还没有对话', '点击上方新对话开始吧。')
  }</div>${memoryBlock}</aside><main class="agent-main">${activeConv ? `<div class="agent-chat-head"><strong>${esc(activeConv.title)}</strong><small class="mono muted">${esc(activeConv.id)}</small></div>` : '<div class="agent-chat-head"><strong>新对话</strong></div>'}${pending}<div class="agent-messages" id="agent-messages">${
    _agentMessages.length
      ? _agentMessages
          .map((m) => `<div class="agent-bubble ${m.role}"><div class="agent-bubble-head">${m.role === 'user' ? icon('user') : icon('chat')}${m.role === 'user' ? '你' : '智能体'}</div><div class="agent-bubble-body">${agentMarkdown(m.content)}</div></div>`)
          .join('')
      : `<div class="agent-welcome">${icon('chat')}<h3>你好！我是实验室智能体</h3><p>可以问我：</p><ul><li>📊 实验室有多少件空闲模块？</li><li>👤 XX 的归还时间是什么时候？</li><li>📋 今天有哪些待办任务？</li>${can('action:agent.operate') ? '<li>➕ 帮我建一个任务：调试电机，我确认后执行</li>' : ''}</ul></div>`
  }</div><form class="agent-input" id="agent-input-form"><textarea id="agent-input" name="message" placeholder="输入消息，Enter 发送 / Shift+Enter 换行" rows="2"></textarea><button type="submit" class="btn primary" id="agent-send">${icon('arrow')} 发送</button></form></main></section></div>`;
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
    _agentPending = resp.pendingOp || null;
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

async function agentConfirm() {
  requirePermission(_agentActiveId, '请先发起对话');
  const resp = await API.request('/agent/confirm', { method: 'POST', body: JSON.stringify({ conversationId: _agentActiveId }) });
  _agentMessages = resp.messages || _agentMessages;
  _agentPending = null;
  render();
  toast(resp.message || '操作已执行');
}
async function agentCancel() {
  if (!_agentActiveId) return;
  await API.request('/agent/cancel', { method: 'POST', body: JSON.stringify({ conversationId: _agentActiveId }) });
  _agentPending = null;
  render();
  toast('已取消待确认操作');
}
function memoryNew() {
  modal(
    '添加个人记忆',
    `<div class="form-grid">${field('记忆标签 *', 'key', '', 'text', 'placeholder="例如：direction、常用设备"')}${field('记忆内容 *', 'value', '', 'text', 'placeholder="例如：STM32 / ROS2"')}</div><p class="privacy-note">记忆仅对你可见，智能体对话时会参考它来个性化回答。</p>`,
    '保存',
    async (f) => {
      const key = (f.get('key') || '').trim();
      const value = (f.get('value') || '').trim();
      requirePermission(key && value, '请填写标签与内容');
      await API.request('/agent/memory/set', { method: 'POST', body: JSON.stringify({ key, value }) });
      await _agentLoadMemory();
      document.querySelector('#modal')?.close();
      render();
      toast('记忆已保存');
    },
  );
}
async function memoryDel(key) {
  await API.request('/agent/memory/delete', { method: 'POST', body: JSON.stringify({ key }) });
  await _agentLoadMemory();
  render();
  toast('记忆已删除');
}

// 注册到 FORM_ACTIONS 和 handleAction
window.agentPage = agentPage;
window.AGENT_ACTIONS = {
  'agent-new': agentNew,
  'agent-open': async (id) => { await agentOpen(id); return null; },
  'agent-confirm': agentConfirm,
  'agent-cancel': agentCancel,
  'memory-new': memoryNew,
  'memory-del': memoryDel,
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
  _agentLoadMemory().then(() => {
    if (view === 'agent') render();
  });
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
