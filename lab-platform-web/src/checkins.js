'use strict';

// ── 扫码签到 ────────────────────────────────────────────────────────────
// 成员用微信 / QQ「扫一扫」或手机相机扫实验室屏幕上的签到二维码，链接形如：
//   https://wuyuan.me/?c=ABCD1234#checkins
// 网页自己调不了摄像头（微信/QQ 内置浏览器不给 getUserMedia），所以扫码动作交给
// 外部扫码能力，平台只负责：接收 ?c= → 打卡时带上签到码 → 后端校验时间窗。
// 位置从"硬门槛"降级为可选信息（内置浏览器与国内桌面浏览器常常取不到）。
const CHECKIN_CODE_KEY = 'lab.checkin.code';
const CHECKIN_CODE_TTL = 15 * 60 * 1000; // 扫到的码最多在本地留 15 分钟（服务端窗口更短）

function _saveScanCode(code) {
  try {
    sessionStorage.setItem(CHECKIN_CODE_KEY, JSON.stringify({ code: String(code).toUpperCase(), at: Date.now() }));
  } catch (e) {
    /* 隐私模式写不了 sessionStorage：降级为手动输入 */
  }
}

function pendingScanCode() {
  try {
    const raw = sessionStorage.getItem(CHECKIN_CODE_KEY);
    if (!raw) return '';
    const saved = JSON.parse(raw);
    if (!saved || !saved.code || Date.now() - saved.at > CHECKIN_CODE_TTL) {
      sessionStorage.removeItem(CHECKIN_CODE_KEY);
      return '';
    }
    return saved.code;
  } catch (e) {
    return '';
  }
}

function clearScanCode() {
  try {
    sessionStorage.removeItem(CHECKIN_CODE_KEY);
  } catch (e) {
    /* 忽略 */
  }
}

// 读取扫码链接上的 ?c= 并存起来，同时抹掉地址栏参数（避免刷新或转发把旧码带出去）
function captureScanCode() {
  if (typeof location === 'undefined') return pendingScanCode();
  const hit = /[?&]c=([A-Za-z0-9]{4,16})/.exec(location.search || '');
  if (hit) {
    _saveScanCode(hit[1]);
    try {
      history.replaceState(null, '', location.pathname + location.hash);
    } catch (e) {
      /* 个别内置浏览器限制 replaceState：留着参数也不影响打卡 */
    }
  }
  return pendingScanCode();
}

let _lastGps = null;

function _position(pos) {
  return { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
}

// 位置（可选）：先试高精度 8s，失败再退到网络定位 15s；两段都失败也不阻断打卡。
function getLocation() {
  return new Promise((resolve, reject) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      reject(new Error('当前浏览器不支持定位'));
      return;
    }
    const ask = (high, done, failed) =>
      navigator.geolocation.getCurrentPosition(done, failed, {
        enableHighAccuracy: high,
        timeout: high ? 8000 : 15000,
        maximumAge: 10 * 60 * 1000,
      });
    ask(true, (pos) => resolve(_position(pos)), () =>
      ask(false, (pos) => resolve(_position(pos)), () => reject(new Error('未取到位置，不影响打卡'))),
    );
  });
}

function buildCheckinBody(photo, code, gps) {
  const form = new FormData();
  form.append('photo', photo);
  form.append('code', String(code || '').trim().toUpperCase());
  if (gps && gps.latitude != null && gps.longitude != null) {
    form.append('latitude', String(gps.latitude));
    form.append('longitude', String(gps.longitude));
  }
  return form;
}

function _placeText(c) {
  return c.latitude != null && c.longitude != null
    ? `📍 ${c.latitude.toFixed(4)}, ${c.longitude.toFixed(4)}`
    : '📍 未记录位置';
}

