import { useLayoutEffect, useState, useCallback } from 'react'

/** Resolve PageButton → destination page index (or null / invalid). */
function resolvePageLinkTarget(widget, pageIdx, pageCount) {
  const mode = widget.nav_mode || 'goto'
  if (mode === 'prev') {
    return pageIdx > 0 ? { target: pageIdx - 1, invalid: false } : null
  }
  if (mode === 'next') {
    return pageIdx < pageCount - 1 ? { target: pageIdx + 1, invalid: false } : null
  }
  const t = widget.target_page ?? 0
  if (t < 0 || t >= pageCount) return { target: t, invalid: true }
  if (t === pageIdx) return null // self-link: skip
  return { target: t, invalid: false }
}

/** Enter target page-slot from the near side, keeping source Y when possible. */
function sideEntry(slotRect, fromX, fromY) {
  const pad = 10
  const y = Math.max(slotRect.top + pad, Math.min(slotRect.bottom - pad, fromY))
  const midX = slotRect.left + slotRect.width / 2
  if (fromX < midX) {
    return { x: slotRect.left, y, dir: 'left' }
  }
  return { x: slotRect.right, y, dir: 'right' }
}

/** Leave the button from the edge facing the destination. */
function startExit(btn, towardX, towardY) {
  const cx = btn.left + btn.width / 2
  const cy = btn.top + btn.height / 2
  const dx = towardX - cx
  const dy = towardY - cy
  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx >= 0
      ? { x: btn.right, y: cy }
      : { x: btn.left, y: cy }
  }
  return dy >= 0
    ? { x: cx, y: btn.bottom }
    : { x: cx, y: btn.top }
}

function arrowHead(x, y, dir, size = 8) {
  if (dir === 'left') {
    return `M${x},${y} L${x - size},${y - size * 0.55} L${x - size},${y + size * 0.55} Z`
  }
  if (dir === 'right') {
    return `M${x},${y} L${x + size},${y - size * 0.55} L${x + size},${y + size * 0.55} Z`
  }
  if (dir === 'top') {
    return `M${x},${y} L${x - size * 0.55},${y - size} L${x + size * 0.55},${y - size} Z`
  }
  return `M${x},${y} L${x - size * 0.55},${y + size} L${x + size * 0.55},${y + size} Z`
}

/**
 * Horizontal-first cubic; lane spreads parallel / opposing links so they don't stack.
 * lane: … -2,-1,1,2 … (skip 0 so a pair splits above/below)
 */
function routePath(x1, y1, x2, y2, lane = 1) {
  const dx = x2 - x1
  const dy = y2 - y1
  const lanePx = lane * 16

  if (Math.abs(dx) >= Math.abs(dy) * 0.55) {
    // Sideways: S-curve through the gap between pages
    const mx = (x1 + x2) / 2
    return `M${x1},${y1} C${mx},${y1 + lanePx} ${mx},${y2 + lanePx} ${x2},${y2}`
  }
  // Mostly vertical: bow sideways
  const my = (y1 + y2) / 2
  return `M${x1},${y1} C${x1 + lanePx},${my} ${x2 + lanePx},${my} ${x2},${y2}`
}

/** Alternate +1,-1,+2,-2… so mutual links (next/prev) sit on opposite sides. */
function laneForIndex(i) {
  const n = Math.floor(i / 2) + 1
  return i % 2 === 0 ? n : -n
}

/**
 * SVG overlay: PageButton → destination page-slot curves.
 * Must be a child of `.pages-row` (position: relative).
 * `zoom` compensates for CSS transform:scale on an ancestor.
 */
