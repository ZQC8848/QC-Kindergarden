// Story review page. Plain DOM, no build step; the server is tools/story_review/server.py.
// Model text is always inserted as text, never as HTML.

const $ = (sel, root = document) => root.querySelector(sel);

// ------------------------------------------------------------------ storage

const local = {
  get(key) {
    try {
      const v = localStorage.getItem(key);
      return v == null ? null : JSON.parse(v);
    } catch {
      return null;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* storage can be blocked; the choice then lasts until reload */
    }
  },
  drop(key) {
    try {
      localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
  },
};

// ------------------------------------------------------------------ language
// Fixed page text is written here in both languages. Story text and QC's notes are
// translated on demand through the server (see "translation" below).

const KEYS_ZH = [
  '快捷键：',
  ['0'],
  '–',
  ['9'],
  ' 打分，',
  ['='],
  ' 打 10 分，',
  ['n'],
  ' 写批注，',
  ['j'],
  ' / ',
  ['k'],
  ' 下一篇 / 上一篇，',
  ['Ctrl'],
  '+',
  ['Enter'],
  ' 提交，',
  ['Esc'],
  ' 离开输入框',
];
const KEYS_EN = [
  'Keys: ',
  ['0'],
  '–',
  ['9'],
  ' score, ',
  ['='],
  ' scores 10, ',
  ['n'],
  ' notes, ',
  ['j'],
  ' / ',
  ['k'],
  ' next / previous, ',
  ['Ctrl'],
  '+',
  ['Enter'],
  ' submit, ',
  ['Esc'],
  ' leave a field',
];

const I18N = {
  zh: {
    pageTitle: '故事评审 · QC Kindergarten',
    brand: '故事评审',
    connecting: '连接中',
    modeDry: '演练 · 临时副本 · 假模型',
    modeLive: '正式 · 生成会调用真实模型',
    storeTitle: '候选目录：{path}',
    langButton: 'EN',
    langAria: 'Switch to English',
    themeToDark: '夜间模式',
    themeToLight: '日间模式',
    filtersAria: '按去向筛选',
    filter: { all: '全部', pending: '待裁', selected: '选中', shortlisted: '候补', discarded: '丢弃' },
    progressLeft: '还有 {n} 篇待裁',
    progressDone: '全部裁完',
    capLabel: '字数上限',
    capMinAria: '字数上限的最小值',
    capMaxAria: '字数上限的最大值',
    chars: '字',
    generate: '生成下一轮',
    generating: '生成中…',
    willRewrite: '下一轮会带回 {n} 篇候补重写',
    blocked: '暂时不能生成：{why}',
    rangeError: '字数范围要满足 1 ≤ 最小 ≤ 最大 ≤ {max}',
    confirmLive: '会调用真实模型：一整轮新大纲{extra}。每个位子的上限在 {lo}–{hi} 字之间随机。继续吗？',
    confirmExtra: '，外加 {n} 篇候补重写',
    logPrevious: '上一次生成的日志',
    logRunning: '正在生成…',
    logFailed: '生成失败：{error}',
    logDone: '生成完成：{round}',
    hideLog: '收起',
    hideLogAria: '收起日志',
    empty1: '还没有候选故事。',
    empty2: '在右上角设好字数上限，点「生成下一轮」。',
    storiesN: '{n} 篇',
    pendingN: '待裁 {n}',
    judged: '已裁完',
    selectedN: '选中 {n}',
    shortlistedN: '候补 {n}',
    discardedN: '丢弃 {n}',
    capN: '上限 {n} 字',
    revealStats: '揭晓模型表现',
    hideStats: '收起模型表现',
    blind: '盲评中',
    blindTitle: '这一轮裁完之前，页面上不出现任何模型名',
    statsHead: ['模型', '选中', '按意见', '候补', '丢弃', '选中率', '平均分'],
    statsReasons: '丢弃理由：{list}',
    statsRewrites: '另有 {n} 篇重写稿不计入上表：重写的 brief 每篇都不同，不能和同位子的四个模型放在一起比。',
    listSep: '，',
    nameSep: '、',
    reasonSep: '；',
    castAria: '出场：{names}',
    noCast: '没有写出场角色',
    guest: '客串：{name}',
    kind: { memory: '记忆事件', extra: '番外' },
    waitlistTag: '候补回炉 · 第 {n} 次',
    waitlistTitle: '这条故事线已经重写 {n} 次，最多 {max} 次',
    reviseTag: '按意见重写',
    lengthTitle: '字数 / 这篇要求的上限',
    lengthOver: '超出了这篇要求的上限',
    length: '{words}/{cap} 字',
    broken: '输出无法解析',
    untitled: '（无标题）',
    selfNotes: '模型自述',
    nearest: '最近的同类',
    none: '无',
    quoteTitle: '《{title}》',
    rewrittenFrom: '改写自 {id}',
    historyRevise: '你选中了上一版，要求这样改：',
    historyWaitlist: '上一版进了候补，你的意见：',
    points: '{n} 分',
    prevVersion: '上一版「{title}」 · {words}/{cap} 字',
    parseNote: '模型的输出没能解析成完整故事，原始内容保留在候选文件里。',
    scoreLabel: '打分',
    reasonsAria: '丢弃理由，可多选',
    notes: '批注',
    rewriteCapAria: '改写稿的字数上限',
    rewriteCap: '重写上限',
    submit: '提交',
    submitting: '提交中…',
    notScored: '还没打分',
    needScore: '先打分：拖滑条，或按数字键',
    needWhyDiscard: '丢弃要写一句为什么',
    needWhyShortlist: '候补要写清楚好在哪、缺什么',
    hintRevise: '提交后立刻交回原模型重写，改写稿会出现在这篇下面',
    hintShortlist: '下一轮生成时由原模型照批注重写',
    capRange: '重写上限要在 1 到 {max} 之间',
    dest: {
      discarded: '→ 丢弃',
      shortlisted: '→ 候补 · 下一轮原模型重写',
      selected: '→ 选中',
      selected_with_notes: '→ 选中 · 立即按意见重写',
    },
    submitAs: { discarded: '丢弃', shortlisted: '放进候补', selected: '选中', selected_with_notes: '选中并重写' },
    notesHint: {
      discarded: '为什么丢？（必填）',
      shortlisted: '好在哪、缺什么？（必填）下一轮生成时，原模型会照这段重写',
      selected: '想改的地方（可选）。写了就会立刻交回原模型重写，改完再给你批',
    },
    verdict: {
      pending: '待裁',
      discarded: '丢弃',
      shortlisted: '候补',
      selected: '选中',
      selected_with_notes: '选中 · 待改',
    },
    why: '理由：{text}',
    notesIs: '批注：{text}',
    rewriteCapIs: '重写上限：{n} 字',
    rewriteArrived: '改写稿已到：',
    rewriting: '原模型正在按意见重写，改完会出现在这篇下面',
    rewriteFailed: '重写失败：{error}',
    rewriteMissing: '还没有改写稿（服务器可能在重写途中重启过）',
    retry: '重试',
    carriedOver: '已带进下一轮重写：',
    retiring: '这条故事线已经重写 {n} 次，下一轮生成时会退出候补',
    nextCap: '下一轮重写上限',
    nextCapAria: '下一轮重写的字数上限',
    between: '要在 1 到 {max} 之间',
    saving: '保存中…',
    saved: '已保存',
    originally: '原本 {n} 字',
    offline: '读不到本地服务器：{error}',
    reconnecting: '和本地服务器断开了，正在重连…',
    arrivals: '新到 {n} 篇 ↓',
    translating: '翻译中…',
    trFailed: '翻译不可用：{error}',
    inEnglish: '英文：',
    viewReview: '评审',
    viewTaste: '创作偏好',
    viewsAria: '切换页面',
    tasteTitle: '创作偏好 · QC taste',
    tasteIntro:
      '按领域拆分，中英两版。每个领域都和「共通」部分一起使用。这里只看不改：规则的修改走 qc-taste 的更新流程，需要你批准。',
    tasteTabsAria: '选择领域',
    tasteVersion: '版本 {version} · 证据截至 {date}',
    tasteUsedBy: '用在：{what}。',
    tasteWithShared: '使用时和「共通」部分一起读。',
    tasteSep: '',
    tasteMissingLang: '这一部分还没有{lang}版，下面显示的是{other}版。',
    tasteStamped: '上次确认一致：{date}',
    tasteFiles: '文件：',
    tasteLoading: '读取中…',
    langName: { en: '英文', zh: '中文' },
    keys: KEYS_ZH,
    locale: 'zh-CN',
  },
  en: {
    pageTitle: 'Story review · QC Kindergarten',
    brand: 'Story review',
    connecting: 'Connecting',
    modeDry: 'Dry run · scratch copy · stub models',
    modeLive: 'Live · generating calls the real models',
    storeTitle: 'Candidates: {path}',
    langButton: '中文',
    langAria: '切换到中文',
    themeToDark: 'Dark mode',
    themeToLight: 'Light mode',
    filtersAria: 'Filter by destination',
    filter: { all: 'All', pending: 'Pending', selected: 'Selected', shortlisted: 'Shortlist', discarded: 'Discarded' },
    progressLeft: '{n} left to judge',
    progressDone: 'All judged',
    capLabel: 'Length cap',
    capMinAria: 'Lowest cap',
    capMaxAria: 'Highest cap',
    chars: 'chars',
    generate: 'Generate next round',
    generating: 'Generating…',
    willRewrite: 'Next round also rewrites {n} from the shortlist',
    blocked: 'Cannot generate yet: {why}',
    rangeError: 'The range needs 1 ≤ lowest ≤ highest ≤ {max}',
    confirmLive:
      'This calls the real models: a full round of new outlines{extra}. Each slot draws a cap between {lo} and {hi} characters. Continue?',
    confirmExtra: ', plus {n} shortlist rewrites',
    logPrevious: 'Log of the last generation',
    logRunning: 'Generating…',
    logFailed: 'Generation failed: {error}',
    logDone: 'Generated {round}',
    hideLog: 'Hide',
    hideLogAria: 'Hide log',
    empty1: 'No candidate stories yet.',
    empty2: 'Set a length cap at the top right and press “Generate next round”.',
    storiesN: '{n} stories',
    pendingN: '{n} pending',
    judged: 'all judged',
    selectedN: '{n} selected',
    shortlistedN: '{n} shortlisted',
    discardedN: '{n} discarded',
    capN: 'cap {n} chars',
    revealStats: 'Reveal model results',
    hideStats: 'Hide model results',
    blind: 'Blind review',
    blindTitle: 'No model names appear on this page until the round is fully judged',
    statsHead: ['Model', 'Selected', 'With notes', 'Shortlist', 'Discarded', 'Accept rate', 'Avg score'],
    statsReasons: 'Discard reasons: {list}',
    statsRewrites:
      '{n} rewrites are left out of this table: every rewrite has its own brief, so they cannot be compared with the four models on a slot.',
    listSep: ', ',
    nameSep: ', ',
    reasonSep: '; ',
    castAria: 'Cast: {names}',
    noCast: 'No cast listed',
    guest: 'Guest: {name}',
    kind: { memory: 'Memory', extra: 'Side story' },
    waitlistTag: 'Shortlist rewrite · #{n}',
    waitlistTitle: 'This storyline has been rewritten {n} times, {max} at most',
    reviseTag: 'Rewritten with notes',
    lengthTitle: 'Characters / the cap this story was given',
    lengthOver: 'Over the cap this story was given',
    length: '{words}/{cap} chars',
    broken: 'Unparsable output',
    untitled: '(untitled)',
    selfNotes: "Model's own notes",
    nearest: 'Nearest story',
    none: 'none',
    quoteTitle: '“{title}”',
    rewrittenFrom: 'Rewrite of {id}',
    historyRevise: 'You selected the previous version and asked for:',
    historyWaitlist: 'The previous version was shortlisted. Your notes:',
    points: '{n} pts',
    prevVersion: 'Previous version “{title}” · {words}/{cap} chars',
    parseNote: "The model's output could not be parsed into a full story; the raw text is kept in the candidate file.",
    scoreLabel: 'Score',
    reasonsAria: 'Discard reasons, pick any',
    notes: 'Notes',
    rewriteCapAria: 'Cap for the rewrite',
    rewriteCap: 'Rewrite cap',
    submit: 'Submit',
    submitting: 'Submitting…',
    notScored: 'Not scored',
    needScore: 'Score it first: drag the slider or press a number',
    needWhyDiscard: 'Say why it goes',
    needWhyShortlist: 'Say what works and what is missing',
    hintRevise: 'Goes straight back to the same model; the rewrite appears below this story',
    hintShortlist: 'The same model rewrites it from these notes next round',
    capRange: 'The rewrite cap must be between 1 and {max}',
    dest: {
      discarded: '→ Discard',
      shortlisted: '→ Shortlist · rewritten next round',
      selected: '→ Select',
      selected_with_notes: '→ Select · rewrite now with notes',
    },
    submitAs: {
      discarded: 'Discard',
      shortlisted: 'Shortlist',
      selected: 'Select',
      selected_with_notes: 'Select and rewrite',
    },
    notesHint: {
      discarded: 'Why does it go? (required)',
      shortlisted: 'What works, what is missing? (required) The same model rewrites from this next round',
      selected: 'What to change (optional). Anything written here sends it straight back to the same model',
    },
    verdict: {
      pending: 'Pending',
      discarded: 'Discarded',
      shortlisted: 'Shortlist',
      selected: 'Selected',
      selected_with_notes: 'Selected · revising',
    },
    why: 'Reasons: {text}',
    notesIs: 'Notes: {text}',
    rewriteCapIs: 'Rewrite cap: {n} chars',
    rewriteArrived: 'Rewrite is in:',
    rewriting: 'The same model is rewriting this from your notes; the result appears below',
    rewriteFailed: 'Rewrite failed: {error}',
    rewriteMissing: 'No rewrite yet (the server may have restarted mid-rewrite)',
    retry: 'Retry',
    carriedOver: 'Carried into the next round:',
    retiring: 'Rewritten {n} times; it leaves the shortlist next round',
    nextCap: 'Next rewrite cap',
    nextCapAria: 'Cap for the next rewrite',
    between: 'Must be between 1 and {max}',
    saving: 'Saving…',
    saved: 'Saved',
    originally: 'was {n}',
    offline: 'Cannot reach the local server: {error}',
    reconnecting: 'Lost the local server, reconnecting…',
    arrivals: '{n} new ↓',
    translating: 'Translating…',
    trFailed: 'Translation unavailable: {error}',
    inEnglish: 'In English:',
    viewReview: 'Review',
    viewTaste: 'Taste',
    viewsAria: 'Switch page',
    tasteTitle: 'QC taste',
    tasteIntro:
      'Split by domain, kept in Chinese and English. Every domain is used together with the shared part. Read-only here: rule changes go through the qc-taste update protocol and need your approval.',
    tasteTabsAria: 'Choose a domain',
    tasteVersion: 'Version {version} · evidence through {date}',
    tasteUsedBy: 'Used by: {what}.',
    tasteWithShared: 'Read together with the shared part.',
    tasteSep: ' ',
    tasteMissingLang: 'This part has no {lang} version yet; showing the {other} one.',
    tasteStamped: 'Last confirmed to match: {date}',
    tasteFiles: 'Files: ',
    tasteLoading: 'Loading…',
    langName: { en: 'English', zh: 'Chinese' },
    keys: KEYS_EN,
    locale: 'en-US',
  },
};
I18N.zh.notesHint.selected_with_notes = I18N.zh.notesHint.selected;
I18N.en.notesHint.selected_with_notes = I18N.en.notesHint.selected;

let lang = local.get('story-review:lang') === 'en' ? 'en' : 'zh';

function t(key, vars) {
  let s = I18N[lang][key] ?? I18N.zh[key] ?? key;
  if (typeof s === 'string' && vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m));
  return s;
}

