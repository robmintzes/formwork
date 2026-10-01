/* Workspace wizard UI. Vanilla ES modules, no build step, no network access
   beyond this server's own endpoints. The CSP is script-src 'self'; style-src 'self',
   so everything here uses DOM APIs and CSSOM (element.style), never inline markup.

   Data flow: the draft's firm.json and tokens file are parsed once into
   app.firm / app.tokens, edited in place, and PUT back (debounced). Validation
   re-runs after each save so the diagnostics counts stay live. */

import { h, clear, append } from '/static/dom.js';
import * as T from '/static/tokens.js';

const TOKEN_KEY = 'toolkitWizardToken';
const SAVE_DELAY = 450;
const VALIDATE_DELAY = 700;

const STEPS = [
  { id: 'start', title: 'Start' },
  { id: 'identity', title: 'Identity' },
  { id: 'technical', title: 'Technical identity' },
  { id: 'logos', title: 'Logos' },
  { id: 'colour', title: 'Colour and type' },
  { id: 'components', title: 'Components' },
  { id: 'preview', title: 'Preview' },
  { id: 'generate', title: 'Generate' },
];

const app = {
  token: null,
  step: 'start',
  starters: [],
  draft: null,
  firm: null,
  tokens: null,
  tokensPath: 'tokens.tokens.json',
  version: 0,
  dirty: new Set(),
  pendingFiles: {},
  pendingRemove: [],
  saveTimer: null,
  validateTimer: null,
  validation: null,
  validatedVersion: -1,
  validating: false,
  previewStamp: 0,
  localImages: {},
  workspacePath: '',
  plan: null,
  generated: null,
  busy: false,
  stopped: false,
};

let view = { updaters: [], onValidated: null };
let uidCounter = 0;
const uid = (prefix) => prefix + '-' + String(++uidCounter);
const $ = (id) => document.getElementById(id);
const isObj = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

/* ---- status ---------------------------------------------------------------- */

function setStatus(message, kind) {
  const el = $('status');
  el.textContent = message || '';
  el.dataset.kind = kind || 'info';
}

function showError(error) {
  const message = error && error.message ? error.message : String(error);
  if (error && error.status === 403) {
    setStatus('Error: ' + message + ' Open the link printed by `python -m toolkit_cli serve`.', 'error');
  } else {
    setStatus('Error: ' + message, 'error');
  }
}

/* ---- token and API --------------------------------------------------------- */

