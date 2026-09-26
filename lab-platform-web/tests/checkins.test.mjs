// 扫码签到的纯前端逻辑：?c= 参数收集 / 本地码缓存 TTL / 打卡表单字段组装
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const scripts = [...html.matchAll(/<script defer src="([^"]+)"><\/script>/g)].map((match) => match[1]);
const source = scripts.map((path) => readFileSync(new URL('../' + path, import.meta.url), 'utf8'));

function setup() {
  const memory = new Map(),
    session = new Map(),
    replaced = [];
  const storage = (m) => ({
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
  });
  const context = vm.createContext({
    console,
    Date,
    Math,
    JSON,
    Promise,
    AbortController,
    FormData,
    TextEncoder,
    crypto: webcrypto,
    Uint8Array,
    setTimeout,
    clearTimeout,
    setInterval: () => {},
    localStorage: storage(memory),
    sessionStorage: storage(session),
    location: { search: '', pathname: '/login/', hash: '' },
    history: { replaceState: (state, title, url) => replaced.push(url) },
    document: {
      addEventListener() {},
      querySelector() {
        return { close() {}, open: false, innerHTML: '', append() {} };
      },
      createElement() {
        return { remove() {} };
      },
      body: { append() {} },
    },
    window: {
      addEventListener() {},
      scrollTo() {},
      matchMedia() {
        return { matches: false };
      },
    },
  });
  source.forEach((script) => vm.runInContext(script, context));
  const run = (code) => vm.runInContext(code, context);
  run("CONFIG.mode='mock';db=seed();sessionId='m1'");
  return { run, context, session, replaced };
}

test('扫码链接的 ?c= 会被收起并大写化，地址栏参数同时抹掉', () => {
  const { run, context, session, replaced } = setup();
  context.location.search = '?c=abc234';
  context.location.hash = '#checkins';
  assert.equal(run('captureScanCode()'), 'ABC234');
  assert.deepEqual([...session.keys()], ['lab.checkin.code']);
  assert.deepEqual(replaced, ['/login/#checkins']);
  // 同一会话内再打开打卡弹窗仍能取到
  assert.equal(run('pendingScanCode()'), 'ABC234');
});

test('没有扫码参数时不写缓存；缓存超过 TTL 自动失效并清除', () => {
  const { run, context, session } = setup();
  context.location.search = '';
  assert.equal(run('captureScanCode()'), '');
  assert.equal(session.size, 0);

  session.set('lab.checkin.code', JSON.stringify({ code: 'ABCD2345', at: Date.now() - 16 * 60 * 1000 }));
  assert.equal(run('pendingScanCode()'), '');
  assert.equal(session.has('lab.checkin.code'), false);
});

test('打卡表单：签到码统一大写去空格，只有拿到位置时才带坐标', () => {
  const { run } = setup();
  const body = (code, gps) => run(`buildCheckinBody('photo-blob', ${JSON.stringify(code)}, ${JSON.stringify(gps)})`);
  const located = body(' ab12cd34 ', { latitude: 26.45, longitude: 111.6 });
  assert.equal(located.get('code'), 'AB12CD34');
  assert.equal(located.get('photo'), 'photo-blob');
  assert.equal(located.get('latitude'), '26.45');
  assert.equal(located.get('longitude'), '111.6');

  const noGps = body('AB12CD34', null);
  assert.equal(noGps.get('latitude'), null);
  assert.equal(noGps.get('longitude'), null);
  assert.equal(noGps.get('code'), 'AB12CD34');
});