const FILTER_KEYS = ['all', 'pending', 'selected', 'shortlisted', 'discarded'];

let S = null; // last /api/state
const byId = new Map();
const cards = new Map(); // id -> { sig, el }
const sections = new Map(); // round id -> { el, head, tools, body, statsEl, statsOpen, isLatest }
const openRounds = new Set();
const closedRounds = new Set();
const drafts = new Map();
let sceneNames = new Map();
let filter = 'all';
let known = null; // ids already seen, so new arrivals can be announced
let current = null; // the card keyboard shortcuts act on
let arrivals = [];
let logOpen = false;
let view = 'review'; // 'review' | 'taste'
let T = null; // last /api/taste
let tasteTab = local.get('story-review:taste-tab') || 'story';

// ------------------------------------------------------------------ helpers

function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style') el.style.cssText = v;
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : String(v));
  }
  for (const kid of kids.flat(2)) {
    if (kid == null || kid === false || kid === '') continue;
    el.append(kid instanceof Node ? kid : String(kid));
  }
  return el;
}

function draft(id) {
  if (!drafts.has(id)) drafts.set(id, local.get(`story-review:draft:${id}`) || {});
  return drafts.get(id);
}
const saveDraft = (id) => local.set(`story-review:draft:${id}`, drafts.get(id));
function dropDraft(id) {
  drafts.delete(id);
  local.drop(`story-review:draft:${id}`);
}

