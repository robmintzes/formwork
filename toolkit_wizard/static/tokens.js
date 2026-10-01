/* Token document helpers: alias resolution, color maths, role tables, edits.
   The server remains the authority; this mirrors toolkit_engine/tokens.py closely
   enough to show live values and WCAG contrast while a draft is being edited. */

const has = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

const STATUS = ['info', 'success', 'warning', 'danger'];

export const COLOR_GROUPS = [
  { title: 'Surface', roles: ['surface.default', 'surface.card', 'surface.sunken', 'surface.inverse'] },
  { title: 'Text', roles: ['text.primary', 'text.secondary', 'text.inverse'] },
  { title: 'Line', roles: ['line.subtle', 'line.strong'] },
  { title: 'Accent', roles: ['accent.default', 'accent.strong', 'accent.soft'] },
  { title: 'Primary action', roles: ['action.primary.bg', 'action.primary.fg'] },
  { title: 'Secondary action', roles: ['action.secondary.bg', 'action.secondary.fg', 'action.secondary.border'] },
  { title: 'Focus', roles: ['focus.ring'] },
  ...STATUS.map((name) => ({ title: 'Status: ' + name, roles: ['status.' + name + '.fg', 'status.' + name + '.bg'] })),
].map((group) => ({ title: group.title, roles: group.roles.map((role) => 'color.' + role) }));

export const COLOR_ROLES = COLOR_GROUPS.flatMap((group) => group.roles);

export const FONT_STACKS = ['display', 'body', 'label', 'code'];
export const FONT_WEIGHTS = ['display', 'body', 'strong', 'label'];
export const FONT_SIZES = ['display', 'title', 'body', 'small', 'label', 'code'];

/* Contrast pairs from FOUNDATION_SPEC 3.4. */
export const CONTRAST_PAIRS = [
  { fg: 'color.text.primary', bg: 'color.surface.default', min: 4.5 },
  { fg: 'color.text.primary', bg: 'color.surface.card', min: 4.5 },
  { fg: 'color.text.secondary', bg: 'color.surface.default', min: 4.5 },
  { fg: 'color.text.secondary', bg: 'color.surface.card', min: 4.5 },
  { fg: 'color.text.inverse', bg: 'color.surface.inverse', min: 4.5 },
  { fg: 'color.action.primary.fg', bg: 'color.action.primary.bg', min: 4.5 },
  { fg: 'color.action.secondary.fg', bg: 'color.action.secondary.bg', min: 4.5 },
  ...STATUS.map((name) => ({ fg: 'color.status.' + name + '.fg', bg: 'color.status.' + name + '.bg', min: 4.5 })),
  { fg: 'color.focus.ring', bg: 'color.surface.default', min: 3 },
];

export function parseAlias(value) {
  if (typeof value !== 'string') return null;
  const match = /^\{([^{}]+)\}$/.exec(value);
  return match ? match[1] : null;
}

/* Find the token at a dotted path. Returns {node, type} (type inherited from groups) or null. */
export function getToken(doc, path) {
  let node = doc;
  let type = null;
  for (const part of path.split('.')) {
    if (!isObject(node) || !has(node, part)) return null;
    if (typeof node.$type === 'string') type = node.$type;
    node = node[part];
  }
  if (!isObject(node) || !has(node, '$value')) return null;
  if (typeof node.$type === 'string') type = node.$type;
  return { node, type };
}

/* Follow aliases. Returns {ok, value, type, chain} or {ok:false, error, chain}.
   chain lists every alias target followed, in order. */
export function resolve(doc, path) {
  const chain = [];
  const seen = new Set();
  let current = path;
  for (;;) {
    if (seen.has(current)) {
      return { ok: false, error: 'Alias cycle: ' + [path, ...chain].join(' -> '), chain };
    }
    seen.add(current);
    const found = getToken(doc, current);
    if (!found) return { ok: false, error: 'No token named ' + current + '.', chain };
    const alias = parseAlias(found.node.$value);
    if (alias === null) return { ok: true, value: found.node.$value, type: found.type, chain, source: current };
    chain.push(alias);
    current = alias;
  }
}

/* ---- color ---------------------------------------------------------------- */

export function normalizeHex(text) {
  let value = String(text).trim();
  if (!value.startsWith('#')) value = '#' + value;
  if (/^#[0-9a-fA-F]{3}$/.test(value)) {
    value = '#' + value.slice(1).split('').map((c) => c + c).join('');
  }
  return /^#[0-9a-fA-F]{6}$/.test(value) ? value.toUpperCase() : null;
}

function hexFromComponents(components) {
  return '#' + components
    .map((c) => Math.max(0, Math.min(255, Math.round(c * 255))).toString(16).padStart(2, '0'))
    .join('')
    .toUpperCase();
}

