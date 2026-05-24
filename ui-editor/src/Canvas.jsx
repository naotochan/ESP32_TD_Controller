import { useState, useCallback, useRef } from 'react'

const SCALE = 2 // display at 2x for visibility

const WIDGET_TEMPLATES = {
  Button:    { w: 105, h: 80 },
  Slider:    { w: 30,  h: 140 },
  RGBPicker: { w: 90,  h: 140 },
}

export default function Canvas({ widgets, selectedId, onSelect, onUpdate, onAddWidget, screenW, screenH }) {
  const canvasRef = useRef(null)
  const dragState = useRef(null)

  // Drag-and-drop from WidgetPanel
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

  const handlePointerDown = useCallback((e, widgetId, mode) => {
    e.stopPropagation()
    e.preventDefault()
    const rect = canvasRef.current.getBoundingClientRect()
    const pointerX = (e.clientX - rect.left) / SCALE
    const pointerY = (e.clientY - rect.top) / SCALE

    if (mode === 'move') {
      const w = widgets.find(w => w.id === widgetId)
      dragState.current = {
        id: widgetId,
        startX: pointerX,
        startY: pointerY,
        origX: w.x,
        origY: w.y,
      }
    } else if (mode === 'resize') {
      const w = widgets.find(w => w.id === widgetId)
      dragState.current = {
        id: widgetId,
        startX: pointerX,
        startY: pointerY,
        origW: w.w,
        origH: w.h,
      }
    }

    onSelect(widgetId)
  }, [widgets, onSelect])

  const onCanvasPointerDown = useCallback((e) => {
    // Deselect if clicking empty area
    onSelect(null)
  }, [onSelect])

  const handlePointerMove = useCallback((e) => {
    if (!dragState.current) return
    e.preventDefault()

    const rect = canvasRef.current.getBoundingClientRect()
    const pointerX = (e.clientX - rect.left) / SCALE
    const pointerY = (e.clientY - rect.top) / SCALE

    const state = dragState.current
    const dx = Math.round(pointerX - state.startX)
    const dy = Math.round(pointerY - state.startY)

    if ('origX' in state) {
      // Move with grid snap (5px)
      let nx = Math.max(0, Math.min(screenW - 10, Math.round((state.origX + dx) / 5) * 5))
      let ny = Math.max(0, Math.min(screenH - 10, Math.round((state.origY + dy) / 5) * 5))
      onUpdate(state.id, { x: nx, y: ny })
    } else if ('origW' in state) {
      // Resize with minimum 10px
      let nw = Math.max(10, state.origW + dx)
      let nh = Math.max(10, state.origH + dy)
      onUpdate(state.id, { w: nw, h: nh })
    }
  }, [onUpdate, screenW, screenH])

  const handlePointerUp = useCallback(() => {
    dragState.current = null
  }, [])

  // Global pointer events for drag outside canvas
  if (dragState.current) {
    document.addEventListener('pointermove', handlePointerMove, { passive: false })
    document.addEventListener('pointerup', handlePointerUp)
  } else {
    document.removeEventListener('pointermove', handlePointerMove)
    document.removeEventListener('pointerup', handlePointerUp)
  }

  return (
    <div className="canvas-container">
      <div
        ref={canvasRef}
        className="canvas"
        style={{
          width: screenW * SCALE,
          height: screenH * SCALE,
        }}
        onPointerDown={onCanvasPointerDown}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        {/* Grid dots (SVG for performance) */}
        <svg
          className="grid-svg"
          width={screenW * SCALE}
          height={screenH * SCALE}
          style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none' }}
        >
          {Array.from({ length: screenW / 10 }).map((_, gx) =>
            Array.from({ length: screenH / 10 }).map((_, gy) => (
              <circle
                key={`dot-${gx}-${gy}`}
                cx={gx * 10 * SCALE + 1}
                cy={gy * 10 * SCALE + 1}
                r={0.5}
                fill="#2a2a4e"
              />
            ))
          )}
        </svg>

        {/* Widgets */}
        {widgets.map(w => (
          <WidgetView
            key={w.id}
            widget={w}
            isSelected={w.id === selectedId}
            onPointerDown={handlePointerDown}
            scale={SCALE}
          />
        ))}

        {/* Coordinate labels */}
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
        <span className="widget-label">{widget.label || 'BTN'}</span>
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} />
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
        <div className="slider-track" />
        <span className="widget-label">Slider</span>
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} />
      </div>
    )
  }

  if (widget.type === 'RGBPicker') {
    return (
      <div
        className={`canvas-widget canvas-widget-rgb ${isSelected ? 'selected' : ''}`}
        style={style}
        onPointerDown={(e) => onPointerDown(e, widget.id, 'move')}
      >
        <div className="rgb-tracks">
          <div className="slider-track track-r" />
          <div className="slider-track track-g" />
          <div className="slider-track track-b" />
        </div>
        <span className="widget-label">RGB</span>
        <ResizeHandle widgetId={widget.id} onPointerDown={onPointerDown} />
      </div>
    )
  }

  return null
}

function ResizeHandle({ widgetId, onPointerDown }) {
  return (
    <div
      className="resize-handle"
      onPointerDown={(e) => onPointerDown(e, widgetId, 'resize')}
    />
  )
}