const bandOf = (verdict) => (verdict === 'selected_with_notes' ? 'selected' : verdict);

function destination(score, notes) {
  if (score == null || !S) return null;
  const band = S.bands.find(([lo, hi]) => score >= lo && score <= hi);
  if (!band) return null;
  return band[2] === 'selected' && notes.trim() ? 'selected_with_notes' : band[2];
}

const reasonLabel = (k) => (lang === 'en' ? S.all_reasons_en : S.all_reasons)[k] || k;

function reasonText(c) {
  const keys = c.reasons && c.reasons.length ? c.reasons : c.reason ? [c.reason] : [];
  return keys.map(reasonLabel).join(t('reasonSep'));
}

function sceneName(loc) {
  const key = String(loc)
    .replace(/\.[a-z0-9]+$/i, '')
    .toLowerCase();
  return sceneNames.get(key) || loc;
}

const slotName = (slot) => (lang === 'en' ? S.slots_en : S.slots)[slot] || slot;

function charName(slug) {
  const ch = S.characters[slug];
  if (!ch) return tx(String(slug));
  return lang === 'en' ? ch.name_en || ch.name : ch.name;
}

function storyTitle(slug) {
  const zh = S.stories[slug];
  if (lang !== 'en') return zh;
  return S.stories_en[slug] || (zh ? tx(zh) : null);
}

const fieldLabel = (f) => (lang === 'en' ? f.label_en || f.label || f.key : f.label || f.key);

function fmtTime(s) {
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString(t('locale'), { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function waitlistCount() {
  return S.candidates.filter((c) => c.verdict === 'shortlisted' && !c.rewritten_as && c.revisit_count < S.max_revisits)
    .length;
}

// The slider track shows the bands, lined up with where the thumb sits for each score.
function trackGradient() {
  const [min, max] = S.score_range;
  const at = (v) => `calc(10px + (100% - 20px) * ${((v - min) / (max - min)).toFixed(4)})`;
  const stops = S.bands.map(([lo, hi, verdict], i) => {
    const start = i === 0 ? '0%' : at(lo - 0.5);
    const end = i === S.bands.length - 1 ? '100%' : at(hi + 0.5);
    return `var(--band-${verdict}) ${start} ${end}`;
  });
  return `linear-gradient(to right, ${stops.join(', ')})`;
}

async function api(path, body) {
  const headers = { 'X-Lang': lang };
  const init = { headers };
  if (body !== undefined) {
    init.method = 'POST';
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  const res = await fetch(path, init);
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok || (data && data.ok === false)) throw new Error((data && data.error) || `${res.status} ${res.statusText}`);
  return data;
}

// ------------------------------------------------------------------ translation
// In English mode, text containing Chinese goes to /api/translate; the server calls Google
// and caches. Until a translation arrives the original shows, then the affected cards are
// rebuilt. QC's own notes are never replaced in the text box: what gets submitted is always
// what QC typed, and the English appears underneath it.

const CJK = /[㐀-鿿豈-﫿]/;
const trCache = new Map();
const trQueue = new Set();
const trInflight = new Set();
let trTimer = 0;
let trError = null;
let trPausedUntil = 0;

const needsTr = (s) => typeof s === 'string' && CJK.test(s);

function tx(s) {
  if (lang !== 'en' || !needsTr(s)) return s;
  const hit = trCache.get(s);
  if (hit != null) return hit;
  queueTr(s);
  return s;
}

function queueTr(s) {
  if (trInflight.has(s) || trCache.has(s) || Date.now() < trPausedUntil) return;
  trQueue.add(s);
  clearTimeout(trTimer);
  trTimer = setTimeout(flushTr, 40);
}

async function flushTr() {
  const texts = [...trQueue];
  trQueue.clear();
  if (!texts.length) return;
  const groups = [];
  let group = [];
  let size = 0;
  for (const s of texts) {
    if (group.length && (group.length >= 150 || size + s.length > 40000)) {
      groups.push(group);
      group = [];
      size = 0;
    }
    group.push(s);
    size += s.length;
  }
  groups.push(group);
  texts.forEach((s) => trInflight.add(s));
  renderTrStatus();
  let got = false;
  await Promise.all(
    groups.map(async (g) => {
      try {
        const res = await api('/api/translate', { texts: g });
        for (const [zh, en] of Object.entries(res.translations || {})) trCache.set(zh, en);
        got = true;
        trError = null;
      } catch (err) {
        // Stop asking for a minute, or every re-render would hit the same failure again.
        trError = err.message;
        trPausedUntil = Date.now() + 60000;
      } finally {
        g.forEach((s) => trInflight.delete(s));
      }
    }),
  );
  renderTrStatus();
  if (got && S && lang === 'en') {
    render();
    refreshNotePreviews();
  }
}

function renderTrStatus() {
  const el = $('#trstatus');
  if (lang !== 'en') {
    el.hidden = true;
    return;
  }
  // classList, not className: the element also carries review-only, which hides it on the taste page.
  if (trInflight.size) {
    el.hidden = false;
    el.classList.remove('failed');
    el.replaceChildren(h('span', { class: 'spinner', 'aria-hidden': 'true' }), t('translating'));
  } else if (trError) {
    el.hidden = false;
    el.classList.add('failed');
    el.replaceChildren(
      t('trFailed', { error: trError }),
      ' ',
      h(
        'button',
        {
          type: 'button',
          class: 'link',
          onclick: () => {
            trError = null;
            trPausedUntil = 0;
            cards.clear();
            if (S) render();
            renderTrStatus();
          },
        },
        t('retry'),
      ),
    );
  } else {
    el.hidden = true;
  }
}

// Every string with Chinese in it, anywhere inside a value, so a card's signature changes
// when any of its translations arrive.
function textsOf(value, out = []) {
  if (typeof value === 'string') {
    if (needsTr(value)) out.push(value);
  } else if (Array.isArray(value)) {
    value.forEach((v) => textsOf(v, out));
  } else if (value && typeof value === 'object') {
    Object.values(value).forEach((v) => textsOf(v, out));
  }
  return out;
}

function refreshNotePreviews() {
  document.querySelectorAll('.story.pending').forEach((el) => el.updatePreview?.());
}

// ------------------------------------------------------------------ language and theme

const currentTheme = () => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');

// Drawn rather than ☀/☾ characters: Windows fonts render the sun as something like an asterisk.
function themeIcon(kind) {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  const attrs = {
    viewBox: '0 0 24 24',
    width: 15,
    height: 15,
    fill: 'none',
    stroke: 'currentColor',
    'stroke-width': 2,
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round',
    'aria-hidden': 'true',
  };
  for (const [k, v] of Object.entries(attrs)) svg.setAttribute(k, String(v));
  const shapes =
    kind === 'sun'
      ? [
          ['circle', { cx: 12, cy: 12, r: 4 }],
          ['path', { d: 'M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41' }],
        ]
      : [['path', { d: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z' }]];
  for (const [tag, shapeAttrs] of shapes) {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(shapeAttrs)) el.setAttribute(k, String(v));
    svg.append(el);
  }
  return svg;
}

function applyStatic() {
  document.documentElement.lang = lang === 'en' ? 'en' : 'zh-CN';
  setTitle();
  for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = t(el.dataset.i18n);
  for (const el of document.querySelectorAll('[data-i18n-aria]')) el.setAttribute('aria-label', t(el.dataset.i18nAria));
  $('#kbd-help').replaceChildren(...t('keys').map((part) => (Array.isArray(part) ? h('kbd', {}, part[0]) : part)));
  const langButton = $('#lang');
  langButton.textContent = t('langButton');
  langButton.setAttribute('aria-label', t('langAria'));
  langButton.title = t('langAria');
  const dark = currentTheme() === 'dark';
  const themeButton = $('#theme');
  const label = dark ? t('themeToLight') : t('themeToDark');
  themeButton.replaceChildren(themeIcon(dark ? 'sun' : 'moon'));
  themeButton.setAttribute('aria-label', label);
  themeButton.setAttribute('aria-pressed', String(dark));
  themeButton.title = label;
  if (!S) $('#mode').textContent = t('connecting');
}

$('#lang').addEventListener('click', () => {
  lang = lang === 'en' ? 'zh' : 'en';
  local.set('story-review:lang', lang);
  for (const s of sections.values()) {
    if (!s.statsOpen) continue;
    s.statsOpen = false;
    s.statsEl?.remove();
    s.statsEl = null;
  }
  applyStatic();
  renderTrStatus();
  if (S) render();
  refreshNotePreviews();
  if (view === 'taste') renderTaste();
});

$('#theme').addEventListener('click', () => {
  const next = currentTheme() === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  local.set('story-review:theme', next);
  applyStatic();
});

// Until QC picks a theme, follow the system setting as it changes.
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
  if (local.get('story-review:theme')) return;
  document.documentElement.dataset.theme = e.matches ? 'dark' : 'light';
  applyStatic();
});

// ------------------------------------------------------------------ state

let refreshing = null;
let again = false;

async function refresh() {
  if (refreshing) {
    again = true;
    return refreshing;
  }
  refreshing = (async () => {
    do {
      again = false;
      try {
        S = await api('/api/state');
        render();
        if (view === 'taste') loadTaste();
        setOffline(null);
      } catch (err) {
        setOffline(t('offline', { error: err.message }));
      }
    } while (again);
  })();
  try {
    await refreshing;
  } finally {
    refreshing = null;
  }
}

let soonTimer = 0;
function soon() {
  clearTimeout(soonTimer);
  soonTimer = setTimeout(refresh, 200);
}

function setOffline(message) {
  const el = $('#offline');
  el.hidden = !message;
  el.textContent = message || '';
}

function render() {
  byId.clear();
  for (const c of S.candidates) byId.set(c.id, c);
  const names = lang === 'en' ? S.scenes_en : S.scenes;
  sceneNames = new Map(
    Object.entries(names).map(([file, name]) => [
      file
        .replace(/\.[a-z0-9]+$/i, '')
        .toLowerCase(),
      name,
    ]),
  );
  renderTop();
  renderFeed();
  renderJob();
  if (!known) {
    known = new Set(S.candidates.map((c) => c.id));
    const first = document.querySelector('.story.pending:not([hidden])');
    if (first) setCurrent(first.dataset.id, 'center');
  } else {
    noteArrivals();
  }
}

// ------------------------------------------------------------------ top bar

function renderTop() {
  const mode = $('#mode');
  mode.textContent = S.mode === 'dry-run' ? t('modeDry') : t('modeLive');
  mode.className = `mode ${S.mode}`;
  mode.title = t('storeTitle', { path: S.store });

  const counts = { all: S.candidates.length, pending: 0, selected: 0, shortlisted: 0, discarded: 0 };
  for (const c of S.candidates) counts[bandOf(c.verdict)] += 1;
  $('#filters').replaceChildren(
    ...FILTER_KEYS.map((key) =>
      h(
        'button',
        {
          type: 'button',
          class: `filter${filter === key ? ' on' : ''}`,
          'aria-pressed': String(filter === key),
          onclick: () => {
            filter = key;
            render();
          },
        },
        t('filter')[key],
        h('span', { class: 'count' }, counts[key]),
      ),
    ),
  );
  $('#progress').textContent = counts.pending
    ? t('progressLeft', { n: counts.pending })
    : S.candidates.length
      ? t('progressDone')
      : '';

  const form = $('#generate');
  const range = local.get('story-review:range') || [S.default_max_chars, S.default_max_chars];
  ['min', 'max'].forEach((name, i) => {
    const input = form.elements[name];
    input.max = S.max_prose_chars;
    if (!input.value && document.activeElement !== input) input.value = range[i];
  });
  const button = form.querySelector('button');
  button.disabled = !S.can_generate;
  button.textContent = S.job.running ? t('generating') : t('generate');
  const n = waitlistCount();
  let note = '';
  if (S.generate_blocked) note = t('blocked', { why: S.generate_blocked[lang] || S.generate_blocked.zh });
  else if (n) note = t('willRewrite', { n });
  $('#blocked').textContent = note;
}

$('#generate').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!S) return;
  const form = e.currentTarget;
  const lo = Number(form.elements.min.value);
  const hi = Number(form.elements.max.value);
  if (!Number.isInteger(lo) || !Number.isInteger(hi) || lo < 1 || lo > hi || hi > S.max_prose_chars) {
    $('#blocked').textContent = t('rangeError', { max: S.max_prose_chars });
    return;
  }
  local.set('story-review:range', [lo, hi]);
  if (S.mode !== 'dry-run') {
    const n = waitlistCount();
    const extra = n ? t('confirmExtra', { n }) : '';
    if (!confirm(t('confirmLive', { extra, lo, hi }))) return;
  }
  try {
    await api('/api/generate', { min_chars: lo, max_chars: hi });
    logOpen = true;
  } catch (err) {
    $('#blocked').textContent = err.message;
  }
  refresh();
});