function checkinsPage() {
  const meId = me().id;
  const isStaff = canApprove() || can('page:members');
  const list = (db.checkins || [])
    .filter((c) => isStaff || c.memberId === meId)
    .filter(
      (c) =>
        !search ||
        matches(
          isStaff ? member(c.memberId)?.name || '' : '',
          c.latitude ?? '',
          c.longitude ?? '',
          fmt(c.created, true),
        ),
    )
    .filter((c) => !filter || c.memberId === filter)
    .sort((a, b) => Date.parse(b.created) - Date.parse(a.created));
  const p = paginate(list, typeof window !== 'undefined' && window.innerHeight < 800 ? 4 : 8);
  const today = new Date().toDateString();
  const checkedToday = list.some((c) => new Date(c.created).toDateString() === today && (isStaff || c.memberId === meId));
  /* 我自己的在席状态：onDuty 由后端按 signout_at 判定；签退后座位上的小人会消失 */
  const myToday = (db.checkins || []).find((c) => c.memberId === meId && new Date(c.created).toDateString() === today);
  const actionBtn = !myToday
    ? btn(`${icon('plus')} 立即打卡`, 'checkin-new', 'primary')
    : myToday.onDuty === true
      ? btn(`${icon('logout')} 下班签退`, 'checkin-signout')
      : btn(`${icon('check')} 今日已签退`, 'checkin-done');
  const qrBtn = can('action:checkin.qrcode') ? btn(`${icon('grid')} 签到二维码`, 'checkin-qr') : '';
  const scanned = pendingScanCode();
  return `<div class="page-fit">${heading('实验室打卡', '扫描实验室屏幕上的签到二维码 + 现场照片，签退后座位上的小人会消失。', qrBtn + actionBtn, 'CHECK-IN / 到场签到')}<div class="stats">${statsCard('累计打卡', list.length, '次', 'pin', '', `<span>${isStaff ? '全员记录' : '我的记录'}</span>`)}${statsCard('本月打卡', list.filter((c) => { const d = new Date(c.created); const now = new Date(); return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear(); }).length, '次', 'calendar', 'green', '<span>坚持到场</span>')}${statsCard('今日状态', checkedToday ? '已打卡' : '待打卡', '', 'check', checkedToday ? 'green' : 'orange', `<span>${checkedToday ? '可专注实验' : '点击上方按钮打卡'}</span>`)}${statsCard('签到码', scanned ? '已扫码' : '未扫码', '', 'grid', scanned ? 'green' : '', `<span>${scanned ? '可直接打卡' : '扫现场二维码获取'}</span>`)}</div><section class="panel"><div class="toolbar"><div class="search-field">${icon('search')}<input aria-label="搜索" id="search" placeholder="${isStaff ? '搜索成员、时间…' : '搜索时间…'}"></div>${isStaff ? `<select aria-label="成员筛选" id="filter">${options([...new Set(list.map((c) => c.memberId))].map((id) => [id, member(id)?.name || id]), '', '全部成员')}</select>` : ''}<button class="text-btn" data-action="checkin-refresh">刷新</button></div><div class="checkin-grid">${
    p.rows.length
      ? p.rows
          .map((c) => {
            const url = c.photo?.startsWith('/') ? c.photo : (c.photo ? '/' + c.photo : '');
            return `<figure class="checkin-card"><div class="checkin-photo" style="${url ? `background-image:url('${esc(url)}')` : ''}">${!url ? icon('pin') : ''}</div><figcaption><strong>${esc(isStaff ? member(c.memberId)?.name || c.memberId : '我')}</strong><small>${fmt(c.created, true)}</small><small class="muted">${_placeText(c)}</small></figcaption></figure>`;
          })
          .join('')
      : empty('暂无打卡记录', isStaff ? '今天大家还没开始。' : '今天还没打卡，扫码或点击上方按钮开始吧。')
  }</div>${p.footer}</section><p class="privacy-note">扫码签到：扫实验室屏幕上的二维码（或手动输入 8 位签到码）+ 现场照片，单用户每天限一次；位置为可选信息，取不到不影响打卡。管理角色可以查看全员打卡记录和照片。</p></div>`;
}

async function checkinNow() {
  _lastGps = null;
  const scanned = pendingScanCode();
  const codeStatus = scanned
    ? `<div class="gps-status ok">${icon('check')}<span>已扫码：<b class="mono">${esc(scanned)}</b></span></div>`
    : `<div class="gps-status">${icon('grid')}<span>还没扫码：请扫实验室屏幕上的二维码，或手动输入 8 位签到码</span></div>`;
  modal(
    '实验室打卡',
    `<div class="notice">用微信 / QQ 的「扫一扫」或手机相机扫描实验室屏幕上的签到二维码，再拍一张现场照片。位置是可选信息，取不到也能打卡。</div><div class="field" style="margin-bottom:16px"><label>签到码 *</label>${codeStatus}<input name="code" id="checkin-code" value="${esc(scanned)}" maxlength="8" autocomplete="off" spellcheck="false" placeholder="8 位签到码" style="margin-top:8px;text-transform:uppercase"></div><div class="field" style="margin-bottom:16px"><label>现场照片 *（≤ 8MB）</label><input type="file" name="photo" id="checkin-photo" accept="image/*" capture="environment" required></div><div class="field"><label>位置（可选）</label><div id="gps-status" class="gps-status">${icon('clock')}<span>正在尝试获取…</span></div></div>`,
    '确认打卡',
    async (f) => {
      const photo = f.get('photo') || document.querySelector('#checkin-photo')?.files?.[0];
      requirePermission(photo && photo.name, '请选择现场照片');
      requirePermission(photo.size <= 8 * 1024 * 1024, '照片不能超过 8MB');
      const code = String(f.get('code') || '').trim();
      requirePermission(code, '请先扫描现场二维码，或手动输入签到码');
      await API.request('/checkins', { method: 'POST', body: buildCheckinBody(photo, code, _lastGps) });
      clearScanCode();
      audit(_lastGps ? `扫码打卡 · ${_lastGps.latitude.toFixed(4)}, ${_lastGps.longitude.toFixed(4)}` : '扫码打卡');
      await API.load();
      document.querySelector('#modal')?.close();
      render();
      toast('打卡成功');
    },
  );
  // 位置异步获取，不阻塞弹窗；失败只提示，不影响提交
  getLocation()
    .then((gps) => {
      _lastGps = gps;
      const el = document.querySelector('#gps-status');
      if (el) {
        el.innerHTML = `${icon('check')}<span>已记录位置：${gps.latitude.toFixed(4)}, ${gps.longitude.toFixed(4)}</span>`;
        el.classList.add('ok');
      }
    })
    .catch((err) => {
      const el = document.querySelector('#gps-status');
      if (el) {
        el.innerHTML = `${icon('close')}<span>${esc(err.message)}</span>`;
        el.classList.add('err');
      }
    });
}

