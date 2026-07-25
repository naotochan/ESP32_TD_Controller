import { useState, useCallback, useRef } from 'react'

/** Default editor pixels per device pixel (fixed page footprint; view zoom is CSS). */
export const BASE_SCALE = 2
/** Matches firmware STATUS_H — reserved for IP + version footer. */
export const STATUS_BAR_H = 14

const WIDGET_TEMPLATES = {
  Button:     { w: 105, h: 80 },
  Toggle:     { w: 105, h: 80 },
  Slider:     { w: 30,  h: 140 },
  HSlider:    { w: 140, h: 30 },
  PageButton: { w: 60,  h: 30 },
}

/** Map client coords → device pixels (works with CSS zoom transforms on ancestors). */
function clientToDevice(clientX, clientY, rect, screenW, screenH) {
  if (!rect || rect.width <= 0 || rect.height <= 0) return { x: 0, y: 0 }
  return {
    x: ((clientX - rect.left) / rect.width) * screenW,
    y: ((clientY - rect.top) / rect.height) * screenH,
  }
}

export default function Canvas({
  widgets, selectedIds, onSelect, onSelectMany,
  onUpdate, onUpdateMany, onAddWidget, onCommitDrag, onGetSnapshot,
  screenW, screenH, showGrid, snapToGrid = true,
  rotationDeg = 0, appVersion = '0.5.1', showPortLabels = true,
  pageIdx = 0, scale = BASE_SCALE,
}) {
  const usableH = screenH - STATUS_BAR_H

  /**
   * Physical USB edge relative to screen content.
   * Degrees are counter-clockwise (左回転) from 0°.
   * 0° portrait: USB=bottom (cable down). 90° CCW landscape: USB=right.
   */
  const portEdges = (() => {
    const deg = ((rotationDeg % 360) + 360) % 360
    const map = {
      0:   { usb: 'bottom' },
      90:  { usb: 'right' },
      180: { usb: 'top' },
      270: { usb: 'left' },
    }
    return map[deg] || map[0]
  })()

  const containerRef = useRef(null)
  const canvasRef = useRef(null)
  const dragState = useRef(null)
  const dragSnapshotRef = useRef(null)
  const rubberBandRef = useRef(null)
  const [rubberBandRect, setRubberBandRect] = useState(null)

  // Stable refs so handlers with [] deps can access latest values
  const widgetsRef = useRef(widgets)
  widgetsRef.current = widgets
  const selectedIdsRef = useRef(selectedIds)
  selectedIdsRef.current = selectedIds
  const onSelectManyRef = useRef(onSelectMany)
  onSelectManyRef.current = onSelectMany
  const onUpdateManyRef = useRef(onUpdateMany)
  onUpdateManyRef.current = onUpdateMany
  const onCommitDragRef = useRef(onCommitDrag)
  onCommitDragRef.current = onCommitDrag
  const onGetSnapshotRef = useRef(onGetSnapshot)
  onGetSnapshotRef.current = onGetSnapshot

  // --- Drag-and-drop from WidgetPanel ---
  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    const widgetType = e.dataTransfer.getData('widgetType')
    if (!widgetType || !WIDGET_TEMPLATES[widgetType]) return
    const rect = canvasRef.current.getBoundingClientRect()
    const { x: cx, y: cy } = clientToDevice(e.clientX, e.clientY, rect, screenW, screenH)
    const x = Math.round((cx - WIDGET_TEMPLATES[widgetType].w / 2) / 5) * 5
    const y = Math.round((cy - WIDGET_TEMPLATES[widgetType].h / 2) / 5) * 5
    onAddWidget(widgetType, x, y)
  }, [onAddWidget, screenW, screenH])

  // --- Widget pointer: start move or resize drag ---
  const handlePointerDown = useCallback((e, widgetId, mode) => {
    e.stopPropagation()
    e.preventDefault()
    const rect = canvasRef.current.getBoundingClientRect()
    const { x: pointerX, y: pointerY } = clientToDevice(e.clientX, e.clientY, rect, screenW, screenH)
    const additive = e.metaKey || e.ctrlKey

    dragSnapshotRef.current = onGetSnapshotRef.current()

    if (mode === 'move') {
      // Group drag: if the dragged widget is part of the selection, move all selected
      const isGrouped = selectedIdsRef.current.includes(widgetId)
      const dragIds = isGrouped ? [...selectedIdsRef.current] : [widgetId]
      const origPositions = {}
      dragIds.forEach(id => {
        const w = widgetsRef.current.find(w => w.id === id)
        if (w) origPositions[id] = { x: w.x, y: w.y }
      })
      dragState.current = { mode: 'move', ids: dragIds, startX: pointerX, startY: pointerY, origPositions }
    } else if (mode.startsWith('resize-')) {
      const w = widgetsRef.current.find(w => w.id === widgetId)
      dragState.current = { mode: 'resize', ids: [widgetId], startX: pointerX, startY: pointerY, origW: w.w, origH: w.h, origX: w.x, origY: w.y, corner: mode.slice('resize-'.length) }
    }

    onSelect(widgetId, additive)
  }, [onSelect, screenW, screenH])

  // --- Canvas background: just deselect (rubber band handled by container) ---
  const onCanvasPointerDown = useCallback((e) => {
    if (e.metaKey || e.ctrlKey) return
    onSelect(null)
    // event bubbles up to container which starts the rubber band
  }, [onSelect])

  // --- Container pointer: start rubber band (works from inside and outside canvas) ---
  const onContainerPointerDown = useCallback((e) => {
    if (e.metaKey || e.ctrlKey) return
    const rect = canvasRef.current.getBoundingClientRect()
    // Clamp start point to canvas coordinate space (can start from outside edge)
    const { x: rawX, y: rawY } = clientToDevice(e.clientX, e.clientY, rect, screenW, screenH)
    const x = Math.max(0, Math.min(screenW, rawX))
    const y = Math.max(0, Math.min(screenH, rawY))
    rubberBandRef.current = { startX: x, startY: y, currentX: x, currentY: y }
    setRubberBandRect({ x, y, w: 0, h: 0 })
  }, [screenW, screenH])

  // --- Stable global handlers (no/minimal deps, read latest via refs) ---
  const handlePointerMove = useCallback((e) => {
    e.preventDefault()
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return

    if (dragState.current) {
      const state = dragState.current
      const { x: pointerX, y: pointerY } = clientToDevice(e.clientX, e.clientY, rect, screenW, screenH)
      const dx = Math.round(pointerX - state.startX)
      const dy = Math.round(pointerY - state.startY)

      if (state.mode === 'move') {
        const firstId = state.ids[0]
        const firstOrig = state.origPositions[firstId]
        const firstW = widgetsRef.current.find(w => w.id === firstId)
        const clampW = firstW ? firstW.w : 10
        const clampH = firstW ? firstW.h : 10

        let nx, ny
        if (snapToGrid) {
          nx = Math.max(0, Math.min(screenW - clampW, Math.round((firstOrig.x + dx) / 5) * 5))
          ny = Math.max(0, Math.min(usableH - clampH, Math.round((firstOrig.y + dy) / 5) * 5))
        } else {
          nx = Math.max(0, Math.min(screenW - clampW, firstOrig.x + dx))
          ny = Math.max(0, Math.min(usableH - clampH, firstOrig.y + dy))
        }
        const snapDx = nx - firstOrig.x
        const snapDy = ny - firstOrig.y

        if (state.ids.length === 1) {
          onUpdate(firstId, { x: nx, y: ny })
        } else {
          const updates = {}
          state.ids.forEach(id => {
            const orig = state.origPositions[id]
            const ww = widgetsRef.current.find(w => w.id === id)
            if (orig && ww) updates[id] = {
              x: Math.max(0, Math.min(screenW - ww.w, orig.x + snapDx)),
              y: Math.max(0, Math.min(usableH - ww.h, orig.y + snapDy)),
            }
          })
          onUpdateManyRef.current(prev =>
            prev.map(w => w.id in updates ? { ...w, ...updates[w.id] } : w)
          )
        }
      } else if (state.mode === 'resize') {
        const w = widgetsRef.current.find(w => w.id === state.ids[0])
        const corner = state.corner || 'br'

        let newX = state.origX
        let newY = state.origY
        let newW = state.origW
        let newH = state.origH

        if (corner.includes('r')) {
          newW = Math.max(10, state.origW + dx)
        } else if (corner.includes('l')) {
          newX = state.origX + dx
          newW = state.origW - dx
          if (newW < 10) { newX = state.origX + state.origW - 10; newW = 10 }
        }

        if (corner.includes('b')) {
          newH = Math.max(10, state.origH + dy)
        } else if (corner.includes('t')) {
          newY = state.origY + dy
          newH = state.origH - dy
          if (newH < 10) { newY = state.origY + state.origH - 10; newH = 10 }
        }

        // Clamp edges to screen bounds, then derive dimensions
        let leftEdge = newX
        let rightEdge = newX + newW
        let topEdge = newY
        let bottomEdge = newY + newH

        if (snapToGrid) {
          leftEdge = Math.round(leftEdge / 5) * 5
          rightEdge = Math.round(rightEdge / 5) * 5
          topEdge = Math.round(topEdge / 5) * 5
          bottomEdge = Math.round(bottomEdge / 5) * 5
        }

        // Clamp edges to usable area (status bar reserved at bottom)
        leftEdge = Math.max(0, Math.min(screenW, leftEdge))
        rightEdge = Math.max(0, Math.min(screenW, rightEdge))
        topEdge = Math.max(0, Math.min(usableH, topEdge))
        bottomEdge = Math.max(0, Math.min(usableH, bottomEdge))

        // Ensure minimum size
        if (rightEdge - leftEdge < 10) {
          rightEdge = leftEdge + 10
        }
        if (bottomEdge - topEdge < 10) {
          bottomEdge = topEdge + 10
        }

        newX = leftEdge
        newW = rightEdge - leftEdge
        newY = topEdge
        newH = bottomEdge - topEdge

        onUpdate(state.ids[0], { x: newX, y: newY, w: newW, h: newH })
      }
    }

    if (rubberBandRef.current) {
      const { x: rawX, y: rawY } = clientToDevice(e.clientX, e.clientY, rect, screenW, screenH)
      const cx = Math.max(0, Math.min(screenW, rawX))
      const cy = Math.max(0, Math.min(screenH, rawY))
      rubberBandRef.current.currentX = cx
      rubberBandRef.current.currentY = cy
      const { startX, startY } = rubberBandRef.current
      setRubberBandRect({
        x: Math.min(startX, cx),
        y: Math.min(startY, cy),
        w: Math.abs(cx - startX),
        h: Math.abs(cy - startY),
      })
    }
  }, [onUpdate, screenW, screenH, usableH, snapToGrid])

  const handlePointerUp = useCallback(() => {
    if (dragState.current !== null && dragSnapshotRef.current !== null) {
      onCommitDragRef.current?.(dragSnapshotRef.current)
    }
    dragSnapshotRef.current = null
    dragState.current = null

    if (rubberBandRef.current) {
      const { startX, startY, currentX, currentY } = rubberBandRef.current
      const rb = {
        x: Math.min(startX, currentX),
        y: Math.min(startY, currentY),
        w: Math.abs(currentX - startX),
        h: Math.abs(currentY - startY),
      }
      if (rb.w > 3 || rb.h > 3) {
        const hit = widgetsRef.current
          .filter(w =>
            w.x < rb.x + rb.w && w.x + w.w > rb.x &&
            w.y < rb.y + rb.h && w.y + w.h > rb.y
          )
          .map(w => w.id)
        onSelectManyRef.current(hit)
      }
      rubberBandRef.current = null
      setRubberBandRect(null)
    }
  }, [])

  // Attach/detach global listeners while interacting
  if (dragState.current || rubberBandRef.current) {
    document.addEventListener('pointermove', handlePointerMove, { passive: false })
    document.addEventListener('pointerup', handlePointerUp)
  } else {
    document.removeEventListener('pointermove', handlePointerMove)
    document.removeEventListener('pointerup', handlePointerUp)
  }

  return (
    <div
      ref={containerRef}
      className="canvas-container"
      onPointerDown={onContainerPointerDown}
    >
      <div className="canvas-board-frame">
        {showPortLabels && (
          <div className={`canvas-port-label edge-${portEdges.usb} port-usb`}>USB</div>
        )}
        <div
          ref={canvasRef}
          className="canvas"
          style={{ width: screenW * scale, height: screenH * scale }}
          onPointerDown={onCanvasPointerDown}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
        {/* Grid dots */}
        {showGrid && (
          <svg
            width={screenW * scale}
            height={screenH * scale}
            style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none' }}
          >
            {Array.from({ length: screenW / 10 }).map((_, gx) =>
              Array.from({ length: screenH / 10 }).map((_, gy) => (
                <circle
                  key={`${gx}-${gy}`}
                  cx={gx * 10 * scale + 1}
                  cy={gy * 10 * scale + 1}
                  r={1.2}
                  fill="#4a4a7e"
                />
              ))
            )}
          </svg>
        )}

        {widgets.map(w => (
          <WidgetView
            key={w.id}
            widget={w}
            isSelected={selectedIds.includes(w.id)}
            onPointerDown={handlePointerDown}
            scale={scale}
            pageIdx={pageIdx}
          />
        ))}

        {/* Firmware always draws IP + version here (portrait & landscape) */}
        <div
          className="canvas-status-bar"
          style={{
            position: 'absolute',
            left: 0,
            top: (screenH - STATUS_BAR_H) * scale,
            width: screenW * scale,
            height: STATUS_BAR_H * scale,
            pointerEvents: 'none',
          }}
        >
          <span className="canvas-status-ip">192.168.x.x</span>
          <span className="canvas-status-ver">v{appVersion}</span>
        </div>

        {/* Rubber band selection rect */}
        {rubberBandRect && rubberBandRect.w > 1 && rubberBandRect.h > 1 && (
          <div
            className="rubber-band"
            style={{
              left:   rubberBandRect.x * scale,
              top:    rubberBandRect.y * scale,
              width:  rubberBandRect.w * scale,
              height: rubberBandRect.h * scale,
            }}
          />
        )}

        <div className="canvas-label canvas-label-top" style={{ left: 0, top: -18 }}>0</div>
        <div className="canvas-label canvas-label-top" style={{ left: screenW * scale, top: -18 }}>{screenW}</div>
        <div className="canvas-label canvas-label-left" style={{ left: -36, top: 0 }}>0</div>
        <div className="canvas-label canvas-label-left" style={{ left: -36, top: screenH * scale }}>{screenH}</div>
      </div>
      </div>
    </div>
  )
}