function readToken() {
  let token = null;
  const hash = location.hash.replace(/^#/, '');
  if (hash) {
    token = new URLSearchParams(hash).get('token');
    if (token) {
      try { sessionStorage.setItem(TOKEN_KEY, token); } catch (error) { /* storage can be blocked */ }
    }
    history.replaceState(null, '', location.pathname + location.search);
  }
  if (!token) {
    try { token = sessionStorage.getItem(TOKEN_KEY); } catch (error) { token = null; }
  }
  return token || null;
}

class ApiError extends Error {
  constructor(code, message, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function api(method, path, body) {
  const headers = { 'X-Toolkit-Token': app.token };
  const init = { method, headers };
  if (method !== 'GET') {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body === undefined ? {} : body);
  }
  let response;
  try {
    response = await fetch(path, init);
  } catch (error) {
    throw new ApiError('network', 'Cannot reach the wizard server. Is it still running?', 0);
  }
  let data = null;
  try { data = await response.json(); } catch (error) { data = null; }
  if (!response.ok) {
    const detail = data && data.error ? data.error : null;
    throw new ApiError(
      detail && detail.code ? detail.code : 'http.' + response.status,
      detail && detail.message ? detail.message : 'Request failed (HTTP ' + response.status + ').',
      response.status,
    );
  }
  return data;
}

/* The server is single-threaded and the draft is one shared object: run every
   request that touches it strictly in order. */
let queue = Promise.resolve();
function enqueue(task) {
  const run = queue.then(task);
  queue = run.catch(() => undefined);
  return run;
}

/* ---- draft model ----------------------------------------------------------- */

function parseJson(text, name) {
  try {
    return JSON.parse(String(text).replace(/^\uFEFF/, ''));
  } catch (error) {
    throw new Error(name + ' in the draft is not valid JSON: ' + error.message);
  }
}

function modelsReady() {
  return Boolean(app.draft && app.firm && app.tokens);
}

function loadDraft(state) {
  clearTimeout(app.saveTimer);
  clearTimeout(app.validateTimer);
  app.saveTimer = null;
  app.validateTimer = null;
  app.draft = state;
  app.version = 0;
  app.dirty = new Set();
  app.pendingFiles = {};
  app.pendingRemove = [];
  app.validation = null;
  app.validatedVersion = -1;
  app.localImages = {};
  app.plan = null;
  app.generated = null;
  app.firm = null;
  app.tokens = null;
  const files = state.files || {};
  if (!files['firm.json'] || typeof files['firm.json'].text !== 'string') {
    throw new Error('The draft has no readable firm.json.');
  }
  const firm = parseJson(files['firm.json'].text, 'firm.json');
  const tokensPath = firm && firm.brand && typeof firm.brand.tokens === 'string' ? firm.brand.tokens : 'tokens.tokens.json';
  if (!files[tokensPath] || typeof files[tokensPath].text !== 'string') {
    throw new Error('The draft has no readable ' + tokensPath + '.');
  }
  app.tokensPath = tokensPath;
  app.tokens = parseJson(files[tokensPath].text, tokensPath);
  app.firm = firm;
}

function serialize(doc) {
  return JSON.stringify(doc, null, 2) + '\n';
}

/* Called after every edit to app.firm or app.tokens. */
function touch(kind) {
  app.dirty.add(kind);
  app.version += 1;
  app.generated = null;
  clearTimeout(app.saveTimer);
  app.saveTimer = setTimeout(() => {
    app.saveTimer = null;
    flushSave().then(scheduleValidate).catch(showError);
  }, SAVE_DELAY);
  updateRail();
}

/* Write dirty documents and pending files. Must run inside the queue or via flushSave. */
async function saveInner() {
  if (!app.dirty.size && !Object.keys(app.pendingFiles).length && !app.pendingRemove.length) return;
  const files = {};
  const sentDirty = new Set(app.dirty);
  if (sentDirty.has('firm')) files['firm.json'] = { text: serialize(app.firm) };
  if (sentDirty.has('tokens')) files[app.tokensPath] = { text: serialize(app.tokens) };
  const sentFiles = app.pendingFiles;
  Object.assign(files, sentFiles);
  const known = app.draft ? app.draft.files : {};
  const remove = app.pendingRemove.filter((path) => known[path] && !(path in files));
  app.dirty = new Set();
  app.pendingFiles = {};
  app.pendingRemove = [];
  try {
    const state = await api('PUT', '/api/files', { files, remove });
    app.draft = state;
  } catch (error) {
    for (const kind of sentDirty) app.dirty.add(kind);
    app.pendingFiles = Object.assign({}, sentFiles, app.pendingFiles);
    app.pendingRemove = remove.concat(app.pendingRemove);
    throw error;
  }
}

function flushSave() {
  clearTimeout(app.saveTimer);
  app.saveTimer = null;
  return enqueue(saveInner).finally(updateRail);
}

function scheduleValidate() {
  clearTimeout(app.validateTimer);
  app.validateTimer = setTimeout(() => {
    app.validateTimer = null;
    runValidate().catch(showError);
  }, VALIDATE_DELAY);
  updateRail();
}

function runValidate() {
  clearTimeout(app.validateTimer);
  app.validateTimer = null;
  clearTimeout(app.saveTimer);
  app.saveTimer = null;
  return enqueue(async () => {
    await saveInner();
    const version = app.version;
    app.validating = true;
    updateRail();
    try {
      const report = await api('POST', '/api/validate', {});
      if (version === app.version) {
        app.validation = report;
        app.validatedVersion = version;
        app.previewStamp = Date.now();
      }
      return report;
    } finally {
      app.validating = false;
      refreshLive();
    }
  });
}

/* ---- live refresh ---------------------------------------------------------- */

function updateRail() {
  for (const button of document.querySelectorAll('.step-btn')) {
    const id = button.dataset.step;
    if (id === app.step) button.setAttribute('aria-current', 'step');
    else button.removeAttribute('aria-current');
    button.disabled = app.stopped || (id !== 'start' && !modelsReady());
  }
  const counts = app.validation ? app.validation.counts : { error: 0, warning: 0, info: 0 };
  for (const name of ['error', 'warning', 'info']) {
    $('count-' + name).textContent = String(counts[name] || 0);
    $('count-' + name).parentElement.classList.toggle('has-' + name, (counts[name] || 0) > 0);
  }
  let text;
  if (!modelsReady()) text = 'No draft yet';
  else if (app.dirty.size || app.saveTimer || Object.keys(app.pendingFiles).length) text = 'Saving changes...';
  else if (app.validating) text = 'Validating...';
  else if (app.validateTimer) text = 'Changes pending validation';
  else if (app.validation && app.validatedVersion === app.version) text = 'Validated: ' + app.validation.outcome;
  else text = 'Not validated';
  $('live-state').textContent = text;
}

function matchesFile(location, name) {
  const file = location.split('#')[0];
  return file === name || file.endsWith('/' + name) || file.endsWith('\\' + name);
}

function diagnosticsFor(file, pointer) {
  if (!app.validation) return [];
  const name = file === 'tokens' ? app.tokensPath : 'firm.json';
  return app.validation.diagnostics.filter((item) => {
    const location = item.location || '';
    if (!location.includes('#') || !matchesFile(location, name)) return false;
    const target = location.slice(location.indexOf('#') + 1);
    return target === pointer || target.startsWith(pointer + '/');
  });
}

function refreshInlineDiagnostics() {
  for (const slot of $('main').querySelectorAll('.diag-slot')) {
    clear(slot);
    const items = diagnosticsFor(slot.dataset.file, slot.dataset.pointer);
    const input = slot.dataset.input ? $(slot.dataset.input) : null;
    for (const item of items) {
      const word = item.severity.charAt(0).toUpperCase() + item.severity.slice(1);
      slot.append(h('p', { class: 'diag-line sev-' + item.severity, text: word + ': ' + item.message + (item.hint ? ' ' + item.hint : '') }));
    }
    if (input) {
      if (items.some((item) => item.severity === 'error')) input.setAttribute('aria-invalid', 'true');
      else input.removeAttribute('aria-invalid');
    }
  }
}

function refreshLive() {
  updateRail();
  refreshInlineDiagnostics();
  if (view.onValidated) view.onValidated();
}

/* ---- field builders -------------------------------------------------------- */

function diagSlot(id, file, pointer, inputId) {
  return h('div', { class: 'diag-slot', id, 'data-file': file, 'data-pointer': pointer, 'data-input': inputId });
}

function textField(opts) {
  const id = uid('f');
  const describedBy = (opts.help ? id + '-help ' : '') + (opts.pointer ? id + '-diag' : '');
  const input = h('input', {
    type: opts.type || 'text',
    id,
    value: opts.value === undefined || opts.value === null ? '' : opts.value,
    class: opts.mono ? 'mono' : undefined,
    autocomplete: 'off',
    spellcheck: 'false',
    maxlength: opts.maxlength,
    min: opts.min,
    max: opts.max,
    step: opts.step,
    placeholder: opts.placeholder,
    'aria-describedby': describedBy.trim() || undefined,
    on: { input: (event) => opts.onInput(event.target.value, event.target) },
  });
  const root = h('div', { class: 'field' },
    h('label', { for: id, text: opts.label }),
    input,
    opts.help ? h('p', { class: 'help', id: id + '-help', text: opts.help }) : null,
    opts.pointer ? diagSlot(id + '-diag', opts.file || 'firm', opts.pointer, id) : null);
  return { root, input };
}

function getIn(obj, path) {
  let node = obj;
  for (const key of path) {
    if (!isObj(node) && !Array.isArray(node)) return undefined;
    node = node[key];
  }
  return node;
}

function setIn(obj, path, value) {
  let node = obj;
  for (let i = 0; i < path.length - 1; i += 1) {
    if (!isObj(node[path[i]])) node[path[i]] = {};
    node = node[path[i]];
  }
  node[path[path.length - 1]] = value;
}

function deleteIn(obj, path) {
  const parent = getIn(obj, path.slice(0, -1));
  if (isObj(parent)) delete parent[path[path.length - 1]];
}

function firmField(opts) {
  const path = opts.path;
  return textField({
    label: opts.label,
    help: opts.help,
    value: getIn(app.firm, path),
    pointer: '/' + path.join('/'),
    file: 'firm',
    maxlength: opts.maxlength,
    mono: opts.mono,
    placeholder: opts.placeholder,
    onInput: (value) => {
      if (opts.optional && value.trim() === '') deleteIn(app.firm, path);
      else setIn(app.firm, path, value);
      touch('firm');
    },
  });
}

function pageHead(title, lede) {
  return [h('h2', { id: 'step-title', tabindex: '-1', text: title }), lede ? h('p', { class: 'lede', text: lede }) : null];
}

function navRow(root) {
  const index = STEPS.findIndex((step) => step.id === app.step);
  const back = index > 0 ? h('button', { type: 'button', class: 'btn secondary', text: 'Back', on: { click: () => goTo(STEPS[index - 1].id) } }) : h('span');
  const next = index < STEPS.length - 1
    ? h('button', { type: 'button', class: 'btn', text: 'Next', disabled: !modelsReady(), on: { click: () => goTo(STEPS[index + 1].id) } })
    : h('span');
  root.append(h('div', { class: 'nav-row' }, back, next));
}

/* ---- diagnostics view ------------------------------------------------------ */

function diagnosticsView(list, emptyText) {
  if (!list.length) return h('p', { class: 'help', text: emptyText || 'No diagnostics.' });
  const wrap = h('div');
  const titles = { error: 'Errors', warning: 'Warnings', info: 'Info' };
  for (const severity of ['error', 'warning', 'info']) {
    const items = list.filter((item) => item.severity === severity);
    if (!items.length) continue;
    wrap.append(h('section', { class: 'diag-group' },
      h('h4', { text: titles[severity] + ' (' + items.length + ')' }),
      items.map((item) => h('div', { class: 'diag-item sev-' + severity },
        h('span', { class: 'code', text: item.code }),
        ' ',
        item.location ? h('span', { class: 'loc', text: item.location }) : null,
        h('p', { text: item.message }),
        item.hint ? h('p', { class: 'hint', text: item.hint }) : null))));
  }
  return wrap;
}

/* ---- step 1: start --------------------------------------------------------- */

async function startDraft(body, label) {
  if (app.draft && app.version > 0 && !window.confirm('Replace the current draft? Edits made in this wizard are discarded.')) return;
  setStatus('Loading ' + label + '...', 'info');
  try {
    const state = await enqueue(() => api('POST', '/api/start', body));
    loadDraft(state);
    if (body.workspace) app.workspacePath = body.workspace.trim();
    setStatus('Loaded ' + label + '. Continue with Identity.', 'ok');
    runValidate().catch(showError);
  } catch (error) {
    showError(error);
  }
  renderStep();
  updateRail();
}

function renderStart(root) {
  append(root, pageHead('Start', 'Pick a starter profile to copy into a draft, or open an existing generated workspace to edit its firm inputs. The draft lives in this session; nothing is written to disk until Generate.'));

  const cards = h('div', { class: 'cards', role: 'group', 'aria-label': 'Starter profiles' });
  for (const starter of app.starters) {
    const selected = app.draft && app.draft.source === 'profile:' + starter.id;
    cards.append(h('button', {
      type: 'button',
      class: 'card-btn',
      'aria-pressed': selected ? 'true' : 'false',
      on: { click: () => startDraft({ profile: starter.id }, 'starter ' + starter.display_name) },
    },
    h('h3', null, starter.display_name, starter.fictional ? h('span', { class: 'badge neutral', text: 'Fictional example' }) : null),
    h('p', { text: starter.description })));
  }
  root.append(cards);

  root.append(h('hr', { class: 'sep' }));
  root.append(h('h3', { text: 'Open an existing workspace' }));
  const pathField = textField({
    label: 'Workspace folder (absolute path)',
    help: 'A folder previously generated by this toolkit. Its firm/ inputs become the draft.',
    value: app.draft && app.draft.source === 'workspace' ? app.workspacePath : '',
    mono: true,
    placeholder: 'C:\\Firm\\Workspace',
    onInput: () => undefined,
  });
  const openButton = h('button', {
    type: 'button',
    class: 'btn',
    text: 'Open workspace',
    on: { click: () => startDraft({ workspace: pathField.input.value }, 'workspace') },
  });
  root.append(h('div', { class: 'inline-row' }, pathField.root, openButton));

  if (modelsReady()) {
    root.append(h('div', { class: 'callout ok' },
      h('strong', { text: 'Draft ready. ' }),
      'Source: ', h('code', { text: app.draft.source }),
      ' - ' + Object.keys(app.draft.files).length + ' files.'));
  }
  navRow(root);
}

/* ---- step 2: identity ------------------------------------------------------ */

function renderIdentity(root) {
  append(root, pageHead('Identity', 'How the firm appears in tool metadata, guide titles, and specimens. These are display strings: safe to change at any time. They never rename paths or identifiers.'));
  const fields = [
    { label: 'Display name', path: ['identity', 'display_name'], maxlength: 80, help: 'Guide titles, specimen header, extension description. Up to 80 characters.' },
    { label: 'Short name', path: ['identity', 'short_name'], maxlength: 24, help: 'Compact labels. Up to 24 characters.' },
    { label: 'Author', path: ['identity', 'author'], maxlength: 80, help: 'Written into tool metadata (__author__, bundle.yaml, extension.json).' },
    { label: 'Logo alt text', path: ['identity', 'logo_alt'], maxlength: 80, help: 'Accessible name for logo images.' },
    { label: 'Support link', path: ['identity', 'links', 'support'], mono: true, placeholder: 'Must start with https', help: 'Required. Used as the tool help link and in the guide footer. https only.' },
    { label: 'Documentation link (optional)', path: ['identity', 'links', 'documentation'], optional: true, mono: true, placeholder: 'Must start with https', help: 'Optional. Leave blank to omit. https only.' },
  ];
  for (const spec of fields) root.append(firmField(spec).root);
  navRow(root);
  refreshInlineDiagnostics();
}

/* ---- step 3: technical identity -------------------------------------------- */

function renderTechnical(root) {
  append(root, pageHead('Technical identity', 'Stable identifiers that other files and folders are derived from.'));
  root.append(h('div', { class: 'callout warn', role: 'note' },
    h('strong', { text: 'Stable identifiers. ' }),
    'These become folder names, CSS and XAML key prefixes, and the workspace manifest identity. Renaming them after a workspace exists is a migration (old managed files become obsolete), not a rebrand.'));
  const fields = [
    { label: 'Namespace', path: ['technical', 'namespace'], mono: true, maxlength: 24, help: 'Lowercase letters and digits, 2-24 characters, starting with a letter. Prefixes CSS custom properties and XAML keys.' },
    { label: 'Workspace id', path: ['technical', 'workspace_id'], mono: true, maxlength: 64, help: 'Kebab-case, up to 64 characters. Identifies the workspace; rendering refuses a workspace initialised for another id.' },
    { label: 'pyRevit extension', path: ['technical', 'pyrevit', 'extension'], mono: true, maxlength: 40, help: 'Letters and digits, starting with a letter. Becomes the <name>.extension folder.' },
    { label: 'pyRevit tab', path: ['technical', 'pyrevit', 'tab'], mono: true, maxlength: 40, help: 'Letters, digits, single spaces. Becomes the <name>.tab folder that pyRevit shows on the ribbon.' },
    { label: 'pyRevit sample panel', path: ['technical', 'pyrevit', 'sample_panel'], mono: true, maxlength: 40, help: 'Same rules as the tab. Becomes the panel folder for the foundation sample.' },
  ];
  for (const spec of fields) root.append(firmField(spec).root);

  root.append(h('h3', { text: 'Maintainers' }));
  root.append(h('p', { class: 'help', text: 'At least one. The branch prefix is lowercase kebab-case; branch policy expects each maintainer\'s branches to start with it.' }));
  const list = h('div');
  root.append(list);
  const renderMaintainers = () => {
    clear(list);
    const maintainers = Array.isArray(app.firm.maintainers) ? app.firm.maintainers : [];
    maintainers.forEach((maintainer, index) => {
      const name = textField({
        label: 'Maintainer ' + (index + 1) + ' name',
        value: maintainer.name,
        maxlength: 80,
        pointer: '/maintainers/' + index + '/name',
        onInput: (value) => { maintainer.name = value; touch('firm'); },
      });
      const prefix = textField({
        label: 'Maintainer ' + (index + 1) + ' branch prefix',
        value: maintainer.branch_prefix,
        mono: true,
        maxlength: 39,
        pointer: '/maintainers/' + index + '/branch_prefix',
        onInput: (value) => { maintainer.branch_prefix = value; touch('firm'); },
      });
      const remove = h('button', {
        type: 'button',
        class: 'btn secondary small',
        text: 'Remove',
        'aria-label': 'Remove maintainer ' + (index + 1),
        disabled: maintainers.length <= 1,
        on: { click: () => { maintainers.splice(index, 1); touch('firm'); renderMaintainers(); refreshInlineDiagnostics(); } },
      });
      list.append(h('div', { class: 'inline-row' }, name.root, prefix.root, remove));
    });
    list.append(h('p', null, h('button', {
      type: 'button',
      class: 'btn secondary small',
      text: 'Add maintainer',
      on: {
        click: () => {
          if (!Array.isArray(app.firm.maintainers)) app.firm.maintainers = [];
          app.firm.maintainers.push({ name: '', branch_prefix: '' });
          touch('firm');
          renderMaintainers();
        },
      },
    })));
  };
  renderMaintainers();

  root.append(h('h3', { text: 'Governance' }));
  const approvals = textField({
    label: 'Required approvals (optional)',
    type: 'number',
    min: 0,
    max: 6,
    step: 1,
    value: getIn(app.firm, ['governance', 'required_approvals']),
    pointer: '/governance/required_approvals',
    help: 'Whole number 0-6. Leave blank for the default: 0 with one maintainer, 1 with more. Only used when the governance surface is enabled.',
    onInput: (value) => {
      const trimmed = value.trim();
      if (trimmed === '') {
        deleteIn(app.firm, ['governance', 'required_approvals']);
        if (isObj(app.firm.governance) && Object.keys(app.firm.governance).length === 0) delete app.firm.governance;
      } else {
        setIn(app.firm, ['governance', 'required_approvals'], Number(trimmed));
      }
      touch('firm');
    },
  });
  root.append(approvals.root);
  navRow(root);
  refreshInlineDiagnostics();
}

/* ---- step 4: logos --------------------------------------------------------- */

const SLOTS = [['wordmark', 'Wordmark'], ['symbol', 'Symbol']];
const VARIANTS = [
  ['light', 'Light', 'For light surfaces.'],
  ['inverse', 'Inverse', 'For dark and brand-colour surfaces. Optional; falls back to light with a warning.'],
];

function assetPath(slot, variant, format) {
  const existing = getIn(app.firm, ['brand', 'assets', slot, variant, format]);
  return typeof existing === 'string' && existing ? existing : 'assets/' + slot + '-' + variant + '.' + format;
}

function readBase64(file) {
  return new Promise((resolvePromise, rejectPromise) => {
    const reader = new FileReader();
    reader.addEventListener('load', () => {
      const result = String(reader.result);
      resolvePromise(result.slice(result.indexOf(',') + 1));
    });
    reader.addEventListener('error', () => rejectPromise(new Error('Could not read ' + file.name + '.')));
    reader.readAsDataURL(file);
  });
}

const PNG_SIGNATURE = 'iVBORw0KGgo';

async function acceptLogo(slot, variant, format, file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.' + format)) throw new Error('Choose a .' + format + ' file for the ' + format.toUpperCase() + ' slot.');
  if (file.size > 8 * 1024 * 1024) throw new Error(file.name + ' is larger than 8 MiB.');
  const base64 = await readBase64(file);
  if (format === 'png' && !base64.startsWith(PNG_SIGNATURE)) throw new Error(file.name + ' is not a PNG file.');
  if (format === 'svg' && !atob(base64).includes('<svg')) throw new Error(file.name + ' does not look like an SVG file.');
  const path = assetPath(slot, variant, format);
  setIn(app.firm, ['brand', 'assets', slot, variant, format], path);
  app.pendingFiles[path] = { base64 };
  app.localImages[path] = 'data:' + (format === 'png' ? 'image/png' : 'image/svg+xml') + ';base64,' + base64;
  touch('firm');
  setStatus('Staged ' + file.name + ' as ' + path + '.', 'ok');
}

function thumbSource(slot, variant, format) {
  const path = getIn(app.firm, ['brand', 'assets', slot, variant, format]);
  if (!path) return null;
  if (app.localImages[path]) return app.localImages[path];
  if (format === 'svg') {
    const file = app.draft.files[path];
    return file && typeof file.text === 'string' ? 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(file.text) : null;
  }
  const previewPath = 'assets/brand/' + slot + '-' + variant + '.png';
  if (app.validation && app.validatedVersion === app.version && (app.validation.preview_files || []).includes(previewPath)) {
    return '/preview/' + previewPath + '?v=' + app.previewStamp;
  }
  return null;
}

function thumb(slot, variant, format) {
  const src = thumbSource(slot, variant, format);
  const dark = variant === 'inverse';
  const label = slot + ' ' + variant + ' ' + format.toUpperCase();
  const box = h('div', { class: 'box ' + (dark ? 'on-dark' : 'on-light') },
    src
      ? h('img', { src, alt: label + ' preview' })
      : h('span', { class: 'none', text: getIn(app.firm, ['brand', 'assets', slot, variant, format]) ? (format === 'png' ? 'Preview after validation' : 'No preview') : 'Not set' }));
  return h('div', { class: 'thumb' }, h('span', { class: 'label', text: format.toUpperCase() }), box);
}

function renderLogos(root) {
  append(root, pageHead('Logos', 'Each logo variant needs an SVG for web surfaces and a PNG for WPF, which cannot render SVG. Files are staged in the draft and written on Generate.'));
  root.append(h('p', { class: 'help', text: 'SVGs must not contain scripts or external references. PNGs are checked structurally by the server.' }));
  const grid = h('div', { class: 'logo-grid' });
  root.append(grid);

  const renderCards = () => {
    clear(grid);
    for (const [slot, slotTitle] of SLOTS) {
      for (const [variant, variantTitle, variantHelp] of VARIANTS) {
        const present = Boolean(getIn(app.firm, ['brand', 'assets', slot, variant]));
        const card = h('div', { class: 'logo-card' },
          h('h3', { text: slotTitle + ': ' + variantTitle }),
          h('p', { class: 'help', text: variantHelp }),
          h('div', { class: 'thumbs' }, thumb(slot, variant, 'svg'), thumb(slot, variant, 'png')));
        for (const format of ['svg', 'png']) {
          const id = uid('logo');
          const input = h('input', {
            type: 'file',
            id,
            accept: format === 'svg' ? '.svg,image/svg+xml' : '.png,image/png',
            on: {
              change: async (event) => {
                const file = event.target.files[0];
                try {
                  await acceptLogo(slot, variant, format, file);
                  renderCards();
                } catch (error) {
                  showError(error);
                  event.target.value = '';
                }
              },
            },
          });
          card.append(h('div', { class: 'field' },
            h('label', { for: id, text: (present ? 'Replace ' : 'Upload ') + format.toUpperCase() }),
            input,
            h('p', { class: 'help', text: 'Draft path: ' + assetPath(slot, variant, format) }),
            diagSlot(id + '-diag', 'firm', '/brand/assets/' + slot + '/' + variant + '/' + format, id)));
        }
        if (variant === 'inverse' && present) {
          card.append(h('button', {
            type: 'button',
            class: 'btn secondary small',
            text: 'Remove inverse variant',
            'aria-label': 'Remove ' + slot + ' inverse variant',
            on: { click: () => removeInverse(slot, renderCards) },
          }));
        }
        grid.append(card);
      }
    }
    refreshInlineDiagnostics();
  };

  view.onValidated = renderCards;
  renderCards();
  navRow(root);
}

function removeInverse(slot, rerender) {
  for (const format of ['svg', 'png']) {
    const path = getIn(app.firm, ['brand', 'assets', slot, 'inverse', format]);
    if (!path) continue;
    delete app.pendingFiles[path];
    delete app.localImages[path];
    if (app.draft.files[path]) app.pendingRemove.push(path);
  }
  deleteIn(app.firm, ['brand', 'assets', slot, 'inverse']);
  touch('firm');
  rerender();
}

/* ---- step 5: colour and type ----------------------------------------------- */

function runUpdaters(skip) {
  const palette = T.paletteTokens(app.tokens);
  view.usage = T.paletteUsage(app.tokens, palette);
  for (const update of view.updaters) update(skip);
}

function colorRow(path, options) {
  const hexId = uid('hex');
  const swatch = h('div', { class: 'swatch', 'aria-hidden': 'true' });
  const picker = h('input', { type: 'color', 'aria-label': path + ' colour picker' });
  const hexInput = h('input', {
    type: 'text', id: hexId, class: 'mono', maxlength: 7, spellcheck: 'false', autocomplete: 'off',
    'aria-describedby': hexId + '-diag',
  });
  const via = h('span', { class: 'via' });
  const row = h('div', { class: 'color-row' },
    h('div', { class: 'name' }, h('label', { for: hexId, text: options.label || path })),
    swatch, picker, hexInput, via,
    diagSlot(hexId + '-diag', 'tokens', '/' + path.split('.').join('/'), hexId));

  const apply = (hex, origin) => {
    T.setColor(app.tokens, path, hex);
    touch('tokens');
    runUpdaters(origin);
  };
  picker.addEventListener('input', () => apply(T.normalizeHex(picker.value), picker));
  hexInput.addEventListener('input', () => {
    const hex = T.normalizeHex(hexInput.value);
    if (hex) {
      hexInput.removeAttribute('aria-invalid');
      apply(hex, hexInput);
    } else {
      hexInput.setAttribute('aria-invalid', 'true');
    }
  });
  hexInput.addEventListener('change', () => { hexInput.removeAttribute('aria-invalid'); runUpdaters(null); });

  view.updaters.push((skip) => {
    const result = T.resolveColor(app.tokens, path);
    if (result.error) {
      swatch.style.backgroundColor = 'transparent';
      via.textContent = result.error;
      return;
    }
    swatch.style.backgroundColor = result.hex;
    if (skip !== picker) picker.value = result.hex.toLowerCase();
    if (skip !== hexInput) hexInput.value = result.hex;
    let text = result.chain.length ? 'alias ' + result.chain.join(' > ') : 'literal';
    if (options.usage && view.usage) {
      const count = view.usage[path] || 0;
      text += ' | used by ' + count + (count === 1 ? ' role' : ' roles');
    }
    via.textContent = text;
  });
  return row;
}

function cssFamily(name) {
  return ['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui'].includes(name) ? name : JSON.stringify(name);
}

function contrastRow(pair) {
  const sample = h('span', { class: 'sample-cell', text: 'Aa' });
  const ratio = h('td', { class: 'mono' });
  const verdict = h('span', { class: 'badge neutral', text: '...' });
  const row = h('tr', null,
    h('td', { class: 'mono', text: pair.fg.replace('color.', '') }),
    h('td', { class: 'mono', text: pair.bg.replace('color.', '') }),
    h('td', null, sample),
    ratio,
    h('td', null, verdict, ' ', h('span', { class: 'help', text: 'min ' + pair.min + ':1' })));
  view.updaters.push(() => {
    const fg = T.resolveColor(app.tokens, pair.fg);
    const bg = T.resolveColor(app.tokens, pair.bg);
    if (fg.error || bg.error) {
      ratio.textContent = 'n/a';
      verdict.className = 'badge fail';
      verdict.textContent = 'Unresolved';
      return;
    }
    const value = T.contrastRatio(fg.hex, bg.hex);
    sample.style.color = fg.hex;
    sample.style.backgroundColor = bg.hex;
    ratio.textContent = value.toFixed(2) + ':1';
    const ok = value >= pair.min;
    verdict.className = 'badge ' + (ok ? 'pass' : 'warn');
    verdict.textContent = ok ? 'Pass' : 'Warn';
  });
  return row;
}

function renderColour(root) {
  append(root, pageHead('Colour and type', 'Semantic roles are what generated tools use. Most are aliases into the palette. Editing a role writes a literal colour into that role; editing a palette colour changes every role aliased to it.'));
  const doc = app.tokens;

  root.append(h('h3', { text: 'Colour roles' }));
  for (const group of T.COLOR_GROUPS) {
    root.append(h('h4', { class: 'label', text: group.title }));
    root.append(h('div', { class: 'role-grid' }, group.roles.map((role) => colorRow(role, { label: role.replace('color.', '') }))));
  }

  root.append(h('h3', { text: 'Palette' }));
  root.append(h('p', { class: 'help', text: 'Primitive colours. Changing one updates every role that aliases it.' }));
  const palette = T.paletteTokens(doc);
  const groups = [];
  for (const item of palette) {
    let group = groups.find((entry) => entry.name === item.group);
    if (!group) { group = { name: item.group, items: [] }; groups.push(group); }
    group.items.push(item.path);
  }
  for (const group of groups) {
    root.append(h('div', { class: 'palette-group' },
      h('h4', { text: 'palette.' + group.name }),
      h('div', { class: 'palette-grid' }, group.items.map((path) => colorRow(path, { label: path.replace('palette.', ''), usage: true })))));
  }

  root.append(h('h3', { text: 'Typography' }));
  root.append(h('p', { class: 'help', text: 'Font stacks are comma-separated; the first family that is installed or packaged wins. Samples use fonts available in this browser.' }));
  const stackGrid = h('div', { class: 'type-grid' });
  for (const role of T.FONT_STACKS) {
    const resolved = T.resolve(doc, 'font.' + role);
    const sample = h('p', { class: 'sample-type', text: 'The quick brown fox 0123456789' });
    const setSample = (list) => { sample.style.fontFamily = list.map(cssFamily).join(', '); };
    setSample(resolved.ok && Array.isArray(resolved.value) ? resolved.value : []);
    const field = textField({
      label: 'font.' + role,
      value: resolved.ok ? T.stackText(resolved.value) : '',
      mono: true,
      pointer: '/font/' + role,
      file: 'tokens',
      onInput: (value, input) => {
        const list = T.parseStack(value);
        if (!list.length) { input.setAttribute('aria-invalid', 'true'); return; }
        input.removeAttribute('aria-invalid');
        T.setFontStack(doc, role, list);
        setSample(list);
        touch('tokens');
      },
    });
    field.root.append(sample);
    stackGrid.append(field.root);
  }
  root.append(stackGrid);

  root.append(h('h4', { class: 'label', text: 'Weights' }));
  const weightGrid = h('div', { class: 'type-grid' });
  for (const role of T.FONT_WEIGHTS) {
    const resolved = T.resolve(doc, 'font-weight.' + role);
    weightGrid.append(textField({
      label: 'font-weight.' + role,
      value: resolved.ok ? String(resolved.value) : '',
      mono: true,
      inputmode: 'numeric',
      pointer: '/font-weight/' + role,
      file: 'tokens',
      help: 'A number from 1 to 1000.',
      onInput: (value, input) => {
        if (value.trim() === '') { input.setAttribute('aria-invalid', 'true'); return; }
        input.removeAttribute('aria-invalid');
        T.setFontWeight(doc, role, value);
        touch('tokens');
      },
    }).root);
  }
  root.append(weightGrid);

  root.append(h('h4', { class: 'label', text: 'Sizes (px)' }));
  const sizeGrid = h('div', { class: 'type-grid' });
  for (const role of T.FONT_SIZES) {
    const resolved = T.resolve(doc, 'font-size.' + role);
    const px = resolved.ok ? T.dimensionPx(resolved.value) : null;
    sizeGrid.append(textField({
      label: 'font-size.' + role,
      type: 'number',
      min: 1,
      step: 1,
      value: px === null ? '' : px,
      pointer: '/font-size/' + role,
      file: 'tokens',
      onInput: (value, input) => {
        const number = Number(value);
        if (value.trim() === '' || !Number.isFinite(number) || number <= 0) { input.setAttribute('aria-invalid', 'true'); return; }
        input.removeAttribute('aria-invalid');
        T.setFontSize(doc, role, number);
        touch('tokens');
      },
    }).root);
  }
  root.append(sizeGrid);

  root.append(h('h3', { text: 'Contrast' }));
  root.append(h('p', { class: 'help', text: 'WCAG 2.x ratios computed here from the resolved colours (alpha ignored). Text needs 4.5:1; the focus ring needs 3:1 against the default surface. The server\'s a11y.contrast diagnostics are authoritative.' }));
  const body = h('tbody');
  for (const pair of T.CONTRAST_PAIRS) body.append(contrastRow(pair));
  root.append(h('div', { class: 'table-wrap' }, h('table', null,
    h('caption', { class: 'sr-only', text: 'Contrast ratios for role pairs' }),
    h('thead', null, h('tr', null,
      h('th', { scope: 'col', text: 'Foreground' }), h('th', { scope: 'col', text: 'Background' }),
      h('th', { scope: 'col', text: 'Sample' }), h('th', { scope: 'col', text: 'Ratio' }), h('th', { scope: 'col', text: 'Result' }))),
    body)));

  runUpdaters(null);
  navRow(root);
  refreshInlineDiagnostics();
}

/* ---- step 6: components ---------------------------------------------------- */

const SHAPES = [
  ['square', 'Square', 'Corner radius 0.'],
  ['rounded', 'Rounded', 'Corner radius from the radius.rounded token.'],
  ['pill', 'Pill', 'Fully rounded ends, half the element height.'],
];
const CASES = [
  ['as-written', 'As written', 'Labels appear exactly as authored.'],
  ['uppercase', 'Uppercase', 'Labels render in capitals.'],
];
const APPEARANCE = [
  { path: ['button', 'primary'], legend: 'Primary button', options: [
    ['solid', 'Solid', 'Filled with the primary action colours.'],
    ['outline', 'Outline', 'Transparent fill with a bordered edge.'],
  ] },
  { path: ['button', 'secondary'], legend: 'Secondary button', options: [
    ['outline', 'Outline', 'Border on a plain fill.'],
    ['tonal', 'Tonal', 'Soft accent fill.'],
    ['ghost', 'Ghost', 'Text only until hover or focus.'],
  ] },
  { path: ['button', 'shape'], legend: 'Button shape', options: SHAPES },
  { path: ['button', 'label_case'], legend: 'Button label case', options: CASES },
  { path: ['badge', 'style'], legend: 'Badge style', options: [
    ['soft', 'Soft', 'Tinted background with coloured text.'],
    ['solid', 'Solid', 'Filled with the foreground colour.'],
    ['outline', 'Outline', 'Border only.'],
  ] },
  { path: ['badge', 'shape'], legend: 'Badge shape', options: SHAPES },
  { path: ['badge', 'label_case'], legend: 'Badge label case', options: CASES },
  { path: ['decorations', 'registration_marks'], legend: 'Registration marks', boolean: true, options: [
    ['true', 'On', 'Print-style corner marks on guide and specimen surfaces. The WPF adapter renders none in v1.'],
    ['false', 'Off', 'No decorative marks.'],
  ] },
];

const SURFACES = [
  ['pyrevit-sample', 'pyRevit sample', 'Extension manifest and a read-only Hello Button bundle with light and dark icons.'],
  ['wpf-specimen', 'WPF specimen', 'Theme.xaml, Controls.xaml, a specimen window, and a PowerShell runner for checking native rendering.'],
  ['html-guide', 'HTML guide', 'Self-contained Hello Button guide with brand header and component specimen.'],
  ['governance', 'Governance files', 'AGENTS.md and client pointers, branch policy, CI workflow, ruleset, and vendored validators.'],
  ['mcp-bridge', 'MCP bridge', 'Read-only Revit MCP bridge inside the extension, an external FastMCP server, and a guide. Requires the pyRevit sample.'],
  ['ui-kit', 'Tool UI kit', 'Branded WPF dialogs for pyRevit tools (chooser, selector, result) with a read-only demo button. Requires the pyRevit sample.'],
  ['web-host', 'Web tool host', 'WebView2 host for pyRevit tools whose interface is HTML, using the WebView2 files that ship with Revit, plus a read-only report-console demo button. Requires the pyRevit sample.'],
  ['revit-addin', 'Revit add-in starter', 'C# add-in project (Revit 2025-2027) with a ribbon button and a read-only command that uses the same theme. Builds with the .NET SDK; no NuGet packages.'],
  ['python-app', 'Python report app', 'Stdlib-only Python command line that turns a CSV or JSON table into a branded offline HTML report. No install step.'],
  ['web-app', 'TypeScript web app', 'Dependency-free TypeScript web starter with a loopback-only static server and a branded app shell. Runs on Node 22.18 or newer with no install step.'],
];

function renderComponents(root) {
  append(root, pageHead('Components', 'Treatments for buttons and badges, and which surfaces to generate. The Preview step shows the effect on the HTML guide.'));
  for (const spec of APPEARANCE) {
    const name = uid('appearance');
    const current = getIn(app.firm, ['appearance', ...spec.path]);
    const currentKey = spec.boolean ? String(current) : current;
    const options = spec.options.slice();
    if (!options.some((option) => option[0] === currentKey)) {
      options.push([String(currentKey), String(currentKey) + ' (unrecognised)', 'Not a known choice; pick one of the others.']);
    }
    const fieldset = h('fieldset', null, h('legend', { text: spec.legend }));
    for (const [value, title, help] of options) {
      const id = uid('opt');
      fieldset.append(h('div', { class: 'choice' },
        h('input', {
          type: 'radio', id, name, value, checked: value === currentKey, 'aria-describedby': id + '-help',
          on: {
            change: () => {
              setIn(app.firm, ['appearance', ...spec.path], spec.boolean ? value === 'true' : value);
              touch('firm');
            },
          },
        }),
        h('label', { for: id, text: title }),
        h('p', { class: 'help', id: id + '-help', text: help })));
    }
    fieldset.append(diagSlot(name + '-diag', 'firm', '/appearance/' + spec.path.join('/')));
    root.append(fieldset);
  }

  root.append(h('h3', { text: 'Surfaces' }));
  const surfaces = h('fieldset', null, h('legend', { text: 'Generate these surfaces' }));
  const selected = () => (Array.isArray(app.firm.surfaces) ? app.firm.surfaces : []);
  for (const [id, title, help] of SURFACES) {
    const inputId = uid('surface');
    surfaces.append(h('div', { class: 'choice' },
      h('input', {
        type: 'checkbox', id: inputId, checked: selected().includes(id), 'aria-describedby': inputId + '-help',
        on: {
          change: (event) => {
            const keep = selected().filter((entry) => entry !== id);
            const known = SURFACES.map((entry) => entry[0]);
            const next = known.filter((entry) => (entry === id ? event.target.checked : keep.includes(entry)));
            app.firm.surfaces = next.concat(keep.filter((entry) => !known.includes(entry)));
            touch('firm');
          },
        },
      }),
      h('label', { for: inputId, text: title }),
      h('p', { class: 'help', id: inputId + '-help', text: help })));
  }
  surfaces.append(h('p', { class: 'help', text: 'At least one surface is required.' }));
  surfaces.append(diagSlot(uid('surface') + '-diag', 'firm', '/surfaces'));
  root.append(surfaces);
  navRow(root);
  refreshInlineDiagnostics();
}

/* ---- step 7: preview ------------------------------------------------------- */

function renderPreview(root) {
  append(root, pageHead('Preview', 'Validate the draft and look at the generated HTML guide.'));
  root.append(h('div', { class: 'callout', role: 'note' },
    h('strong', { text: 'Approximation. ' }),
    'The browser preview approximates web surfaces only. Native WPF rendering must be checked with specimens/wpf/show-specimen.ps1 in the generated workspace.'));

  const validateButton = h('button', { type: 'button', class: 'btn', text: 'Validate now', on: { click: () => { setStatus('Validating...', 'info'); runValidate().then(report => setStatus('Validation ' + report.outcome + '.', report.outcome === 'pass' ? 'ok' : 'error')).catch(showError); } } });
  root.append(h('p', null, validateButton));
  const body = h('div');
  root.append(body);

  const renderBody = () => {
    clear(body);
    const report = app.validation;
    if (!report) {
      body.append(h('p', { class: 'help', text: 'Not validated yet.' }));
      return;
    }
    const stale = app.validatedVersion !== app.version;
    body.append(h('p', null,
      h('span', { class: 'badge ' + (report.outcome === 'pass' ? 'pass' : 'fail'), text: report.outcome }),
      ' ' + report.counts.error + ' errors, ' + report.counts.warning + ' warnings, ' + report.counts.info + ' info.',
      stale ? ' Edits since this run are not yet validated.' : ''));
    body.append(diagnosticsView(report.diagnostics, 'No diagnostics.'));
    if (report.outcome === 'pass' && !stale && (report.preview_files || []).includes('docs/guides/hello-button.html')) {
      body.append(h('h3', { text: 'HTML guide' }));
      body.append(h('iframe', {
        class: 'preview',
        title: 'Generated Hello Button guide',
        /* No scripts in previewed output; same-origin keeps the preview cookie working. */
        sandbox: 'allow-same-origin',
        src: '/preview/docs/guides/hello-button.html?v=' + app.previewStamp,
      }));
      body.append(h('details', null,
        h('summary', { text: 'Generated files (' + report.preview_files.length + ')' }),
        h('div', { class: 'table-wrap' }, h('table', null, h('tbody', null, report.preview_files.map((path) => h('tr', null, h('td', { class: 'path', text: path }))))))));
    } else if (report.outcome !== 'pass') {
      body.append(h('div', { class: 'callout warn', text: 'No preview while the draft has errors.' }));
    }
  };
  view.onValidated = renderBody;
  renderBody();
  if (!app.validation) runValidate().catch(showError);
  navRow(root);
}

/* ---- step 8: generate ------------------------------------------------------ */

const ACTION_ORDER = ['conflict', 'create', 'update', 'adopt', 'delete', 'forget', 'skip', 'unchanged'];

function planView(plan) {
  const wrap = h('div');
  const data = plan.data;
  wrap.append(h('p', null,
    h('span', { class: 'badge ' + (data.outcome === 'pass' ? 'pass' : 'fail'), text: 'Plan ' + data.outcome }),
    ' ',
    data.initialized ? 'Existing workspace: changes below are applied on top of it.' : 'New workspace: nothing exists at this path yet.'));
  const groups = {};
  for (const action of data.actions || []) {
    if (!groups[action.action]) groups[action.action] = [];
    groups[action.action].push(action);
  }
  const names = Object.keys(groups).sort((a, b) => {
    const ia = ACTION_ORDER.indexOf(a);
    const ib = ACTION_ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
  });
  wrap.append(h('div', { class: 'chips' }, names.map((name) => h('span', { class: 'chip' + (name === 'conflict' ? ' conflict' : ''), text: name + ' ' + groups[name].length }))));
  for (const name of names) {
    const items = groups[name];
    const open = !['unchanged', 'skip'].includes(name);
    const details = h('details', { class: name === 'conflict' ? 'conflict' : undefined, open },
      h('summary', { text: name + ' (' + items.length + ')' }),
      h('div', { class: 'table-wrap' }, h('table', null,
        h('thead', null, h('tr', null, ['Path', 'Ownership', 'Adapter', 'Reason'].map((title) => h('th', { scope: 'col', text: title })))),
        h('tbody', null, items.map((item) => h('tr', { class: item.action === 'conflict' ? 'conflict' : undefined },
          h('td', { class: 'path', text: item.path }),
          h('td', { text: item.ownership || '' }),
          h('td', { text: item.adapter || '' }),
          h('td', { text: item.reason || '' })))))));
    wrap.append(details);
  }
  if ((data.diagnostics || []).length) {
    wrap.append(h('h3', { text: 'Plan diagnostics' }));
    wrap.append(diagnosticsView(data.diagnostics));
  }
  return wrap;
}

function cmdBlock(text) {
  return h('div', { class: 'cmd' },
    h('code', { text }),
    h('button', {
      type: 'button',
      class: 'btn secondary small',
      text: 'Copy',
      'aria-label': 'Copy command: ' + text,
      on: {
        click: async () => {
          try {
            await navigator.clipboard.writeText(text);
            setStatus('Copied to clipboard.', 'ok');
          } catch (error) {
            setStatus('Copy failed. Select the command and copy it manually.', 'error');
          }
        },
      },
    }));
}

function generatedView(done) {
  const wrap = h('div');
  const report = done.data;
  wrap.append(h('div', { class: 'callout ' + (report.outcome === 'pass' ? 'ok' : 'error') },
    h('strong', { text: report.outcome === 'pass' ? 'Workspace generated. ' : 'Generation finished with errors. ' }),
    h('code', { text: done.path })));
  if (isObj(report.summary)) {
    wrap.append(h('dl', { class: 'kv' }, Object.entries(report.summary).flatMap(([key, value]) => [
      h('dt', { text: key }),
      h('dd', { text: isObj(value) || Array.isArray(value) ? JSON.stringify(value) : String(value) }),
    ])));
  }
  if ((report.diagnostics || []).length) wrap.append(diagnosticsView(report.diagnostics));
  if (report.outcome === 'pass') {
    wrap.append(h('h3', { text: 'Next steps' }));
    wrap.append(h('ol', { class: 'next' },
      h('li', null, 'Check the generated workspace from the foundation checkout.', cmdBlock('python -m toolkit_cli validate --workspace "' + done.path + '"')),
      h('li', null, 'Register the generated extensions folder with pyRevit.', cmdBlock('pyrevit extensions paths add "' + done.path.replace(/[\\/]+$/, '') + '\\extensions"')),
      h('li', null, 'Run the live check in Revit using the runbook in the foundation checkout: ', h('code', { text: 'docs/verification/GENERATED_WORKSPACE.md' }), '.'),
      h('li', null, 'For native WPF rendering, run ', h('code', { text: 'specimens/wpf/show-specimen.ps1' }), ' in the generated workspace.')));
  }
  return wrap;
}

function renderGenerate(root) {
  append(root, pageHead('Generate', 'Choose where the workspace goes, review exactly what will be written, then generate. Plan is read-only.'));
  const pathField = textField({
    label: 'Workspace folder (absolute path)',
    help: 'A new or empty folder outside this repository, or an existing generated workspace to update.',
    value: app.workspacePath,
    mono: true,
    placeholder: 'C:\\Firm\\Workspace',
    onInput: (value) => { app.workspacePath = value; controls(); },
  });
  const planButton = h('button', { type: 'button', class: 'btn secondary', text: 'Plan', on: { click: () => doPlan() } });
  const generateButton = h('button', { type: 'button', class: 'btn', text: 'Generate', on: { click: () => doApply() } });
  const hint = h('p', { class: 'help' });
  root.append(pathField.root, h('p', null, planButton, ' ', generateButton), hint);
  const results = h('div');
  root.append(results);

  function canGenerate() {
    const path = app.workspacePath.trim();
    return Boolean(app.plan && app.plan.workspace === path && app.plan.version === app.version
      && app.dirty.size === 0 && app.plan.data.outcome === 'pass' && !app.busy);
  }

  function controls() {
    planButton.disabled = app.busy || !app.workspacePath.trim();
    generateButton.disabled = !canGenerate();
    if (app.busy) hint.textContent = 'Working...';
    else if (canGenerate()) hint.textContent = 'The plan passed for this path and draft. Generate will write these files.';
    else if (app.plan && app.plan.workspace === app.workspacePath.trim() && app.plan.data.outcome !== 'pass') hint.textContent = 'The plan has errors or conflicts. Fix them and plan again.';
    else hint.textContent = 'Generate unlocks after a passing plan for this path and the current draft.';
  }

  function paint() {
    clear(results);
    const path = app.workspacePath.trim();
    if (app.generated && app.generated.path === path) results.append(generatedView(app.generated));
    else if (app.plan && app.plan.workspace === path) {
      if (app.plan.version !== app.version) results.append(h('div', { class: 'callout warn', text: 'The draft changed after this plan. Plan again.' }));
      results.append(planView(app.plan));
    }
    controls();
  }

  async function doPlan() {
    const path = app.workspacePath.trim();
    app.busy = true;
    controls();
    setStatus('Planning...', 'info');
    try {
      const outcome = await enqueue(async () => {
        await saveInner();
        const version = app.version;
        return { version, data: await api('POST', '/api/plan', { workspace: path }) };
      });
      app.plan = { workspace: path, version: outcome.version, data: outcome.data };
      app.generated = null;
      setStatus('Plan ' + outcome.data.outcome + ': ' + (outcome.data.actions || []).length + ' actions.', outcome.data.outcome === 'pass' ? 'ok' : 'error');
    } catch (error) {
      app.plan = null;
      showError(error);
    } finally {
      app.busy = false;
      updateRail();
    }
    paint();
  }

  async function doApply() {
    const path = app.workspacePath.trim();
    app.busy = true;
    controls();
    setStatus('Generating...', 'info');
    try {
      const data = await enqueue(async () => {
        await saveInner();
        if (!app.plan || app.plan.workspace !== path || app.plan.version !== app.version) {
          throw new Error('The draft changed after the plan. Plan again.');
        }
        return api('POST', '/api/apply', { workspace: path });
      });
      app.generated = { path, data };
      app.plan = null;
      if (app.draft) app.draft.source = 'workspace';
      setStatus(data.outcome === 'pass' ? 'Workspace generated.' : 'Generation finished with errors.', data.outcome === 'pass' ? 'ok' : 'error');
    } catch (error) {
      showError(error);
    } finally {
      app.busy = false;
      updateRail();
    }
    paint();
  }

  paint();
  navRow(root);
}

/* ---- shell ----------------------------------------------------------------- */

const RENDERERS = {
  start: renderStart,
  identity: renderIdentity,
  technical: renderTechnical,
  logos: renderLogos,
  colour: renderColour,
  components: renderComponents,
  preview: renderPreview,
  generate: renderGenerate,
};

function renderStep() {
  const main = $('main');
  clear(main);
  view = { updaters: [], onValidated: null };
  if (!modelsReady() && app.step !== 'start') app.step = 'start';
  RENDERERS[app.step](main);
  updateRail();
}

function goTo(id) {
  app.step = id;
  setStatus('', 'info');
  renderStep();
  const title = $('step-title');
  if (title) title.focus();
  window.scrollTo(0, 0);
}

function buildRail() {
  const list = $('steps');
  STEPS.forEach((step, index) => {
    list.append(h('li', null, h('button', {
      type: 'button',
      class: 'step-btn',
      'data-step': step.id,
      on: { click: () => goTo(step.id) },
    }, h('span', { class: 'step-num', text: String(index + 1).padStart(2, '0') }), h('span', { text: step.title }))));
  });
  $('shutdown').addEventListener('click', shutdown);
}

async function shutdown() {
  if (!window.confirm('Shut down the wizard? The draft exists only in this session; anything not yet generated is discarded.')) return;
  try {
    await enqueue(() => api('POST', '/api/shutdown', {}));
  } catch (error) {
    showError(error);
    return;
  }
  app.stopped = true;
  clear($('main'));
  $('main').append(h('h2', { text: 'Wizard stopped' }), h('p', { class: 'lede', text: 'The server has shut down. You can close this tab. Run `python -m toolkit_cli serve` to start again.' }));
  $('shutdown').disabled = true;
  setStatus('Wizard stopped.', 'info');
  updateRail();
}

function showNoToken() {
  const main = $('main');
  clear(main);
  main.append(
    h('h2', { text: 'No session token' }),
    h('p', { class: 'lede' }, 'Open the link printed by ', h('code', { text: 'python -m toolkit_cli serve' }), '. It carries a one-time token in the address fragment.'));
  setStatus('Open the link printed by `python -m toolkit_cli serve`.', 'error');
  $('shutdown').disabled = true;
  updateRail();
}

async function boot() {
  buildRail();
  app.token = readToken();
  if (!app.token) {
    showNoToken();
    return;
  }
  try {
    await api('POST', '/api/session', {});
    const listing = await api('GET', '/api/starters');
    app.starters = listing.starters || [];
    /* A fresh session answers with source null instead of an error. */
    const state = await api('GET', '/api/state');
    if (state.source) {
      loadDraft(state);
      setStatus('Resumed the draft already open in this session (' + state.source + ').', 'info');
      runValidate().catch(showError);
    }
  } catch (error) {
    showError(error);
  }
  renderStep();
}

boot();
