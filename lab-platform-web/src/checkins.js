'use strict';

let _lastGps = null;

async function getLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('浏览器不支持定位'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      (err) => reject(new Error('定位失败：' + (err.message || '请检查定位权限'))),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
    );
  });
}

function checkinsPage() {
  const meId = me().id;
  const isStaff = canApprove() || can('page:members');
  const list = (db.checkins || [])
    .filter((c) => isStaff || c.memberId === meId)
    .sort((a, b) => Date.parse(b.created) - Date.parse(a.created));
  const p = paginate(list, typeof window !== 'undefined' && window.innerHeight < 800 ? 4 : 8);
  const today = new Date().toDateString();
  const checkedToday = list.some((c) => new Date(c.created).toDateString() === today && (isStaff || c.memberId === meId));
  return `<div class="page-fit">${heading('实验室打卡', '到实验室现场签到，让在线状态更准确。', !checkedToday ? btn(`${icon('plus')} 立即打卡`, 'checkin-new', 'primary') : btn(`${icon('check')} 今日已打卡`, 'checkin-done'), 'CHECK-IN / 到场签到')}<div class="stats">${statsCard('累计打卡', list.length, '次', 'pin', '', `<span>${isStaff ? '全员记录' : '我的记录'}</span>`)}${statsCard('本月打卡', list.filter((c) => { const d = new Date(c.created); const now = new Date(); return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear(); }).length, '次', 'calendar', 'green', '<span>坚持到场</span>')}${statsCard('今日状态', checkedToday ? '已打卡' : '待打卡', '', 'check', checkedToday ? 'green' : 'orange', `<span>${checkedToday ? '可专注实验' : '点击上方按钮打卡'}</span>`)}${statsCard('定位精度', _lastGps ? '已获取' : '待获取', '', 'wifi', _lastGps ? 'green' : '', '<span>GPS + 现场照片</span>')}</div><section class="panel"><div class="toolbar"><div class="search-field">${icon('search')}<input aria-label="搜索" id="search" placeholder="${isStaff ? '搜索成员、时间…' : '搜索时间…'}"></div>${isStaff ? `<select aria-label="成员筛选" id="filter">${options([...new Set(list.map((c) => c.memberId))].map((id) => [id, member(id)?.name || id]), '', '全部成员')}</select>` : ''}<button class="text-btn" data-action="checkin-refresh">刷新</button></div><div class="checkin-grid">${
    p.rows.length
      ? p.rows
          .map((c) => {
            const url = c.photo?.startsWith('/') ? c.photo : (c.photo ? '/' + c.photo : '');
            return `<figure class="checkin-card"><div class="checkin-photo" style="${url ? `background-image:url('${esc(url)}')` : ''}">${!url ? icon('pin') : ''}</div><figcaption><strong>${esc(isStaff ? member(c.memberId)?.name || c.memberId : '我')}</strong><small>${fmt(c.created, true)}</small><small class="muted">📍 ${c.latitude?.toFixed(4) || '—'}, ${c.longitude?.toFixed(4) || '—'}</small></figcaption></figure>`;
          })
          .join('')
      : empty('暂无打卡记录', isStaff ? '今天大家还没开始。' : '今天还没打卡，点击上方按钮开始吧。')
  }</div>${p.footer}</section><p class="privacy-note">打卡需要 GPS 定位授权 + 现场照片，单用户每天限一次。管理角色可以查看全员打卡记录和照片。</p></div>`;
}

async function checkinNow() {
  modal(
    '实验室打卡',
    `<div class="notice">请在实验室现场完成打卡。需要定位权限和现场照片。</div><div class="field" style="margin-bottom:18px"><label>定位状态</label><div id="gps-status" class="gps-status">${icon('wifi')}<span>正在获取 GPS…</span></div></div><div class="field"><label>现场照片 *（≤ 8MB）</label><input type="file" id="checkin-photo" name="photo" accept="image/*" capture="environment" required></div>`,
    '确认打卡',
    async (f) => {
      const photo = f.get('photo') || document.querySelector('#checkin-photo')?.files?.[0];
      requirePermission(photo && photo.name, '请选择现场照片');
      requirePermission(photo.size <= 8 * 1024 * 1024, '照片不能超过 8MB');
      const gps = _lastGps || (await getLocation());
      const form = new FormData();
      form.append('photo', photo);
      form.append('latitude', String(gps.latitude));
      form.append('longitude', String(gps.longitude));
      await API.request('/checkins', { method: 'POST', body: form });
      audit(`打卡 · ${gps.latitude.toFixed(4)}, ${gps.longitude.toFixed(4)}`);
      await API.load();
      document.querySelector('#modal')?.close();
      render();
      toast('打卡成功');
    },
  );
  // 异步获取 GPS，不阻塞 modal 打开
  getLocation()
    .then((gps) => {
      _lastGps = gps;
      const el = document.querySelector('#gps-status');
      if (el) {
        el.innerHTML = `${icon('check')}<span>已定位：${gps.latitude.toFixed(4)}, ${gps.longitude.toFixed(4)}</span>`;
        el.classList.add('ok');
      }
    })
    .catch((err) => {
      const el = document.querySelector('#gps-status');
      if (el) {
        el.innerHTML = `${icon('close')}<span style="color:#d28370">${err.message}</span>`;
        el.classList.add('err');
      }
    });
}

async function checkinRefresh() {
  await API.load();
  render();
  toast('已刷新');
}

window.checkinsPage = checkinsPage;
window.CHECKIN_ACTIONS = {
  'checkin-new': checkinNow,
  'checkin-done': () => toast('今天已打卡，明天再来'),
  'checkin-refresh': checkinRefresh,
};