// 扫了码但还没登录：登录成功后自动接着完成打卡
function maybeOpenScannedCheckin() {
  const code = pendingScanCode();
  if (!code || !me() || !can('action:checkin.create')) return;
  // 有强制弹窗（完善资料 / 首次改密）时先让路，码留着，打完卡页点按钮仍会自动带入
  if (document.querySelector('#modal')?.open) return;
  const today = new Date().toDateString();
  const mine = (db.checkins || []).find((c) => c.memberId === me().id && new Date(c.created).toDateString() === today);
  go('checkins');
  if (mine) {
    clearScanCode();
    toast(mine.onDuty ? '今天已经打卡过了，明天再来' : '今天已签退，明天再来');
    return;
  }
  checkinNow();
}

// ── 管理端：实验室屏幕上的签到二维码（全屏展示 + 到点自动换码）──
let _qrTimer = null;
let _qrLeft = 0;

async function checkinQrBoard() {
  const d = document.createElement('dialog');
  d.className = 'qr-board';
  d.setAttribute('aria-label', '实验室签到二维码');
  d.innerHTML = `<div class="qr-board-inner"><div class="qr-board-head"><div><h2>实验室签到二维码</h2><p class="muted">成员用微信 / QQ「扫一扫」或手机相机扫描；也可以手动输入下方 8 位签到码。</p></div><button class="icon-btn" data-action="checkin-qr-close" aria-label="关闭二维码">${icon('close')}</button></div><div class="qr-board-body"><div class="qr-holder">${icon('clock')}<span class="muted">加载中…</span></div><div class="qr-code-text"><span class="mono" id="qr-code-value">————</span><small id="qr-countdown">正在取码…</small></div></div></div>`;
  d.addEventListener('close', () => {
    if (_qrTimer) {
      clearInterval(_qrTimer);
      _qrTimer = null;
    }
    d.remove();
  });
  document.body.append(d);
  d.showModal();
  await _qrRefresh();
  _qrTimer = setInterval(_qrTick, 1000);
}

async function _qrRefresh() {
  try {
    const info = await API.request('/checkins/code');
    _qrLeft = info.secondsLeft;
    const holder = document.querySelector('.qr-holder');
    if (holder) holder.innerHTML = `<img src="${esc(info.qr)}" alt="签到二维码">`;
    const value = document.querySelector('#qr-code-value');
    if (value) value.textContent = info.code;
  } catch (e) {
    _qrLeft = 15;
    const holder = document.querySelector('.qr-holder');
    if (holder) holder.innerHTML = `<span class="muted">${esc(e.message || '取码失败')}</span>`;
  }
}

function _qrTick() {
  _qrLeft -= 1;
  const el = document.querySelector('#qr-countdown');
  if (_qrLeft <= 0) {
    if (el) el.textContent = '正在换码…';
    _qrRefresh();
    return;
  }
  if (el) el.textContent = `${_qrLeft} 秒后自动换码`;
}

function checkinQrClose() {
  const d = document.querySelector('.qr-board');
  if (d) d.close();
}

async function checkinSignout() {
  modal(
    '下班签退',
    '<p style="line-height:1.9;font-size:13px">签退后今天不能再打卡，你在实验室座位图上的小人会立刻消失。确定离开实验室吗？</p>',
    '确认签退',
    async () => {
      await API.request('/checkins/signout', { method: 'POST' });
      audit('签退 · 离开实验室');
      await API.load();
      document.querySelector('#modal')?.close();
      render();
      toast('已签退，座位上的小人已消失');
    },
  );
}

async function checkinRefresh() {
  await API.load();
  render();
  toast('已刷新');
}

window.checkinsPage = checkinsPage;
window.captureScanCode = captureScanCode;
window.maybeOpenScannedCheckin = maybeOpenScannedCheckin;
window.CHECKIN_ACTIONS = {
  'checkin-new': checkinNow,
  'checkin-signout': checkinSignout,
  'checkin-done': () => toast('今天已签退，明天再来'),
  'checkin-refresh': checkinRefresh,
  'checkin-qr': checkinQrBoard,
  'checkin-qr-close': checkinQrClose,
};