'use strict';
// 邮件提醒：SMTP 配置 + 规则模板 + 发送日志。发送由后端 cron (send_reminders) 与审批回执触发。

const EMAIL_RULE_META = {
  task_due: { label: '任务临近截止', hint: '任务截止前 {hours} 小时提醒负责人' },
  task_assigned: { label: '任务指派', hint: '指派/转派任务时即时发送通知邮件' },
  loan_overdue: { label: '借用已逾期', hint: '借用超过预计归还时间后每日提醒' },
  competition_deadline: { label: '比赛报名截止', hint: '报名截止前 {hours} 小时提醒全体成员' },
  competition_start: { label: '比赛开赛提醒', hint: '开赛前 {hours} 小时提醒全体成员' },
  leave_result: { label: '请假审批结果', hint: '审批通过/拒绝时即时发送回执' },
  loan_reviewed: { label: '借用审批结果', hint: '审批通过/拒绝时即时发送回执' },
  loan_issued: { label: '借用发放', hint: '确认发放时即时发送回执' },
  asset_repaired: { label: '维修完成', hint: '维修完成时即时通知管理人员' },
  custom: { label: '自定义', hint: '预留规则，可在模板中自行编写' },
};
const EMAIL_INSTANT_RULES = ['leave_result', 'loan_reviewed', 'loan_issued', 'asset_repaired', 'task_assigned'];

let _emailCfg = null;
let _emailRules = null;
let _emailLogs = null;

function _mockCfg() {
  return { smtpHost: '', smtpPort: 465, smtpUser: '', passwordSet: false, fromAddr: '', useSsl: true, enabled: false };
}
function _mockRules() {
  return Object.entries(EMAIL_RULE_META).map(([key, meta]) => ({
    key, label: meta.label, enabled: false, hoursBefore: 24, subjectTpl: '', bodyTpl: '',
  }));
}

async function ensureEmail(kind) {
  if (kind === 'cfg' && _emailCfg) return;
  if (kind === 'rules' && _emailRules) return;
  if (kind === 'logs' && _emailLogs) return;
  try {
    if (kind === 'cfg') _emailCfg = CONFIG.mode === 'api' ? await API.request('/email/config') : _mockCfg();
    if (kind === 'rules') _emailRules = CONFIG.mode === 'api' ? await API.request('/email/rules') : _mockRules();
    if (kind === 'logs') _emailLogs = CONFIG.mode === 'api' ? await API.request('/email/logs') : [];
  } catch (e) {
    if (kind === 'cfg') _emailCfg = _mockCfg();
    if (kind === 'rules') _emailRules = _mockRules();
    if (kind === 'logs') _emailLogs = [];
  }
  render();
}

