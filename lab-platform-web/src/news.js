'use strict';
// 实时动态：AI/具身智能领域资讯时间线（RSS 抓取/手动录入/LLM 摘要）。

let _newsCache = null;

const NEWS_SOURCE_LABEL = { manual: '手动', rss: 'RSS', llm: 'AI 摘要' };

function _mockNews() {
  const now = new Date();
  return [
    { id: 'NEWS-DEMO-1', title: '实验室入选校级大学生创新训练计划', source: '实验室动态', url: '', summary: '围绕具身智能方向开展项目研究，物联网/电子设计/智能导航三大方向同步推进。', publishedAt: new Date(now - 2 * 86400000).toISOString(), fetchSource: 'manual' },
    { id: 'NEWS-DEMO-2', title: '2026 年全国大学生电子设计竞赛校赛报名启动', source: '竞赛通知', url: '', summary: '有意参赛的同学请在报名截止前完成组队并提交项目方向。', publishedAt: new Date(now - 5 * 86400000).toISOString(), fetchSource: 'manual' },
  ];
}

async function ensureNews() {
  if (_newsCache) return;
  try {
    _newsCache = CONFIG.mode === 'api' ? await API.request('/news') : _mockNews();
  } catch (e) {
    _newsCache = [];
  }
  render();
}

function newsPage() {
  ensureNews();
  const canManage = can('action:news.manage');
  const head = heading('实时动态', '汇聚 AI 与具身智能领域资讯，跟进行业与技术前沿。', canManage ? btn(`${icon('plus')} 录入动态`, 'news-new', 'primary') + btn(`${icon('refresh')} 刷新`, 'news-refresh') : btn(`${icon('refresh')} 刷新`, 'news-refresh'), 'NEWS / 实时跟进');
  if (!_newsCache) return `${head}<section class="panel"><div class="empty">${icon('clock')}加载中…</div></section>`;
  const p = paginate(_newsCache, 5);
  const timeline = p.rows
    .map(
      (n) => `<article class="news-card"><div class="news-head"><div class="row" style="gap:8px"><span class="badge ${(NEWS_SOURCE_LABEL[n.fetchSource] === 'RSS' ? 'blue' : n.fetchSource === 'AI 摘要' ? 'purple' : 'green')}">${esc(NEWS_SOURCE_LABEL[n.fetchSource] || '动态')}</span>${n.source ? `<span class="muted small">${esc(n.source)}</span>` : ''}</div>${canManage ? recordButton('删除', 'news-delete', n.id) : ''}</div><h3>${n.url ? `<a href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">${esc(n.title)}</a>` : esc(n.title)}</h3>${n.summary ? `<p class="muted news-summary">${esc(n.summary)}</p>` : ''}<time class="muted small">${new Date(n.publishedAt).toLocaleString('zh-CN')}</time></article>`,
    )
    .join('');
  return `<div class="page-fit">${head}<section class="panel"><div class="news-timeline">${timeline || empty('暂无动态', '可通过 RSS 抓取或手动录入。')}</div>${p.footer}</section></div>`;
}

function newsNew() {
  modal(
    '录入动态',
    `<div class="form-grid">${field('标题 *', 'title', '', 80)}${field('来源', 'source', '', 40)}${field('原文链接', 'url', '', 'url', 'placeholder="https://…"')}${field('发布时间', 'publishedAt', inputDate(0, 9), 'datetime-local')}</div><div class="field" style="margin-top:14px"><label>摘要</label><textarea name="summary" maxlength="2000" style="min-height:100px"></textarea></div>`,
    '保存',
    async (f) => {
      const d = {
        title: f.get('title').trim(),
        source: f.get('source').trim(),
        url: f.get('url').trim(),
        summary: f.get('summary').trim(),
        publishedAt: f.get('publishedAt') ? new Date(f.get('publishedAt')).toISOString() : '',
      };
      requirePermission(d.title, '请填写标题');
      requirePermission(!d.url || isHttpURL(d.url), '链接只支持 http/https');
      await API.request('/news/create', { method: 'POST', body: JSON.stringify(d) });
      _newsCache = null;
      document.querySelector('#modal')?.close();
      render();
      toast('动态已录入');
    },
  );
}

async function newsDelete(id) {
  await API.request(`/news/${id}/delete`, { method: 'POST', body: '{}' });
  _newsCache = null;
  render();
  toast('动态已删除');
}

window.newsPage = newsPage;
window.NEWS_ACTIONS = {
  'news-new': newsNew,
  'news-delete': newsDelete,
  'news-refresh': () => { _newsCache = null; render(); },
};