function renderJob() {
  if (!S) return;
  const box = $('#joblog');
  const job = S.job;
  if (job.running) logOpen = true;
  box.hidden = !logOpen || (!job.running && !job.log.length && !job.error);
  let title = t('logPrevious');
  if (job.running) title = t('logRunning');
  else if (job.error) title = t('logFailed', { error: job.error });
  else if (job.round) title = t('logDone', { round: job.round });
  box.querySelector('.joblog-title').textContent = title;
  box.classList.toggle('failed', Boolean(job.error) && !job.running);
  const pre = box.querySelector('pre');
  const text = job.log.join('\n');
  if (pre.textContent !== text) {
    pre.textContent = text;
    pre.scrollTop = pre.scrollHeight;
  }
}

function appendLog(line) {
  if (S) S.job.log.push(line);
  logOpen = true;
  const box = $('#joblog');
  box.hidden = false;
  const pre = box.querySelector('pre');
  pre.textContent += (pre.textContent ? '\n' : '') + line;
  pre.scrollTop = pre.scrollHeight;
}

$('#joblog .joblog-close').addEventListener('click', () => {
  logOpen = false;
  renderJob();
});

// ------------------------------------------------------------------ feed

// Keep existing nodes where they are, so a card being typed in keeps its focus and caret.
function place(container, els) {
  const keep = new Set(els);
  for (const child of [...container.children]) if (!keep.has(child)) child.remove();
  els.forEach((el, i) => {
    if (container.children[i] !== el) container.insertBefore(el, container.children[i] || null);
  });
}

// A card is rebuilt when its data, its language or its translations change. If QC was
// typing in it at that moment, put the caret back where it was.
function captureFocus() {
  const a = document.activeElement;
  const story = a && a.closest ? a.closest('.story') : null;
  if (!story || !(a instanceof HTMLTextAreaElement || a instanceof HTMLInputElement)) return null;
  let start = null;
  let end = null;
  try {
    start = a.selectionStart;
    end = a.selectionEnd;
  } catch {
    /* number inputs have no selection */
  }
  return { id: story.dataset.id, notes: a.classList.contains('notes'), start, end, scroll: a.scrollTop };
}

function restoreFocus(f) {
  if (!f) return;
  const story = document.getElementById(`story-${f.id}`);
  if (!story || story.contains(document.activeElement)) return;
  const el = f.notes ? story.querySelector('textarea.notes') : story.querySelector('input[type="number"]');
  if (!el) return;
  el.focus({ preventScroll: true });
  try {
    if (f.start != null) el.setSelectionRange(f.start, f.end);
  } catch {
    /* ignore */
  }
  el.scrollTop = f.scroll;
}

const matches = (c) => filter === 'all' || bandOf(c.verdict) === filter;

// Within a round: waitlist rewrites first, then slot by slot, each revise rewrite directly
// under the story it rewrites. Inside a slot the order is by id, which is random, so it
// says nothing about which model wrote what.
function orderRound(cands) {
  const slotOrder = Object.keys(S.slots);
  const rank = (c) => {
    if (c.rewrite === 'waitlist') return -1;
    const i = slotOrder.indexOf(c.slot);
    return i === -1 ? slotOrder.length : i;
  };
  const fresh = cands.filter((c) => c.rewrite !== 'revise').sort((a, b) => rank(a) - rank(b) || a.id.localeCompare(b.id));
  const revises = cands.filter((c) => c.rewrite === 'revise');
  const out = [];
  const placed = new Set();
  const put = (c) => {
    out.push(c);
    placed.add(c.id);
    for (const r of revises) if (r.parent === c.id && !placed.has(r.id)) put(r);
  };
  fresh.forEach(put);
  for (const r of revises) if (!placed.has(r.id)) put(r);
  return out;
}