export default function PageLinksOverlay({
  containerRef,
  pages,
  selectedIds,
  currentPage,
  zoom = 1,
  revision = 0,
}) {
  const [paths, setPaths] = useState([])
  const [size, setSize] = useState({ w: 0, h: 0 })

  const measure = useCallback(() => {
    const root = containerRef.current
    if (!root) return

    const inv = zoom > 0 ? zoom : 1
    const rootRect = root.getBoundingClientRect()
    setSize({ w: root.scrollWidth, h: root.scrollHeight })

    const toLocal = (clientX, clientY) => ({
      x: (clientX - rootRect.left) / inv + root.scrollLeft,
      y: (clientY - rootRect.top) / inv + root.scrollTop,
    })

    const slotEls = [...root.querySelectorAll('[data-page-slot]')]
    const slotMap = new Map()
    slotEls.forEach((el) => {
      const idx = Number(el.getAttribute('data-page-slot'))
      const r = el.getBoundingClientRect()
      const tl = toLocal(r.left, r.top)
      const br = toLocal(r.right, r.bottom)
      slotMap.set(idx, {
        left: tl.x,
        top: tl.y,
        right: br.x,
        bottom: br.y,
        width: br.x - tl.x,
        height: br.y - tl.y,
      })
    })

    const pageCount = pages.length
    const drafts = []
    const pairIndex = new Map()

    pages.forEach((pageWidgets, pageIdx) => {
      ;(pageWidgets || []).forEach((w) => {
        if (w.type !== 'PageButton') return
        const resolved = resolvePageLinkTarget(w, pageIdx, pageCount)
        if (!resolved) return

        const btnEl = root.querySelector(
          `[data-page-link="1"][data-widget-id="${w.id}"][data-page-idx="${pageIdx}"]`
        )
        if (!btnEl) return
        const br = btnEl.getBoundingClientRect()
        const tl = toLocal(br.left, br.top)
        const brLocal = toLocal(br.right, br.bottom)
        const btn = {
          left: tl.x,
          top: tl.y,
          right: brLocal.x,
          bottom: brLocal.y,
          width: brLocal.x - tl.x,
          height: brLocal.y - tl.y,
        }

        const selected = selectedIds.includes(w.id)
        const emphasized =
          selected ||
          pageIdx === currentPage ||
          (!resolved.invalid && resolved.target === currentPage)

        if (resolved.invalid) {
          const start = startExit(btn, btn.right + 40, btn.top + btn.height / 2)
          const x2 = start.x + 28
          const y2 = start.y
          drafts.push({
            id: `${pageIdx}-${w.id}`,
            d: `M${start.x},${start.y} L${x2},${y2}`,
            arrow: arrowHead(x2, y2, 'right'),
            invalid: true,
            emphasized,
          })
          return
        }

        const localSlot = slotMap.get(resolved.target)
        if (!localSlot) return

        // Provisional end for exit direction; refine after start known
        const endGuess = sideEntry(
          localSlot,
          btn.left + btn.width / 2,
          btn.top + btn.height / 2,
        )
        const start = startExit(btn, endGuess.x, endGuess.y)
        const end = sideEntry(localSlot, start.x, start.y)

        const a = Math.min(pageIdx, resolved.target)
        const b = Math.max(pageIdx, resolved.target)
        const pairKey = `${a}-${b}`
        const i = pairIndex.get(pairKey) || 0
        pairIndex.set(pairKey, i + 1)

        drafts.push({
          id: `${pageIdx}-${w.id}`,
          d: routePath(start.x, start.y, end.x, end.y, laneForIndex(i)),
          arrow: arrowHead(end.x, end.y, end.dir),
          invalid: false,
          emphasized,
        })
      })
    })

    setPaths(drafts)
  }, [containerRef, pages, selectedIds, currentPage, zoom])

  useLayoutEffect(() => {
    measure()
    const root = containerRef.current
    if (!root) return undefined

    const ro = new ResizeObserver(() => measure())
    ro.observe(root)
    root.querySelectorAll('[data-page-slot]').forEach((el) => ro.observe(el))

    window.addEventListener('resize', measure)
    const t = requestAnimationFrame(measure)

    return () => {
      ro.disconnect()
      window.removeEventListener('resize', measure)
      cancelAnimationFrame(t)
    }
  }, [measure, containerRef, revision, pages, selectedIds, currentPage])

  if (size.w === 0 || paths.length === 0) return null

  return (
    <svg
      className="page-links-overlay"
      width={size.w}
      height={size.h}
      aria-hidden="true"
    >
      {paths.map((p) => (
        <g
          key={p.id}
          className={`page-link ${p.invalid ? 'invalid' : ''} ${p.emphasized ? 'emphasized' : ''}`}
        >
          <path d={p.d} fill="none" className="page-link-path page-link-path-halo" />
          <path d={p.d} fill="none" className="page-link-path" />
          <path d={p.arrow} className="page-link-arrow" />
        </g>
      ))}
    </svg>
  )
}