function WidgetView({ widget, isSelected, onPointerDown, scale, pageIdx = 0 }) {
  const style = {
    position: 'absolute',
    left: widget.x * scale,
    top: widget.y * scale,
    width: widget.w * scale,
    height: widget.h * scale,
  }

  const custom = widget.color || null

  if (widget.type === 'Button') {
    const btnStyle = custom ? { ...style, background: custom } : style
    return (
      <div
        className={`canvas-widget canvas-widget-button ${isSelected ? 'selected' : ''}`}
        style={btnStyle}
        onPointerDown={(e) => onPointerDown(e, widget.id, 'move')}
      >
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tr" />
        <span className="widget-label">{widget.label || 'BTN'}</span>
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="bl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="br" />
      </div>
    )
  }

  if (widget.type === 'Toggle') {
    const isOn = !!widget.default
    const togStyle = custom
      ? {
          ...style,
          background: isOn ? lightenHex(custom, 28) : darkenHex(custom, 28),
          boxShadow: isOn ? `inset 0 0 0 2px ${lightenHex(custom, 90)}` : 'none',
        }
      : style
    return (
      <div
        className={`canvas-widget canvas-widget-toggle ${isOn ? 'toggle-on' : ''} ${isSelected ? 'selected' : ''}`}
        style={togStyle}
        onPointerDown={(e) => onPointerDown(e, widget.id, 'move')}
      >
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tr" />
        <span
          className="toggle-indicator"
          style={custom ? { background: lightenHex(custom, 80) } : undefined}
        />
        <span className="widget-label">{widget.label || 'TOG'}</span>
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="bl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="br" />
      </div>
    )
  }

  if (widget.type === 'Slider') {
    return (
      <div
        className={`canvas-widget canvas-widget-slider ${isSelected ? 'selected' : ''}`}
        style={style}
        onPointerDown={(e) => onPointerDown(e, widget.id, 'move')}
      >
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tr" />
        <div
          className="slider-track"
          style={custom ? { background: custom } : undefined}
        />
        <span className="widget-label">{widget.label || 'SLIDER'}</span>
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="bl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="br" />
      </div>
    )
  }

  if (widget.type === 'HSlider') {
    return (
      <div
        className={`canvas-widget canvas-widget-hslider ${isSelected ? 'selected' : ''}`}
        style={style}
        onPointerDown={(e) => onPointerDown(e, widget.id, 'move')}
      >
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tr" />
        <div
          className="hslider-track"
          style={custom ? { background: custom } : undefined}
        />
        <span className="widget-label">{widget.label || 'HSLIDER'}</span>
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="bl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="br" />
      </div>
    )
  }

  if (widget.type === 'PageButton') {
    const navMode = widget.nav_mode || 'goto'
    const defaultLabel = navMode === 'prev' ? '◀ PREV'
                       : navMode === 'next' ? 'NEXT ▶'
                       : `▶ P${(widget.target_page ?? 0) + 1}`
    const pageStyle = custom ? { ...style, background: custom } : style
    return (
      <div
        className={`canvas-widget canvas-widget-pagebutton ${isSelected ? 'selected' : ''}`}
        style={pageStyle}
        data-page-link="1"
        data-widget-id={widget.id}
        data-page-idx={pageIdx}
        onPointerDown={(e) => onPointerDown(e, widget.id, 'move')}
      >
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tr" />
        <span
          className="widget-label pagebutton-label"
          style={custom ? { color: lightenHex(custom, 120) } : undefined}
        >{widget.label || defaultLabel}</span>
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="bl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="br" />
      </div>
    )
  }

  return null
}

function parseHex(hex) {
  if (!hex || typeof hex !== 'string') return null
  const s = hex.startsWith('#') ? hex.slice(1) : hex
  if (s.length !== 6) return null
  const n = Number.parseInt(s, 16)
  if (Number.isNaN(n)) return null
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

function formatHex(r, g, b) {
  const h = (v) => Math.max(0, Math.min(255, v | 0)).toString(16).padStart(2, '0')
  return `#${h(r)}${h(g)}${h(b)}`
}

function lightenHex(hex, amount = 40) {
  const rgb = parseHex(hex)
  if (!rgb) return hex
  return formatHex(rgb[0] + amount, rgb[1] + amount, rgb[2] + amount)
}

function darkenHex(hex, amount = 40) {
  const rgb = parseHex(hex)
  if (!rgb) return hex
  return formatHex(rgb[0] - amount, rgb[1] - amount, rgb[2] - amount)
}

function ResizeHandle({ widgetId, onPointerDown, corner = 'br' }) {
  const mode = `resize-${corner}`
  return (
    <div
      className={`resize-handle resize-handle-${corner}`}
      onPointerDown={(e) => onPointerDown(e, widgetId, mode)}
    />
  )
}