function renderFeed() {
  const focus = captureFocus();
  const groups = new Map(S.rounds.map((r) => [r.id, []]));
  for (const c of S.candidates) {
    if (!groups.has(c.round)) groups.set(c.round, []);
    groups.get(c.round).push(c);
  }
  const latest = S.rounds.length ? S.rounds[S.rounds.length - 1].id : null;
  const els = [];
  for (const r of S.rounds) {
    const sec = section(r, r.id === latest);
    const list = orderRound(groups.get(r.id) || []);
    let visible = 0;
    const cardEls = list.map((c) => {
      const el = card(c);
      el.hidden = !matches(c);
      if (!el.hidden) visible += 1;
      return el;
    });
    place(sec.body, cardEls);
    sec.el.hidden = filter !== 'all' && !visible;
    els.push(sec.el);
  }
  if (!S.rounds.length) els.push(h('p', { class: 'empty' }, t('empty1'), h('br'), t('empty2')));
  place($('#feed'), els);
  for (const id of [...cards.keys()]) if (!byId.has(id)) cards.delete(id);
  restoreFocus(focus);
}

function section(r, isLatest) {
  let s = sections.get(r.id);
  if (!s) {
    const head = h('button', { type: 'button', class: 'round-head' });
    const tools = h('div', { class: 'round-tools' });
    const body = h('div', { class: 'round-body' });
    const el = h(
      'section',
      { class: 'round', dataset: { round: r.id } },
      h('div', { class: 'round-bar' }, h('h2', { class: 'round-title' }, head), tools),
      body,
    );
    s = { el, head, tools, body, statsEl: null, statsOpen: false, isLatest };
    head.addEventListener('click', () => {
      const opening = s.el.classList.contains('collapsed');
      (opening ? openRounds : closedRounds).add(r.id);
      (opening ? closedRounds : openRounds).delete(r.id);
      renderSection(s, S.rounds.find((x) => x.id === r.id));
    });
    sections.set(r.id, s);
  }
  s.isLatest = isLatest;
  renderSection(s, r);
  return s;
}

function renderSection(s, r) {
  const n = { selected: 0, shortlisted: 0, discarded: 0 };
  for (const c of S.candidates) if (c.round === r.id && c.verdict !== 'pending') n[bandOf(c.verdict)] += 1;
  const collapsed =
    filter === 'all' && (closedRounds.has(r.id) || (!openRounds.has(r.id) && r.complete && !s.isLatest));
  s.el.classList.toggle('collapsed', collapsed);
  s.head.setAttribute('aria-expanded', String(!collapsed));
  const range = r.max_chars_range;
  const meta = [
    t('storiesN', { n: r.total }),
    r.pending ? t('pendingN', { n: r.pending }) : t('judged'),
    n.selected && t('selectedN', { n: n.selected }),
    n.shortlisted && t('shortlistedN', { n: n.shortlisted }),
    n.discarded && t('discardedN', { n: n.discarded }),
    range && t('capN', { n: range[0] === range[1] ? range[0] : range.join('–') }),
    r.format,
  ].filter(Boolean);
  // replaceChildren, unlike h(), turns null into the text "null", so drop empties first.
  s.head.replaceChildren(
    ...[
      h('span', { class: 'round-id' }, r.id),
      h('span', { class: 'round-meta' }, meta.join(' · ')),
      r.dry_run ? h('span', { class: 'tag dry' }, 'dry run') : null,
    ].filter(Boolean),
  );
  s.tools.replaceChildren(
    r.complete
      ? h(
          'button',
          { type: 'button', class: 'btn ghost small', onclick: () => toggleStats(s, r.id) },
          s.statsOpen ? t('hideStats') : t('revealStats'),
        )
      : h('span', { class: 'blind-note', title: t('blindTitle') }, t('blind')),
  );
}

async function toggleStats(s, roundId) {
  if (s.statsOpen) {
    s.statsOpen = false;
    s.statsEl?.remove();
    s.statsEl = null;
  } else {
    try {
      const st = await api(`/api/stats?round=${encodeURIComponent(roundId)}`);
      s.statsEl?.remove();
      s.statsEl = statsTable(st);
      s.el.insertBefore(s.statsEl, s.body);
      s.statsOpen = true;
    } catch (err) {
      alert(err.message);
    }
  }
  const r = S.rounds.find((x) => x.id === roundId);
  if (r) renderSection(s, r);
}

function statsTable(st) {
  const rows = Object.entries(st.models).sort(([a], [b]) => a.localeCompare(b));
  const pct = (v) => `${Math.round(v * 100)}%`;
  const reasons = st.reasons.map((x) => `${lang === 'en' ? x.label_en : x.label} ${x.count}`).join(t('listSep'));
  return h(
    'div',
    { class: 'stats' },
    h(
      'div',
      { class: 'stats-scroll' },
      h(
        'table',
        {},
        h('thead', {}, h('tr', {}, t('statsHead').map((label) => h('th', { scope: 'col' }, label)))),
        h(
          'tbody',
          {},
          rows.map(([model, row]) =>
            h(
              'tr',
              {},
              h('th', { scope: 'row' }, model),
              h('td', {}, row.selected),
              h('td', {}, row.selected_with_notes),
              h('td', {}, row.shortlisted),
              h('td', {}, row.discarded),
              h('td', {}, pct(row.accept_rate)),
              h('td', {}, row.avg_score ?? '–'),
            ),
          ),
        ),
      ),
    ),
    st.reasons.length ? h('p', {}, t('statsReasons', { list: reasons })) : null,
    st.rewrites ? h('p', {}, t('statsRewrites', { n: st.rewrites })) : null,
  );
}

// ------------------------------------------------------------------ cards

function sigOf(c) {
  const p = c.parent && byId.get(c.parent);
  const child = c.rewritten_as && byId.get(c.rewritten_as);
  const parts = [
    c,
    S.rewrites[c.id] || null,
    p ? [p.title, p.score, p.verdict, p.notes, p.outline, p.words, p.ceiling] : null,
    child ? [child.title, child.verdict] : null,
    lang,
  ];
  if (lang === 'en') {
    const nearest = c.nearest && !S.stories_en[c.nearest] ? S.stories[c.nearest] : null;
    const texts = textsOf([parts.slice(0, 4), nearest, (c.cast || []).filter((slug) => !S.characters[slug])]);
    parts.push(texts.map((s) => trCache.get(s) ?? null));
  }
  return JSON.stringify(parts);
}

function card(c) {
  const sig = sigOf(c);
  const hit = cards.get(c.id);
  if (hit && hit.sig === sig) return hit.el;
  const expanded = Boolean(hit && hit.el.classList.contains('expanded'));
  const el = c.verdict === 'pending' ? pendingCard(c) : decidedCard(c, expanded);
  if (current === c.id) el.classList.add('current');
  cards.set(c.id, { sig, el });
  return el;
}

function faces(c) {
  const cast = Array.isArray(c.cast) ? c.cast : [];
  const names = cast.map(charName);
  return h(
    'div',
    {
      class: 'faces',
      role: 'img',
      'aria-label': names.length ? t('castAria', { names: names.join(t('nameSep')) }) : t('noCast'),
    },
    cast.map((slug, i) => {
      const ch = S.characters[slug];
      if (ch && ch.avatar) {
        return h('img', {
          class: 'face',
          src: `/avatar/${encodeURIComponent(slug)}.png`,
          alt: '',
          title: names[i],
          loading: 'lazy',
          style: `--ring:${ch.accent};object-position:${ch.focus}`,
        });
      }
      const name = names[i];
      return h(
        'span',
        { class: 'face guest', title: ch ? name : t('guest', { name }), style: ch ? `--ring:${ch.accent}` : null },
        Array.from(name)[0] || '?',
      );
    }),
  );
}

function tags(c) {
  return h(
    'div',
    { class: 'tags' },
    h('span', { class: `tag kind-${c.kind === 'extra' ? 'extra' : 'memory'}` }, t('kind')[c.kind] || t('kind').memory),
    c.rewrite === 'waitlist'
      ? h(
          'span',
          { class: 'tag rewrite-waitlist', title: t('waitlistTitle', { n: c.revisit_count, max: S.max_revisits }) },
          t('waitlistTag', { n: c.revisit_count }),
        )
      : null,
    c.rewrite === 'revise' ? h('span', { class: 'tag rewrite-revise' }, t('reviseTag')) : null,
    h('span', { class: 'tag slot' }, slotName(c.slot)),
    c.location ? h('span', { class: 'tag place' }, sceneName(c.location)) : null,
    h(
      'span',
      { class: `tag length${c.over_limit ? ' over' : ''}`, title: c.over_limit ? t('lengthOver') : t('lengthTitle') },
      t('length', { words: c.words, cap: c.ceiling }),
    ),
    c.parse_failed ? h('span', { class: 'tag broken' }, t('broken')) : null,
  );
}

function head(c) {
  return h(
    'header',
    { class: 'story-head' },
    faces(c),
    h('div', { class: 'story-titles' }, h('h3', {}, tx(c.title) || t('untitled')), tags(c)),
  );
}

