import { useLayoutEffect, useState, useCallback } from 'react'

/** Resolve PageButton → destination page index (or null / invalid). */
export function resolvePageLinkTarget(widget, pageIdx, pageCount) {
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

function edgePoint(slotRect, fromX, fromY) {
  const cx = slotRect.left + slotRect.width / 2
  const cy = slotRect.top + slotRect.height / 2
  const dx = cx - fromX
  const dy = cy - fromY
  if (Math.abs(dx) >= Math.abs(dy)) {
    // Approach from left or right
    if (dx >= 0) {
      return { x: slotRect.left, y: cy, dir: 'left' }
    }
    return { x: slotRect.right, y: cy, dir: 'right' }
  }
  if (dy >= 0) {
    return { x: cx, y: slotRect.top, dir: 'top' }
  }
  return { x: cx, y: slotRect.bottom, dir: 'bottom' }
}

function arrowHead(x, y, dir, size = 7) {
  // Arrow tip at (x,y), pointing into the slot
  if (dir === 'left') {
    return `M${x},${y} L${x - size},${y - size * 0.6} L${x - size},${y + size * 0.6} Z`
  }
  if (dir === 'right') {
    return `M${x},${y} L${x + size},${y - size * 0.6} L${x + size},${y + size * 0.6} Z`
  }
  if (dir === 'top') {
    return `M${x},${y} L${x - size * 0.6},${y - size} L${x + size * 0.6},${y - size} Z`
  }
  return `M${x},${y} L${x - size * 0.6},${y + size} L${x + size * 0.6},${y + size} Z`
}

function curvePath(x1, y1, x2, y2) {
  const mx = (x1 + x2) / 2
  const my = (y1 + y2) / 2
  const dx = x2 - x1
  const dy = y2 - y1
  // Offset control point perpendicular-ish for a soft arc
  const cx = mx + dy * 0.12
  const cy = my - dx * 0.08
  return `M${x1},${y1} Q${cx},${cy} ${x2},${y2}`
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

    const slotEls = [...root.querySelectorAll('[data-page-slot]')]
    const slotMap = new Map()
    slotEls.forEach((el) => {
      const idx = Number(el.getAttribute('data-page-slot'))
      const r = el.getBoundingClientRect()
      slotMap.set(idx, {
        left: (r.left - rootRect.left) / inv + root.scrollLeft,
        top: (r.top - rootRect.top) / inv + root.scrollTop,
        right: (r.right - rootRect.left) / inv + root.scrollLeft,
        bottom: (r.bottom - rootRect.top) / inv + root.scrollTop,
        width: r.width / inv,
        height: r.height / inv,
      })
    })

    const pageCount = pages.length
    const next = []

    pages.forEach((pageWidgets, pageIdx) => {
      ;(pageWidgets || []).forEach((w) => {
        if (w.type !== 'PageButton') return
        const resolved = resolvePageLinkTarget(w, pageIdx, pageCount)
        if (!resolved) return

        const btn = root.querySelector(
          `[data-page-link="1"][data-widget-id="${w.id}"][data-page-idx="${pageIdx}"]`
        )
        if (!btn) return
        const br = btn.getBoundingClientRect()
        const x1 = (br.left + br.width / 2 - rootRect.left) / inv + root.scrollLeft
        const y1 = (br.top + br.height / 2 - rootRect.top) / inv + root.scrollTop

        const selected = selectedIds.includes(w.id)
        const emphasized =
          selected ||
          pageIdx === currentPage ||
          (!resolved.invalid && resolved.target === currentPage)

        if (resolved.invalid) {
          // Short stub pointing right as error marker
          const x2 = x1 + 28
          const y2 = y1
          next.push({
            id: `${pageIdx}-${w.id}`,
            d: `M${x1},${y1} L${x2},${y2}`,
            arrow: arrowHead(x2, y2, 'right'),
            invalid: true,
            emphasized,
          })
          return
        }

        const localSlot = slotMap.get(resolved.target)
        if (!localSlot) return

        const end = edgePoint(localSlot, x1, y1)
        next.push({
          id: `${pageIdx}-${w.id}`,
          d: curvePath(x1, y1, end.x, end.y),
          arrow: arrowHead(end.x, end.y, end.dir),
          invalid: false,
          emphasized,
        })
      })
    })

    setPaths(next)
  }, [containerRef, pages, selectedIds, currentPage, zoom])

  useLayoutEffect(() => {
    measure()
    const root = containerRef.current
    if (!root) return undefined

    const ro = new ResizeObserver(() => measure())
    ro.observe(root)
    root.querySelectorAll('[data-page-slot]').forEach((el) => ro.observe(el))

    window.addEventListener('resize', measure)
    // Re-measure after layout settles (fonts / canvas size)
    const t = requestAnimationFrame(measure)

    return () => {
      ro.disconnect()
      window.removeEventListener('resize', measure)
      cancelAnimationFrame(t)
    }
  }, [measure, revision, pages, selectedIds, currentPage])

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
          <path d={p.d} fill="none" className="page-link-path" />
          <path d={p.arrow} className="page-link-arrow" />
        </g>
      ))}
    </svg>
  )
}
