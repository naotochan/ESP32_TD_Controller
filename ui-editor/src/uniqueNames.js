const LABEL_PREFIX = {
  Button: 'BTN ',
  Toggle: 'TOG ',
  Slider: 'SLIDER ',
  HSlider: 'HSLIDER ',
  PageButton: 'PAGE ',
}

const OSC_PREFIX = {
  Button: '/esp32/button/',
  Toggle: '/esp32/toggle/',
  Slider: '/esp32/slider/',
  HSlider: '/esp32/hslider/',
}

function flattenWidgets(pages) {
  return (pages || []).flatMap((p) => p || [])
}

/** Collect used labels / OSC addresses across all pages (optionally exclude one widget). */
export function collectUsedNames(pages, excludeId = null) {
  const labels = new Set()
  const oscAddrs = new Set()
  for (const w of flattenWidgets(pages)) {
    if (excludeId != null && w.id === excludeId) continue
    const label = (w.label || '').trim()
    if (label) labels.add(label)
    const addr = (w.osc_addr || '').trim()
    if (addr) oscAddrs.add(addr)
  }
  return { labels, oscAddrs }
}

function nextFreeNumbered(reserved, prefix) {
  let n = 1
  while (reserved.has(prefix + n)) n += 1
  return prefix + n
}

/** Next unique default label for a widget type (global across pages). */
export function nextUniqueLabel(pages, type, reservedExtra = null) {
  const reserved = reservedExtra
    ? new Set([...collectUsedNames(pages).labels, ...reservedExtra])
    : collectUsedNames(pages).labels
  const prefix = LABEL_PREFIX[type] || `${type} `
  return nextFreeNumbered(reserved, prefix)
}

/** Next unique OSC address for a widget type (global across pages). Empty for PageButton. */
export function nextUniqueOscAddr(pages, type, reservedExtra = null) {
  const prefix = OSC_PREFIX[type]
  if (!prefix) return ''
  const reserved = reservedExtra
    ? new Set([...collectUsedNames(pages).oscAddrs, ...reservedExtra])
    : collectUsedNames(pages).oscAddrs
  return nextFreeNumbered(reserved, prefix)
}

/** Ensure pasted/cloned widgets get unique labels and OSC addresses across all pages. */
export function uniquifyWidgets(pages, widgets) {
  const { labels, oscAddrs } = collectUsedNames(pages)
  return widgets.map((w) => {
    let label = (w.label || '').trim()
    if (!label || labels.has(label)) {
      label = nextUniqueLabel(pages, w.type, labels)
    }
    labels.add(label)

    let osc_addr = (w.osc_addr || '').trim()
    if (OSC_PREFIX[w.type]) {
      if (!osc_addr || oscAddrs.has(osc_addr)) {
        osc_addr = nextUniqueOscAddr(pages, w.type, oscAddrs)
      }
      oscAddrs.add(osc_addr)
      return { ...w, label, osc_addr }
    }
    return { ...w, label }
  })
}