function emailPage() {
  ensureEmail('cfg');
  ensureEmail('rules');
  ensureEmail('logs');
  const canManage = can('action:email.manage');
  const head = heading('邮件提醒', '配置 SMTP 并设定提醒规则，临期任务、逾期借用与比赛报名自动发信。', canManage ? btn(`${icon('refresh')} 刷新`, 'email-refresh') : '', 'EMAIL / 通知中心');
  if (!_emailCfg || !_emailRules) return `${head}<section class="panel"><div class="empty">${icon('clock')}加载中…</div></section>`;
  const f = _emailCfg;
  const cfgCard = `<section class="panel"><div class="panel-head"><div><h2>SMTP 配置</h2><p>阿里云 ECS 默认屏蔽 25 端口，请使用 465/SSL</p></div>${canManage ? btn('保存配置', 'email-save-config', 'primary') : ''}</div><div class="panel-body"><div class="form-grid">${field('服务器地址', 'smtpHost', f.smtpHost || '', 'text', 'placeholder="smtp.example.com"')}${field('端口', 'smtpPort', f.smtpPort || 465, 'number')}${field('账号', 'smtpUser', f.smtpUser || '', '', 'autocomplete="off"')}${field(f.passwordSet ? '密码（留空不改）' : '密码', 'password', '', 'password', 'autocomplete="new-password"')}${field('发件人地址', 'fromAddr', f.fromAddr || '', 'email')}<div class="field"><label>加密方式</label><select name="useSsl"><option value="1" ${f.useSsl ? 'selected' : ''}>SSL（推荐）</option><option value="0" ${!f.useSsl ? 'selected' : ''}>STARTTLS</option></select></div><label class="check-label" style="align-self:end"><input type="checkbox" name="enabled" ${f.enabled ? 'checked' : ''}> 启用发送</label></div><p class="privacy-note">密码使用签名加密保存，不落明文。保存时可勾选“发送测试邮件”验证配置。</p></div></section>`;
  const rulesCard = `<section class="panel"><div class="panel-head"><div><h2>提醒规则</h2><p>模板占位符：{name} 姓名 · {title} 标题 · {due} 时间 · {result} 审批结果</p></div>${canManage ? btn('保存规则', 'email-save-rules', 'primary') : ''}</div><div class="panel-body rule-list">${_emailRules
    .map(
      (r) => `<div class="rule-editor"><div class="row between"><div><strong>${esc(r.label)}</strong><small class="muted">${(EMAIL_RULE_META[r.key]?.hint || '').replace('{hours}', r.hoursBefore)}</small></div><label class="check-label"><input type="checkbox" class="er-enable" data-key="${esc(r.key)}" ${r.enabled ? 'checked' : ''}> 启用</label></div><div class="form-grid" style="margin-top:10px">${EMAIL_INSTANT_RULES.includes(r.key) ? '<div class="field"><label>&nbsp;</label><div class="small muted" style="padding-top:8px">即时发送</div></div>' : `<div class="field"><label>提前提醒（小时）</label><input type="number" class="er-hours" data-key="${esc(r.key)}" min="0" max="720" value="${r.hoursBefore}"></div>`}<div class="field ${EMAIL_INSTANT_RULES.includes(r.key) ? 'full' : ''}"><label>标题模板</label><input class="er-subject" data-key="${esc(r.key)}" value="${esc(r.subjectTpl)}" maxlength="200" placeholder="例如：任务【{title}】即将截止"></div></div><div class="field"><label>正文模板</label><textarea class="er-body" data-key="${esc(r.key)}" rows="2" maxlength="2000" placeholder="例如：{name}，你好…">${esc(r.bodyTpl)}</textarea></div></div>`,
    )
    .join('')}</div></section>`;
  const logsCard = `<section class="panel"><div class="panel-head"><div><h2>发送日志</h2><p>最近 100 条发送结果</p></div><button class="text-btn" data-action="email-refresh">刷新</button></div><div class="panel-body full-log">${
    _emailLogs.length
      ? _emailLogs
          .map(
            (l) => `<div class="activity-item"><strong>${esc(l.recipient)}</strong> · ${esc(l.subject || l.ruleKey)}${l.ok ? '' : `<b style="color:#d28370"> · 失败：${esc(l.error || '')}</b>`}<small>${new Date(l.sentAt).toLocaleString('zh-CN')}</small></div>`,
          )
          .join('')
      : `<div class="empty small">${icon('mail')}暂无发送记录</div>`
  }</div></section>`;
  const testBtn = canManage ? `<label class="check-label" style="margin-top:10px"><input type="checkbox" id="email-send-test"> 保存并发送测试邮件</label>` : '';
  const noEmail = (db.members || []).filter((m) => m.active && !m.email).length;
  const tip = noEmail ? `<div class="notice">${icon('bell')} 有 ${noEmail} 位在职成员尚未填写邮箱，不会收到提醒邮件。请成员在"个人中心"或管理员在"成员管理"中补填。</div>` : '';
  const cfgTab = () => cfgCard + testBtn;
  const rulesTab = () => rulesCard;
  const logsTab = () => logsCard;
  return `<div class="page-fit">${head}${tip}${uiTab('email', [
    ['cfg', 'SMTP 配置', cfgTab],
    ['rules', '提醒规则', rulesTab],
    ['logs', '发送日志', logsTab],
  ])}</div>`;
}

function _readRuleForm() {
  return (_emailRules || []).map((r) => ({
    key: r.key,
    enabled: !!document.querySelector(`.er-enable[data-key="${r.key}"]`)?.checked,
    hoursBefore: Number(document.querySelector(`.er-hours[data-key="${r.key}"]`)?.value ?? r.hoursBefore),
    subjectTpl: document.querySelector(`.er-subject[data-key="${r.key}"]`)?.value ?? '',
    bodyTpl: document.querySelector(`.er-body[data-key="${r.key}"]`)?.value ?? '',
  }));
}

async function emailSaveConfig() {
  const q = (s) => document.querySelector(s)?.value ?? '';
  const payload = {
    smtpHost: q('[name="smtpHost"]').trim(),
    smtpPort: Number(q('[name="smtpPort"]')) || 465,
    smtpUser: q('[name="smtpUser"]').trim(),
    fromAddr: q('[name="fromAddr"]').trim(),
    useSsl: q('[name="useSsl"]') === '1',
    enabled: !!document.querySelector('[name="enabled"]')?.checked,
    sendTest: !!document.querySelector('#email-send-test')?.checked,
  };
  const pw = q('[name="password"]');
  if (pw) payload.password = pw;
  if (CONFIG.mode === 'api') {
    _emailCfg = await API.request('/email/config/save', { method: 'POST', body: JSON.stringify(payload) });
  } else {
    _emailCfg = { ..._emailCfg, ...payload, passwordSet: !!pw };
  }
  render();
  toast(payload.sendTest ? '配置已保存，测试邮件已发送（请在收件箱查收）' : '配置已保存');
}

async function emailSaveRules() {
  if (CONFIG.mode === 'api') {
    _emailRules = await API.request('/email/rules/save', { method: 'POST', body: JSON.stringify({ rules: _readRuleForm() }) });
  } else {
    _emailRules = _readRuleForm();
  }
  render();
  toast('提醒规则已保存');
}

const EMAIL_ACTIONS = {
  'email-refresh': () => {
    _emailCfg = _emailRules = _emailLogs = null;
    render();
  },
  'email-save-config': emailSaveConfig,
  'email-save-rules': emailSaveRules,
};
window.EMAIL_ACTIONS = EMAIL_ACTIONS;
window.emailPage = emailPage;