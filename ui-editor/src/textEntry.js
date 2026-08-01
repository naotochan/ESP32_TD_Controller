/** True when the element takes text input — global shortcuts must leave it alone. */
export function isTextEntry(el) {
  if (!el) return false
  return el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable === true
}