function outline(c) {
  const paras = String(tx(c.outline) || '')
    .split(/\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
  if (!paras.length) return null;
  return h(
    'div',
    { class: 'outline' },
    paras.map((p) => h('p', {}, p)),
  );
}

function selfNotes(c) {
  const rows = [];
  for (const f of S.format.fields) {
    if (f.show !== 'note') continue;
    let v = Object.prototype.hasOwnProperty.call(c, f.key) ? c[f.key] : c.extra?.[f.key];
    if (v == null || v === '' || (Array.isArray(v) && !v.length)) continue;
    if (f.key === 'new_elements' && (v === 'none' || (Array.isArray(v) && v.every((x) => x === 'none')))) v = t('none');
    else if (Array.isArray(v)) v = v.map((x) => (typeof x === 'string' ? tx(x) : JSON.stringify(x))).join(t('nameSep'));
    else if (typeof v === 'object') v = JSON.stringify(v);
    else v = tx(String(v));
    rows.push(h('div', { class: 'note-row' }, h('dt', {}, fieldLabel(f)), h('dd', {}, v)));
  }
  if (c.nearest) {
    const title = storyTitle(c.nearest);
    rows.push(
      h(
        'div',
        { class: 'note-row' },
        h('dt', {}, t('nearest')),
        h('dd', {}, title ? t('quoteTitle', { title }) : c.nearest),
      ),
    );
  }
  if (!rows.length) return null;
  return h('details', { class: 'self', open: true }, h('summary', {}, t('selfNotes')), h('dl', {}, rows));
}

function history(c) {
  if (!c.parent) return null;
  const p = byId.get(c.parent);
  if (!p) return h('div', { class: 'history' }, t('rewrittenFrom', { id: c.parent }));
  return h(
    'div',
    { class: 'history' },
    h(
      'div',
      { class: 'history-head' },
      h('span', {}, c.rewrite === 'revise' ? t('historyRevise') : t('historyWaitlist')),
      p.score != null ? h('span', { class: 'score-chip' }, t('points', { n: p.score })) : null,
    ),
    p.notes ? h('blockquote', {}, tx(p.notes)) : null,
    h(
      'details',
      { class: 'history-prev' },
      h('summary', {}, t('prevVersion', { title: tx(p.title) || t('untitled'), words: p.words, cap: p.ceiling })),
      outline(p),
    ),
  );
}

function parseNote(c) {
  return c.parse_failed ? h('p', { class: 'parse-note' }, t('parseNote')) : null;
}

function nextPendingAfter(id) {
  const list = [...document.querySelectorAll('.story.pending')].filter((el) => !el.hidden);
  const i = list.findIndex((el) => el.dataset.id === id);
  const next = list[i + 1] || list.find((el) => el.dataset.id !== id);
  return next ? next.dataset.id : null;
}

function pendingCard(c) {
  const d = draft(c.id);
  const [min, max] = S.score_range;
  let busy = false;

  const el = h('article', {
    class: 'story pending',
    id: `story-${c.id}`,
    tabindex: '-1',
    dataset: { id: c.id, rewrite: c.rewrite || '' },
  });

  const slider = h('input', { type: 'range', class: 'slider', min, max, step: 1, 'aria-label': t('scoreLabel') });
  slider.style.setProperty('--track', trackGradient());
  const ticks = h('div', { class: 'ticks', 'aria-hidden': 'true' });
  for (let v = min; v <= max; v += 1) ticks.append(h('span', { onclick: () => setScore(v) }, v));
  const value = h('output', { class: 'score-value' });
  const pill = h('span', { class: 'dest' });

  const reasons = h('div', { class: 'reasons', role: 'group', 'aria-label': t('reasonsAria') });
  for (const [key, label] of Object.entries(lang === 'en' ? S.reasons_en : S.reasons)) {
    const box = h('input', { type: 'checkbox', value: key });
    box.checked = (d.reasons || []).includes(key);
    box.addEventListener('change', () => {
      d.reasons = [...reasons.querySelectorAll('input:checked')].map((i) => i.value);
      saveDraft(c.id);
    });
    reasons.append(h('label', { class: 'reason' }, box, label));
  }

  const notes = h('textarea', { class: 'notes', rows: 3, 'aria-label': t('notes') });
  notes.value = d.notes || '';
  const preview = h('p', { class: 'notes-translation', 'aria-live': 'polite', hidden: true });
  const ceilingInput = h('input', {
    type: 'number',
    min: 1,
    max: S.max_prose_chars,
    step: 1,
    inputmode: 'numeric',
    'aria-label': t('rewriteCapAria'),
  });
  ceilingInput.value = d.max_chars ?? c.ceiling;
  const ceiling = h('label', { class: 'ceiling' }, t('rewriteCap'), ceilingInput, t('chars'));
  const hint = h('span', { class: 'hint', 'aria-live': 'polite' });
  const submit = h('button', { type: 'submit', class: 'btn' }, t('submit'));

  const form = h(
    'form',
    { class: 'verdict' },
    h(
      'div',
      { class: 'score-row' },
      h('span', { class: 'score-label' }, t('scoreLabel')),
      h('div', { class: 'slider-wrap' }, slider, ticks),
      value,
      pill,
    ),
    reasons,
    notes,
    preview,
    h('div', { class: 'actions' }, ceiling, hint, submit),
  );

  function problem(dest) {
    if (!dest) return t('needScore');
    if (dest === 'discarded' && !notes.value.trim()) return t('needWhyDiscard');
    if (dest === 'shortlisted' && !notes.value.trim()) return t('needWhyShortlist');
    return '';
  }

  function sync() {
    const touched = d.score != null;
    slider.value = touched ? d.score : Math.round((min + max) / 2);
    slider.classList.toggle('untouched', !touched);
    value.textContent = touched ? d.score : '–';
    const dest = destination(d.score, notes.value);
    el.dataset.band = dest ? bandOf(dest) : '';
    pill.textContent = dest ? t('dest')[dest] : t('notScored');
    pill.className = dest ? `dest band-${bandOf(dest)}` : 'dest';
    reasons.hidden = dest !== 'discarded';
    notes.placeholder = dest ? t('notesHint')[dest] : t('notes');
    notes.required = dest === 'discarded' || dest === 'shortlisted';
    ceiling.hidden = dest !== 'selected_with_notes';
    const why = problem(dest);
    let note = why;
    if (!why && dest === 'selected_with_notes') note = t('hintRevise');
    if (!why && dest === 'shortlisted') note = t('hintShortlist');
    hint.textContent = note;
    hint.classList.toggle('warn', Boolean(why) && touched);
    submit.disabled = Boolean(why) || busy;
    submit.textContent = busy ? t('submitting') : dest ? t('submitAs')[dest] : t('submit');
  }

  // English mode: show what QC has typed, in English, under the box. The box keeps the
  // original, which is what gets submitted and what the model reads.
  let previewTimer = 0;
  function updatePreview(immediate) {
    const text = notes.value.trim();
    if (lang !== 'en' || !needsTr(text)) {
      preview.hidden = true;
      return;
    }
    preview.hidden = false;
    const label = h('span', { class: 'label' }, t('inEnglish'));
    const hit = trCache.get(text);
    if (hit != null) {
      preview.replaceChildren(label, hit);
      return;
    }
    preview.replaceChildren(label, h('span', { class: 'waiting' }, t('translating')));
    clearTimeout(previewTimer);
    previewTimer = setTimeout(() => queueTr(text), immediate ? 0 : 900);
  }
  el.updatePreview = () => updatePreview(true);

  function setScore(v) {
    d.score = Math.min(max, Math.max(min, v));
    saveDraft(c.id);
    sync();
  }

  function fail(message) {
    hint.textContent = message;
    hint.classList.add('warn');
  }

  slider.addEventListener('input', () => setScore(Number(slider.value)));
  // Clicking the thumb where it already sits fires no input event; count it as a score.
  slider.addEventListener('click', () => {
    if (d.score == null) setScore(Number(slider.value));
  });
  notes.addEventListener('input', () => {
    d.notes = notes.value;
    saveDraft(c.id);
    sync();
    updatePreview(false);
  });
  ceilingInput.addEventListener('input', () => {
    d.max_chars = ceilingInput.value === '' ? null : Number(ceilingInput.value);
    saveDraft(c.id);
  });
  form.addEventListener('score', (e) => setScore(e.detail));
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    sync();
    if (submit.disabled) return;
    const dest = destination(d.score, notes.value);
    const payload = {
      id: c.id,
      score: d.score,
      notes: notes.value.trim(),
      reasons: dest === 'discarded' ? d.reasons || [] : [],
    };
    if (dest === 'selected_with_notes') {
      const v = Number(ceilingInput.value);
      if (!Number.isInteger(v) || v < 1 || v > S.max_prose_chars) {
        fail(t('capRange', { max: S.max_prose_chars }));
        return;
      }
      payload.max_chars = v;
    }
    const next = nextPendingAfter(c.id);
    busy = true;
    sync();
    try {
      await api('/api/verdict', payload);
      dropDraft(c.id);
      await refresh();
      if (next && byId.get(next)?.verdict === 'pending') setCurrent(next, 'nearest');
    } catch (err) {
      busy = false;
      sync();
      fail(err.message);
    }
  });

  el.append(...[head(c), parseNote(c), history(c), outline(c), selfNotes(c), form].filter(Boolean));
  sync();
  updatePreview(true);
  return el;
}

