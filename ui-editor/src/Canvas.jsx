import { useState, useCallback, useRef } from 'react'

const SCALE = 2

const WIDGET_TEMPLATES = {
  Button:     { w: 105, h: 80 },
  Slider:     { w: 30,  h: 140 },
  HSlider:    { w: 140, h: 30 },
  HSVPicker:  { w: 90,  h: 140 },
  IPDisplay:  { w: 120, h: 30 },
  PageButton: { w: 60,  h: 30 },
}

export default function Canvas({
  widgets, selectedIds, onSelect, onSelectMany,
  onUpdate, onUpdateMany, onAddWidget, onCommitDrag, onGetSnapshot,
  screenW, screenH, showGrid, snapToGrid = true,
}) {
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
    const x = Math.round(((e.clientX - rect.left) / SCALE - WIDGET_TEMPLATES[widgetType].w / 2) / 5) * 5
    const y = Math.round(((e.clientY - rect.top) / SCALE - WIDGET_TEMPLATES[widgetType].h / 2) / 5) * 5
    onAddWidget(widgetType, x, y)
  }, [onAddWidget])

  // --- Widget pointer: start move or resize drag ---
  const handlePointerDown = useCallback((e, widgetId, mode) => {
    e.stopPropagation()
    e.preventDefault()
    const rect = canvasRef.current.getBoundingClientRect()
    const pointerX = (e.clientX - rect.left) / SCALE
    const pointerY = (e.clientY - rect.top) / SCALE
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
  }, [onSelect])

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
    const x = Math.max(0, Math.min(screenW, (e.clientX - rect.left) / SCALE))
    const y = Math.max(0, Math.min(screenH, (e.clientY - rect.top) / SCALE))
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
      const pointerX = (e.clientX - rect.left) / SCALE
      const pointerY = (e.clientY - rect.top) / SCALE
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
          ny = Math.max(0, Math.min(screenH - clampH, Math.round((firstOrig.y + dy) / 5) * 5))
        } else {
          nx = Math.max(0, Math.min(screenW - clampW, firstOrig.x + dx))
          ny = Math.max(0, Math.min(screenH - clampH, firstOrig.y + dy))
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
              y: Math.max(0, Math.min(screenH - ww.h, orig.y + snapDy)),
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

        // Clamp edges to screen
        leftEdge = Math.max(0, Math.min(screenW, leftEdge))
        rightEdge = Math.max(0, Math.min(screenW, rightEdge))
        topEdge = Math.max(0, Math.min(screenH, topEdge))
        bottomEdge = Math.max(0, Math.min(screenH, bottomEdge))

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
      const cx = Math.max(0, Math.min(screenW, (e.clientX - rect.left) / SCALE))
      const cy = Math.max(0, Math.min(screenH, (e.clientY - rect.top) / SCALE))
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
  }, [onUpdate, screenW, screenH, snapToGrid])

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
      <div
        ref={canvasRef}
        className="canvas"
        style={{ width: screenW * SCALE, height: screenH * SCALE }}
        onPointerDown={onCanvasPointerDown}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        {/* Grid dots */}
        {showGrid && (
          <svg
            width={screenW * SCALE}
            height={screenH * SCALE}
            style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none' }}
          >
            {Array.from({ length: screenW / 10 }).map((_, gx) =>
              Array.from({ length: screenH / 10 }).map((_, gy) => (
                <circle
                  key={`${gx}-${gy}`}
                  cx={gx * 10 * SCALE + 1}
                  cy={gy * 10 * SCALE + 1}
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
            scale={SCALE}
          />
        ))}

        {/* Rubber band selection rect */}
        {rubberBandRect && rubberBandRect.w > 1 && rubberBandRect.h > 1 && (
          <div
            className="rubber-band"
            style={{
              left:   rubberBandRect.x * SCALE,
              top:    rubberBandRect.y * SCALE,
              width:  rubberBandRect.w * SCALE,
              height: rubberBandRect.h * SCALE,
            }}
          />
        )}

        <div className="canvas-label canvas-label-top" style={{ left: 0, top: -18 }}>0</div>
        <div className="canvas-label canvas-label-top" style={{ left: screenW * SCALE, top: -18 }}>{screenW}</div>
        <div className="canvas-label canvas-label-left" style={{ left: -36, top: 0 }}>0</div>
        <div className="canvas-label canvas-label-left" style={{ left: -36, top: screenH * SCALE }}>{screenH}</div>
      </div>
    </div>
  )
}

function WidgetView({ widget, isSelected, onPointerDown, scale }) {
  const style = {
    position: 'absolute',
    left: widget.x * scale,
    top: widget.y * scale,
    width: widget.w * scale,
    height: widget.h * scale,
  }

  if (widget.type === 'Button') {
    return (
      <div
        className={`canvas-widget canvas-widget-button ${isSelected ? 'selected' : ''}`}
        style={style}
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

  if (widget.type === 'Slider') {
    return (
      <div
        className={`canvas-widget canvas-widget-slider ${isSelected ? 'selected' : ''}`}
        style={style}
        onPointerDown={(e) => onPointerDown(e, widget.id, 'move')}
      >
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tr" />
        <div className="slider-track" />
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
        <div className="hslider-track" />
        <span className="widget-label">{widget.label || 'HSLIDER'}</span>
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="bl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="br" />
      </div>
    )
  }

  if (widget.type === 'HSVPicker') {
    const wheelR = Math.min(widget.w, widget.h) * 0.42;
    const cx = widget.w * 0.5 - 10;
    const cy = widget.h / 2;
    const barX = widget.w - 20;
    const stops = 24;
    const wheelSVG = Array.from({ length: stops }, (_, i) => {
      const a1 = (2 * Math.PI * i) / stops;
      const a2 = (2 * Math.PI * (i + 1)) / stops;
      const x1o = cx + wheelR * Math.cos(a1);
      const y1o = cy + wheelR * Math.sin(a1);
      const x2o = cx + wheelR * Math.cos(a2);
      const y2o = cy + wheelR * Math.sin(a2);
      const large = ((a2 - a1) / (2 * Math.PI)) > 0.5 ? 1 : 0;
      const pathD = `M${cx},${cy}L${x1o.toFixed(1)},${y1o.toFixed(1)}A${wheelR},${wheelR} 0 ${large},1 ${x2o.toFixed(1)},${y2o.toFixed(1)}Z`;
      const midAngle = (a1 + a2) / 2;
      const hueDeg = ((midAngle / (2 * Math.PI)) * 360 + 360) % 360;
      return <path key={i} d={pathD} fill={`hsl(${hueDeg},100%,50%)`} />;
    });
    const barGradId = `vbar-${widget.id}`;
    return (
      <div
        className={`canvas-widget canvas-widget-hsv ${isSelected ? 'selected' : ''}`}
        style={style}
        onPointerDown={(e) => onPointerDown(e, widget.id, 'move')}
      >
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tr" />
        <svg width={widget.w} height={widget.h} className="hsv-wheel-svg">
          <defs>
            <linearGradient id={barGradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#fff" />
              <stop offset="100%" stopColor="#000" />
            </linearGradient>
          </defs>
          {wheelSVG}
          <rect x={barX} y={2} width={16} height={widget.h - 4} fill={`url(#${barGradId})`} rx={2} />
        </svg>
        <span className="widget-label hsv-label">{widget.label || 'HSV'}</span>
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="bl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="br" />
      </div>
    )
  }

  if (widget.type === 'IPDisplay') {
    return (
      <div
        className={`canvas-widget canvas-widget-ip ${isSelected ? 'selected' : ''}`}
        style={style}
        onPointerDown={(e) => onPointerDown(e, widget.id, 'move')}
      >
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tr" />
        <span className="widget-label">{widget.label || 'IP: ---'}</span>
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="bl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="br" />
      </div>
    )
  }

  if (widget.type === 'PageButton') {
    const target = widget.target_page != null ? widget.target_page + 1 : '?'
    return (
      <div
        className={`canvas-widget canvas-widget-pagebutton ${isSelected ? 'selected' : ''}`}
        style={style}
        onPointerDown={(e) => onPointerDown(e, widget.id, 'move')}
      >
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="tr" />
        <span className="widget-label pagebutton-label">▶ {target}</span>
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="bl" />
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} corner="br" />
      </div>
    )
  }

  return null
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