/* A DTCG color object -> {hex, alpha} or null. Mirrors the server: a valid hex wins. */
export function colorFromValue(value) {
  if (!isObject(value) || value.colorSpace !== 'srgb') return null;
  const alpha = typeof value.alpha === 'number' ? value.alpha : 1;
  if (typeof value.hex === 'string') {
    const hex = normalizeHex(value.hex);
    if (hex) return { hex, alpha };
  }
  const c = value.components;
  if (Array.isArray(c) && c.length === 3 && c.every((n) => typeof n === 'number' && n >= 0 && n <= 1)) {
    return { hex: hexFromComponents(c), alpha };
  }
  return null;
}

/* Resolve a color token. Returns {hex, alpha, chain} or {error, chain}. */
export function resolveColor(doc, path) {
  const result = resolve(doc, path);
  if (!result.ok) return { error: result.error, chain: result.chain };
  if (result.type !== 'color') return { error: path + ' is ' + (result.type || 'untyped') + ', not a color.', chain: result.chain };
  const color = colorFromValue(result.value);
  if (!color) return { error: 'Not a valid sRGB color value.', chain: result.chain };
  return { hex: color.hex, alpha: color.alpha, chain: result.chain, source: result.source };
}

export function rgbOf(hex) {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
}

function luminance(hex) {
  const [r, g, b] = rgbOf(hex).map((v) => {
    const c = v / 255;
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(hexA, hexB) {
  const a = luminance(hexA);
  const b = luminance(hexB);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

/* A literal DTCG color object. components rounded to 4 decimals, uppercase hex. */
export function literalColor(hex, previous) {
  const clean = normalizeHex(hex);
  const value = {
    colorSpace: 'srgb',
    components: rgbOf(clean).map((v) => Math.round((v / 255) * 10000) / 10000),
    hex: clean,
  };
  if (isObject(previous) && typeof previous.alpha === 'number') value.alpha = previous.alpha;
  return value;
}

/* Replace a color token's value with a literal color. Other token fields ($extensions, ...) stay. */
export function setColor(doc, path, hex) {
  const found = getToken(doc, path);
  if (!found) return false;
  found.node.$value = literalColor(hex, found.node.$value);
  return true;
}

/* ---- palette --------------------------------------------------------------- */

/* Every color token under `palette`, as [{path, group}] in document order. */
export function paletteTokens(doc) {
  const out = [];
  const root = isObject(doc) && isObject(doc.palette) ? doc.palette : null;
  if (!root) return out;
  const walk = (node, parts) => {
    for (const [key, child] of Object.entries(node)) {
      if (key.startsWith('$') || !isObject(child)) continue;
      const next = [...parts, key];
      if (has(child, '$value')) {
        const path = 'palette.' + next.join('.');
        const found = getToken(doc, path);
        if (found && found.type === 'color') out.push({ path, group: parts.join('.') || 'palette' });
      } else {
        walk(child, next);
      }
    }
  };
  walk(root, []);
  return out;
}

/* Number of required color roles whose alias chain passes through each palette token. */
export function paletteUsage(doc, palette) {
  const usage = {};
  for (const item of palette) usage[item.path] = 0;
  for (const role of COLOR_ROLES) {
    const result = resolve(doc, role);
    for (const target of result.chain) if (has(usage, target)) usage[target] += 1;
  }
  return usage;
}

/* ---- typography ------------------------------------------------------------ */

export function parseStack(text) {
  return String(text)
    .split(',')
    .map((part) => part.trim().replace(/^(["'])(.*)\1$/, '$2').trim())
    .filter((part) => part.length > 0);
}

export function stackText(value) {
  return Array.isArray(value) ? value.join(', ') : typeof value === 'string' ? value : '';
}

export function setFontStack(doc, role, list) {
  const found = getToken(doc, 'font.' + role);
  if (!found) return false;
  found.node.$value = list.slice();
  return true;
}

export function setFontWeight(doc, role, text) {
  const found = getToken(doc, 'font-weight.' + role);
  if (!found) return false;
  const trimmed = String(text).trim();
  found.node.$value = /^\d+$/.test(trimmed) ? Number(trimmed) : trimmed;
  return true;
}

export function setFontSize(doc, role, px) {
  const found = getToken(doc, 'font-size.' + role);
  if (!found) return false;
  if (isObject(found.node.$value) && !parseAlias(found.node.$value)) found.node.$value.value = px;
  else found.node.$value = { value: px, unit: 'px' };
  return true;
}

export function dimensionPx(value) {
  return isObject(value) && typeof value.value === 'number' ? value.value : null;
}
