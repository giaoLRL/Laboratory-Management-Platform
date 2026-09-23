'use strict';

const TASK_STATUSES = [
  ['todo', '待办'],
  ['doing', '进行中'],
  ['done', '已完成'],
];
const TASK_PRIORITIES = [
  ['low', '低'],
  ['normal', '普通'],
  ['high', '高'],
  ['urgent', '紧急'],
];

function taskPriorityColor(p) {
  return { low: '', normal: '', high: 'orange', urgent: 'red' }[p] || '';
}
function taskPriorityLabel(p) {
  return (TASK_PRIORITIES.find(([k]) => k === p) || ['', '普通'])[1];
}
function taskStatusLabel(s) {
  return (TASK_STATUSES.find(([k]) => k === s) || ['', s])[1];
}
function taskAssigneeName(id) {
  return member(id)?.name || '待分配';
}

function taskByStatus(status) {
  return (db.tasks || []).filter((t) => t.status === status);
}

function tasksPage() {
  const todo = taskByStatus('doing').length + taskByStatus('todo').length;
  const done = taskByStatus('done').length;
  const total = (db.tasks || []).length;
  return `${heading('任务看板', '把协作任务放进三列看板，让每一件事都知道去向。', btn(`${icon('plus')} 新建任务`, 'task-new', 'primary'), 'TASKS / 实验室看板')}<div class="stats">${statsCard('全部任务', total, '件', 'task', '', `<span>${todo} 件待推进</span>`)}${statsCard('已完成', done, '件', 'check', 'green', `<span>${Math.round(percentage(done, total))}% 完成率</span>`)}${statsCard('待办 / 进行中', todo, '件', 'clock', todo > 5 ? 'orange' : '', `<span>${taskByStatus('urgent')?.length || 0} 件紧急</span>`)}${statsCard('活跃成员', new Set((db.tasks || []).map((t) => t.assigneeId).filter(Boolean)).size, '人', 'users', 'purple', '<span>参与任务分配</span>')}</div><section class="panel task-board">${
    TASK_STATUSES.map(([key, label]) => {
      const col = taskByStatus(key).sort((a, b) => Date.parse(b.updated) - Date.parse(a.updated));
      return `<div class="task-col" data-status="${key}"><div class="task-col-head"><strong>${label}</strong><small>${col.length} 件</small></div><div class="task-col-body">${col.map(taskCard).join('') || empty(`暂无${label}任务`, '点击新建或从其他列移动。')}</div></div>`;
    }).join('')
  }</section>`;
}

function taskCard(t) {
  return `<article class="task-card" data-id="${esc(t.id)}"><div class="row between"><span class="mono" style="font-size:11px;color:#8992a4">${esc(t.id)}</span><span class="badge ${taskPriorityColor(t.priority)}">${taskPriorityLabel(t.priority)}</span></div><h4>${esc(t.title)}</h4>${t.description ? `<p class="muted small" style="line-height:1.6">${esc(t.description)}</p>` : ''}<div class="row between" style="margin-top:10px"><span class="small muted">${icon('users')} ${esc(taskAssigneeName(t.assigneeId))}</span>${t.due ? `<span class="small muted">${icon('clock')} ${fmt(t.due, true)}</span>` : ''}</div><div class="task-card-foot">${recordButton('移动', 'task-move', t.id)}${recordButton('编辑', 'task-edit', t.id)}${recordButton('删除', 'task-delete', t.id)}</div></article>`;
}

function taskForm(id) {
  const t = id ? (db.tasks || []).find((x) => x.id === id) : null;
  requirePermission(!id || t, '任务不存在');
  modal(
    id ? '编辑任务' : '新建任务',
    `<div class="form-grid">${field('任务标题 *', 'title', t?.title || '', 60)}${area('任务描述', 'description', t?.description || '', 500)}${selectField('看板列', 'status', TASK_STATUSES, t?.status || 'todo')}${selectField('优先级', 'priority', TASK_PRIORITIES, t?.priority || 'normal')}<div class="field"><label>截止时间</label><input type="datetime-local" name="due" value="${t?.due ? inputDate(t.due) : ''}"></div>${selectField(
      '负责人',
      'assigneeId',
      [['', '待分配'], ...db.members.filter((m) => m.active).map((m) => [m.id, m.name])],
      t?.assigneeId || '',
    )}</div>`,
    id ? '保存修改' : '创建任务',
    async (f) => {
      const data = Object.fromEntries(f);
      requirePermission(data.title && data.title.trim(), '请填写任务标题');
      const payload = {
        title: data.title.trim(),
        description: data.description,
        status: data.status,
        priority: data.priority,
        assigneeId: data.assigneeId || '',
        due: data.due ? new Date(data.due).toISOString() : null,
      };
      if (id) {
        await API.request(`/tasks/${id}/update`, { method: 'POST', body: JSON.stringify(payload) });
        audit(`更新任务 ${t.id} ${payload.title.slice(0, 20)}`);
      } else {
        await API.request('/tasks', { method: 'POST', body: JSON.stringify(payload) });
        audit(`创建任务 ${payload.title.slice(0, 20)}`);
      }
      await API.load();
      document.querySelector('#modal').close();
      render();
      toast(id ? '任务已更新' : '任务已创建');
    },
  );
}

function taskMove(id) {
  const t = (db.tasks || []).find((x) => x.id === id);
  requirePermission(t, '任务不存在');
  const next = TASK_STATUSES.map(([k, l]) => {
    const nxt = k === t.status ? null : k;
    return nxt ? `<option value="${k}">${l}</option>` : '';
  }).join('');
  modal(
    '移动任务到',
    `${details([['当前状态', taskStatusLabel(t.status)], ['任务', t.title]])}<div class="field" style="margin-top:18px"><label>目标列 *</label><select name="status">${next}</select></div>`,
    '确认移动',
    async (f) => {
      const status = f.get('status');
      requirePermission(status && status !== t.status, '请选择不同的目标列');
      await API.request(`/tasks/${id}/update`, { method: 'POST', body: JSON.stringify({ status }) });
      audit(`任务 ${t.id} 状态 → ${taskStatusLabel(status)}`);
      await API.load();
      document.querySelector('#modal').close();
      render();
      toast(`已移到「${taskStatusLabel(status)}」`);
    },
  );
}

function taskDeleteConfirm(id) {
  const t = (db.tasks || []).find((x) => x.id === id);
  requirePermission(t, '任务不存在');
  confirmation(
    '删除任务',
    `确认删除「${t.title}」？此操作不可恢复。`,
    '',
    {},
    async () => {
      await API.request(`/tasks/${id}/delete`, { method: 'POST', body: JSON.stringify({}) });
      audit(`删除任务 ${t.id} ${t.title.slice(0, 20)}`);
      await API.load();
      render();
    },
  );
}

// 把三个函数挂到全局给 app.js 和 FORM_ACTIONS 用
const TASK_ACTIONS = {
  'task-new': () => taskForm(null),
  'task-edit': taskForm,
  'task-move': taskMove,
  'task-delete': taskDeleteConfirm,
};
window.TASK_ACTIONS = TASK_ACTIONS;
window.tasksPage = tasksPage;