function decidedCard(c, expanded) {
  const band = bandOf(c.verdict);
  const el = h('article', {
    class: `story decided${expanded ? ' expanded' : ''}`,
    id: `story-${c.id}`,
    tabindex: '-1',
    dataset: { id: c.id, band, rewrite: c.rewrite || '' },
  });
  const toggle = h(
    'button',
    { type: 'button', class: 'decided-row', 'aria-expanded': String(expanded) },
    h('span', { class: `dest band-${band}` }, t('verdict')[c.verdict] || c.verdict),
    c.score != null ? h('span', { class: 'score-chip' }, t('points', { n: c.score })) : null,
    h('span', { class: 'decided-title' }, tx(c.title) || t('untitled')),
    h('span', { class: 'decided-notes' }, tx(c.notes) || reasonText(c)),
  );
  toggle.addEventListener('click', () => {
    const on = !el.classList.contains('expanded');
    el.classList.toggle('expanded', on);
    toggle.setAttribute('aria-expanded', String(on));
  });
  const full = h(
    'div',
    { class: 'decided-full' },
    head(c),
    parseNote(c),
    history(c),
    outline(c),
    selfNotes(c),
    summary(c),
  );
  el.append(...[toggle, followUp(c), full].filter(Boolean));
  return el;
}

function summary(c) {
  const why = reasonText(c);
  const line = [t('verdict')[c.verdict], c.score != null && t('points', { n: c.score }), c.decided_at && fmtTime(c.decided_at)]
    .filter(Boolean)
    .join(' · ');
  return h(
    'div',
    { class: 'summary' },
    h('p', {}, line),
    why ? h('p', {}, t('why', { text: why })) : null,
    c.notes ? h('p', {}, t('notesIs', { text: tx(c.notes) })) : null,
    c.rewrite_max_chars ? h('p', {}, t('rewriteCapIs', { n: c.rewrite_max_chars })) : null,
  );
}

function jump(id, text) {
  return h('button', { type: 'button', class: 'link', onclick: () => setCurrent(id, 'center') }, text);
}

function followUp(c) {
  if (c.verdict === 'selected_with_notes') {
    if (c.rewritten_as) {
      const child = byId.get(c.rewritten_as);
      const title = tx(child?.title) || c.rewritten_as;
      return h('div', { class: 'follow' }, t('rewriteArrived'), ' ', jump(c.rewritten_as, `${title} ↓`));
    }
    const job = S.rewrites[c.id];
    if (job && job.state === 'running') {
      return h(
        'div',
        { class: 'follow running' },
        h('span', { class: 'spinner', 'aria-hidden': 'true' }),
        t('rewriting'),
      );
    }
    const why = job && job.error ? t('rewriteFailed', { error: job.error }) : t('rewriteMissing');
    return h(
      'div',
      { class: 'follow failed' },
      why,
      h('button', { type: 'button', class: 'btn ghost small', onclick: (e) => retry(c.id, e.currentTarget) }, t('retry')),
    );
  }
  if (c.verdict === 'shortlisted') {
    if (c.rewritten_as) {
      const child = byId.get(c.rewritten_as);
      return h('div', { class: 'follow' }, t('carriedOver'), ' ', jump(c.rewritten_as, tx(child?.title) || c.rewritten_as));
    }
    if (c.revisit_count >= S.max_revisits) {
      return h('div', { class: 'follow' }, t('retiring', { n: c.revisit_count }));
    }
    return ceilingEditor(c);
  }
  return null;
}

function ceilingEditor(c) {
  const input = h('input', {
    type: 'number',
    min: 1,
    max: S.max_prose_chars,
    step: 1,
    inputmode: 'numeric',
    'aria-label': t('nextCapAria'),
  });
  input.value = c.rewrite_max_chars ?? c.ceiling;
  const status = h('span', { class: 'hint', 'aria-live': 'polite' });
  async function save() {
    const v = Number(input.value);
    if (!Number.isInteger(v) || v < 1 || v > S.max_prose_chars) {
      status.textContent = t('between', { max: S.max_prose_chars });
      status.classList.add('warn');
      return;
    }
    const wanted = v === c.ceiling ? null : v;
    if (wanted === (c.rewrite_max_chars ?? null)) return;
    status.textContent = t('saving');
    status.classList.remove('warn');
    try {
      await api('/api/ceiling', { id: c.id, max_chars: wanted });
      status.textContent = t('saved');
      refresh();
    } catch (err) {
      status.textContent = err.message;
      status.classList.add('warn');
    }
  }
  input.addEventListener('change', save);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      save();
    }
  });
  return h(
    'div',
    { class: 'follow' },
    h('label', { class: 'ceiling' }, t('nextCap'), input, t('chars')),
    c.rewrite_max_chars ? h('span', { class: 'hint' }, t('originally', { n: c.ceiling })) : null,
    status,
  );
}

async function retry(id, button) {
  button.disabled = true;
  try {
    await api('/api/retry-rewrite', { id });
  } catch (err) {
    alert(err.message);
  }
  refresh();
}

// ------------------------------------------------------------------ focus, arrivals, keys

function setCurrent(id, block) {
  if (current && current !== id) document.getElementById(`story-${current}`)?.classList.remove('current');
  current = id;
  if (!id || !S) return;
  const c = byId.get(id);
  let rerender = false;
  if (c && filter !== 'all' && bandOf(c.verdict) !== filter) {
    filter = 'all';
    rerender = true;
  }
  if (c && sections.get(c.round)?.el.classList.contains('collapsed')) {
    openRounds.add(c.round);
    closedRounds.delete(c.round);
    rerender = true;
  }
  if (rerender) render();
  const el = document.getElementById(`story-${id}`);
  if (!el) return;
  el.classList.add('current');
  if (block) {
    const smooth = !matchMedia('(prefers-reduced-motion: reduce)').matches;
    el.scrollIntoView({ block, behavior: smooth ? 'smooth' : 'auto' });
    el.focus({ preventScroll: true });
  }
}

function step(dir) {
  const list = [...document.querySelectorAll('.story')].filter(
    (el) => !el.hidden && !el.closest('.round')?.classList.contains('collapsed') && !el.closest('.round')?.hidden,
  );
  if (!list.length) return;
  const i = list.findIndex((el) => el.dataset.id === current);
  let next;
  if (i === -1) next = dir > 0 ? list[0] : list[list.length - 1];
  else next = list[Math.min(list.length - 1, Math.max(0, i + dir))];
  setCurrent(next.dataset.id, 'center');
}

function noteArrivals() {
  for (const c of S.candidates) {
    if (known.has(c.id)) continue;
    known.add(c.id);
    if (c.verdict !== 'pending') continue;
    arrivals.push(c.id);
    cards.get(c.id)?.el.classList.add('fresh');
  }
  updateArrivals();
}

function updateArrivals() {
  arrivals = arrivals.filter((id) => byId.get(id)?.verdict === 'pending');
  const button = $('#arrivals');
  button.hidden = !arrivals.length;
  button.textContent = t('arrivals', { n: arrivals.length });
  setTitle();
}

// The tab title counts stories that arrived and have not been looked at yet, so a round can
// run in a background tab and still say when there is something new to read.
function setTitle() {
  document.title = (arrivals.length ? `(${arrivals.length}) ` : '') + t('pageTitle');
}

$('#arrivals').addEventListener('click', () => {
  const id = arrivals[0];
  arrivals = [];
  updateArrivals();
  if (id) setCurrent(id, 'center');
});

let scrollFrame = 0;
addEventListener(
  'scroll',
  () => {
    if (scrollFrame || !arrivals.length) return;
    scrollFrame = requestAnimationFrame(() => {
      scrollFrame = 0;
      arrivals = arrivals.filter((id) => {
        const box = document.getElementById(`story-${id}`)?.getBoundingClientRect();
        return !(box && box.top < innerHeight && box.bottom > 0);
      });
      updateArrivals();
    });
  },
  { passive: true },
);

