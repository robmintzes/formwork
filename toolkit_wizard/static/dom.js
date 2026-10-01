/* Tiny DOM builder. Text always goes through textContent or text nodes,
   never innerHTML, so server- or user-provided strings cannot inject markup. */

export function h(tag, props, ...children) {
  const el = document.createElement(tag);
  if (props) {
    for (const [key, value] of Object.entries(props)) {
      if (value === undefined || value === null || value === false) continue;
      if (key === 'class') el.className = value;
      else if (key === 'text') el.textContent = value;
      else if (key === 'on') {
        for (const [name, handler] of Object.entries(value)) el.addEventListener(name, handler);
      } else if (key === 'value') el.value = value;
      else if (key === 'checked') el.checked = Boolean(value);
      else if (key === 'disabled') el.disabled = Boolean(value);
      else if (value === true) el.setAttribute(key, '');
      else el.setAttribute(key, String(value));
    }
  }
  append(el, children);
  return el;
}

export function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === undefined || child === null || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function clear(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
  return el;
}