document.addEventListener('keydown', (e) => {
  // Scoring keys act on hidden review cards otherwise.
  if (!S || view !== 'review') return;
  const target = e.target instanceof Element ? e.target : document.body;
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    const form =
      target.closest('form.verdict') || (current && document.querySelector(`#story-${current} form.verdict`));
    if (form) {
      e.preventDefault();
      form.requestSubmit();
    }
    return;
  }
  const typing = target.closest(
    'textarea, select, [contenteditable], input:not([type="range"]):not([type="checkbox"])',
  );
  if (typing) {
    if (e.key === 'Escape') {
      target.blur();
      target.closest('.story')?.focus({ preventScroll: true });
    }
    return;
  }
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === 'j' || e.key === 'k') {
    e.preventDefault();
    step(e.key === 'j' ? 1 : -1);
    return;
  }
  const id = target.closest('.story')?.dataset.id || current;
  const form = id && document.querySelector(`#story-${id} form.verdict`);
  if (!form) return;
  if (/^[0-9]$/.test(e.key) || e.key === '=') {
    e.preventDefault();
    form.dispatchEvent(new CustomEvent('score', { detail: e.key === '=' ? 10 : Number(e.key) }));
    setCurrent(id);
  } else if (e.key === 'n') {
    e.preventDefault();
    form.querySelector('textarea').focus();
    setCurrent(id);
  }
});

// ------------------------------------------------------------------ taste page
// QC's taste profile, straight from .agents/skills/qc-taste/references/taste/. Both languages
// are written files, so this page never goes through Google; it follows the language toggle.

function setView(next, { scroll = true } = {}) {
  view = next === 'taste' ? 'taste' : 'review';
  document.body.dataset.view = view;
  for (const link of document.querySelectorAll('.view-link')) {
    const on = link.dataset.view === view;
    link.classList.toggle('on', on);
    if (on) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  if (view === 'taste') {
    renderTaste();
    loadTaste();
  }
  if (scroll) window.scrollTo(0, 0);
}

addEventListener('hashchange', () => setView(location.hash === '#taste' ? 'taste' : 'review'));

async function loadTaste() {
  try {
    T = await api('/api/taste');
  } catch (err) {
    T = { error: err.message, parts: [] };
  }
  renderTaste();
}

// Just enough Markdown for the taste files: headings, paragraphs, lists, quotes, bold,
// italics and code. Everything is built as DOM text, never parsed as HTML.
function inlineMd(text) {
  const out = [];
  const re = /\*\*(.+?)\*\*|`([^`]+)`|\*([^*\s](?:[^*]*[^*\s])?)\*/g;
  let last = 0;
  let m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1] != null) out.push(h('strong', {}, inlineMd(m[1])));
    else if (m[2] != null) out.push(h('code', {}, m[2]));
    else out.push(h('em', {}, m[3]));
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function markdown(text) {
  const blocks = [];
  let para = [];
  let list = null;
  const flushPara = () => {
    if (!para.length) return;
    const kids = [];
    para.forEach((line, i) => {
      if (i) kids.push(para[i - 1].hard ? h('br') : ' ');
      kids.push(inlineMd(line.text));
    });
    blocks.push(h('p', {}, kids));
    para = [];
  };
  const flushList = () => {
    if (list) blocks.push(list);
    list = null;
  };
  for (const raw of text.replace(/\r\n/g, '\n').split('\n')) {
    const line = raw.trim();
    if (!line) {
      flushPara();
      flushList();
      continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      flushPara();
      flushList();
      blocks.push(h(`h${Math.min(heading[1].length + 2, 6)}`, {}, inlineMd(heading[2])));
      continue;
    }
    const item = /^[-*]\s+(.*)$/.exec(line);
    if (item) {
      flushPara();
      if (!list) list = h('ul', {});
      list.append(h('li', {}, inlineMd(item[1])));
      continue;
    }
    if (/^>\s?/.test(line)) {
      flushPara();
      flushList();
      blocks.push(h('blockquote', {}, inlineMd(line.replace(/^>\s?/, ''))));
      continue;
    }
    flushList();
    para.push({ text: line, hard: / {2,}$/.test(raw) });
  }
  flushPara();
  flushList();
  return blocks;
}

function syncClass(part) {
  if (part.problems.length || part.state === 'missing') return 'broken';
  return part.state === 'synced' ? '' : 'stale';
}

function tasteVersion(parts) {
  const shared = parts.find((p) => p.key === '_shared');
  const en = (shared && shared.texts.en) || '';
  const version = (/^Version:\s*(\S+)/m.exec(en) || [])[1];
  const date = (/^Evidence through:\s*(\S+)/m.exec(en) || [])[1];
  return version ? t('tasteVersion', { version, date: date || '?' }) : '';
}

function renderTaste() {
  const root = $('#taste');
  if (!T) {
    root.replaceChildren(h('p', { class: 'taste-note' }, t('tasteLoading')));
    return;
  }
  if (T.error) {
    root.replaceChildren(h('p', { class: 'offline' }, T.error));
    return;
  }
  const parts = T.parts;
  if (!parts.some((p) => p.key === tasteTab)) tasteTab = parts[0] && parts[0].key;
  const part = parts.find((p) => p.key === tasteTab);
  const tabs = h(
    'div',
    { class: 'taste-tabs', role: 'tablist', 'aria-label': t('tasteTabsAria') },
    parts.map((p) =>
      h(
        'button',
        {
          type: 'button',
          role: 'tab',
          class: `taste-tab${p.key === tasteTab ? ' on' : ''}${p.shared ? ' shared' : ''}`,
          'aria-selected': String(p.key === tasteTab),
          title: p.state_text[lang],
          onclick: () => {
            tasteTab = p.key;
            local.set('story-review:taste-tab', p.key);
            renderTaste();
          },
        },
        h('span', { class: `sync-dot ${syncClass(p)}`, 'aria-hidden': 'true' }),
        p.title[lang],
      ),
    ),
  );
  root.replaceChildren(
    ...[
      h(
        'header',
        { class: 'taste-head' },
        h('h2', {}, t('tasteTitle')),
        h('p', {}, t('tasteIntro')),
        h('p', { class: 'taste-version' }, tasteVersion(parts)),
      ),
      tabs,
      part ? tastePanel(part) : null,
    ].filter(Boolean),
  );
}

function tastePanel(part) {
  const other = lang === 'en' ? 'zh' : 'en';
  const shown = part.texts[lang] != null ? lang : other;
  const text = part.texts[shown];
  const cls = syncClass(part);
  const stateText = part.state_text[lang];
  const status = [
    h('span', { class: `sync-dot ${cls}`, 'aria-hidden': 'true' }),
    stateText.charAt(0).toUpperCase() + stateText.slice(1),
  ];
  if (part.stamped && part.state === 'synced') status.push(' · ', t('tasteStamped', { date: part.stamped }));
  return h(
    'section',
    { class: 'taste-panel', role: 'tabpanel' },
    h('p', { class: `taste-status ${cls}` }, status),
    part.problems.length ? h('ul', { class: 'taste-problems' }, part.problems.map((p) => h('li', {}, p))) : null,
    h(
      'p',
      { class: 'taste-note' },
      t('tasteUsedBy', { what: part.used_by[lang] }),
      part.shared ? null : t('tasteSep') + t('tasteWithShared'),
    ),
    shown !== lang
      ? h('p', { class: 'taste-note warn' }, t('tasteMissingLang', { lang: t('langName')[lang], other: t('langName')[other] }))
      : null,
    h('article', { class: 'md', lang: shown === 'zh' ? 'zh-CN' : 'en' }, text ? markdown(text) : null),
    h('p', { class: 'taste-files' }, t('tasteFiles'), h('code', {}, part.files.zh), ' · ', h('code', {}, part.files.en)),
  );
}

// ------------------------------------------------------------------ start

new ResizeObserver(() => {
  document.documentElement.style.setProperty('--topbar-h', `${$('.topbar').offsetHeight}px`);
}).observe($('.topbar'));

function connect() {
  const events = new EventSource('/api/events');
  events.addEventListener('open', () => {
    setOffline(null);
    soon();
  });
  events.addEventListener('changed', soon);
  events.addEventListener('job', soon);
  events.addEventListener('log', (e) => {
    try {
      appendLog(JSON.parse(e.data));
    } catch {
      /* ignore a malformed line */
    }
  });
  events.addEventListener('error', () => setOffline(t('reconnecting')));
}

applyStatic();
setView(location.hash === '#taste' ? 'taste' : 'review', { scroll: false });
refresh().finally(connect);
