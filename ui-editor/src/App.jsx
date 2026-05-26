import { useState, useCallback, useEffect } from 'react'
import './App.css'
import Canvas from './Canvas'
import WidgetPanel from './WidgetPanel'
import Properties from './Properties'
import ExportButton from './ExportButton'
import useUndoableState from './useUndoableState'
import LayersPanel from './LayersPanel'

const PORTRAIT = { w: 240, h: 320 }
const LANDSCAPE = { w: 320, h: 240 }

const WIDGET_TEMPLATES = {
  Button:    { type: 'Button',    w: 105, h: 80 },
  Slider:    { type: 'Slider',    w: 30,  h: 140 },
  HSlider:   { type: 'HSlider',   w: 140, h: 30 },
  HSVPicker: { type: 'HSVPicker', w: 90,  h: 140 },
  IPDisplay: { type: 'IPDisplay', w: 120, h: 30 },
}

export default function App() {
  const widgetsState = useUndoableState([])
  const [selectedIds, setSelectedIds] = useState([])
  const [clipboard, setClipboard] = useState([])
  const [landscape, setLandscape] = useState(false)
  const [showGrid, setShowGrid] = useState(true)
  const [snapToGrid, setSnapToGrid] = useState(true)

  const screenW = landscape ? LANDSCAPE.w : PORTRAIT.w
  const screenH = landscape ? LANDSCAPE.h : PORTRAIT.h

  const onAddWidget = useCallback((templateType, x, y) => {
    const tmpl = WIDGET_TEMPLATES[templateType]
    const count = widgetsState.value.filter(w => w.type === templateType).length + 1
    let nx = Math.max(0, Math.min(screenW - tmpl.w, x || 10))
    let ny = Math.max(0, Math.min(screenH - tmpl.h, y || 10))

    const labels = { Button: 'BTN ', Slider: 'SLIDER ', HSlider: 'HSLIDER ', HSVPicker: 'HSV ', IPDisplay: 'IP:' }
    const newWidget = {
      id: Date.now(),
      type: templateType,
      x: nx,
      y: ny,
      w: tmpl.w,
      h: tmpl.h,
      label: (labels[templateType] || '') + count,
      osc_addr: templateType === 'Button'
        ? `/esp32/button/${count}`
        : templateType === 'Slider'
          ? `/esp32/slider/${count}`
          : templateType === 'HSlider'
            ? `/esp32/hslider/${count}`
            : templateType === 'HSVPicker'
              ? `/esp32/color/${count}`
              : templateType === 'IPDisplay'
                ? `/esp32/ip/1`
                : `/esp32/widget/${count}`,
    }
    if (templateType === 'Slider' || templateType === 'HSlider') newWidget.default = 127
    if (templateType === 'HSVPicker') newWidget.default = [127, 127, 127]

    const overlap = widgetsState.value.find(w => w.x === nx && w.y === ny)
    if (overlap) newWidget.x += tmpl.w + 5

    widgetsState.set(prev => [...prev, newWidget])
    setSelectedIds([newWidget.id])
  }, [widgetsState.value, screenW, screenH, widgetsState.set])

  const onSelect = useCallback((id, additive = false) => {
    if (id == null) {
      setSelectedIds([])
    } else if (additive) {
      setSelectedIds(prev =>
        prev.includes(id) ? prev.filter(sid => sid !== id) : [...prev, id]
      )
    } else {
      setSelectedIds([id])
    }
  }, [])

  const onSelectMany = useCallback((ids) => {
    setSelectedIds(ids)
  }, [])

  // History-recording versions — used by Properties panel
  const onUpdate = useCallback((id, changes) => {
    widgetsState.set(prev => prev.map(w => w.id === id ? { ...w, ...changes } : w))
  }, [widgetsState.set])

  const onUpdateMany = useCallback((updaterFn) => {
    widgetsState.set(updaterFn)
  }, [widgetsState.set])

  // Silent versions — used by Canvas during drag (no per-frame history)
  const onUpdateSilent = useCallback((id, changes) => {
    widgetsState.setSilent(prev => prev.map(w => w.id === id ? { ...w, ...changes } : w))
  }, [widgetsState.setSilent])

  const onUpdateManySilent = useCallback((updaterFn) => {
    widgetsState.setSilent(updaterFn)
  }, [widgetsState.setSilent])

  // Commit one undo step at drag end (snapshot = state at drag start)
  const onCommitDrag = useCallback((snapshot) => {
    widgetsState.pushToHistory(snapshot)
  }, [widgetsState.pushToHistory])

  const onReorder = useCallback((id, direction) => {
    widgetsState.set(prev => {
      const idx = prev.findIndex(w => w.id === id)
      if (idx === -1) return prev
      const swapIdx = direction === 'up' ? idx + 1 : idx - 1
      if (swapIdx < 0 || swapIdx >= prev.length) return prev
      const next = [...prev]
      ;[next[idx], next[swapIdx]] = [next[swapIdx], next[idx]]
      return next
    })
  }, [widgetsState.set])

  const onDelete = useCallback((id) => {
    widgetsState.set(prev => prev.filter(w => w.id !== id))
    setSelectedIds(prev => prev.filter(sid => sid !== id))
  }, [widgetsState.set])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return

      // Escape: deselect all
      if (e.key === 'Escape') {
        setSelectedIds([])
        return
      }

      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedIds.length > 0) {
        widgetsState.set(prev => prev.filter(w => !selectedIds.includes(w.id)))
        setSelectedIds([])
        return
      }

      const mod = e.ctrlKey || e.metaKey

      if (mod && e.key === 'a') {
        e.preventDefault()
        setSelectedIds(widgetsState.value.map(w => w.id))
        return
      }

      if (mod && e.key === 'c' && selectedIds.length > 0) {
        e.preventDefault()
        const copied = widgetsState.value
          .filter(w => selectedIds.includes(w.id))
          .map(({ id, ...rest }) => rest) // eslint-disable-line no-unused-vars
        setClipboard(copied)
        return
      }

      if (mod && e.key === 'x' && selectedIds.length > 0) {
        e.preventDefault()
        const copied = widgetsState.value
          .filter(w => selectedIds.includes(w.id))
          .map(({ id, ...rest }) => rest) // eslint-disable-line no-unused-vars
        setClipboard(copied)
        widgetsState.set(prev => prev.filter(w => !selectedIds.includes(w.id)))
        setSelectedIds([])
        return
      }

      if (mod && e.key === 'v' && clipboard.length > 0) {
        e.preventDefault()
        const base = Date.now()
        const pasted = clipboard.map((w, i) => ({
          ...w,
          id: base + i,
          x: Math.min(screenW - w.w, w.x + 10),
          y: Math.min(screenH - w.h, w.y + 10),
        }))
        widgetsState.set(prev => [...prev, ...pasted])
        setSelectedIds(pasted.map(w => w.id))
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [selectedIds, clipboard, widgetsState.value, widgetsState.set, screenW, screenH])

  const selectedWidget = selectedIds.length === 1
    ? widgetsState.value.find(w => w.id === selectedIds[0]) || null
    : null

  return (
    <div className="app">
      <header className="app-header">
        <h1>ESP32 UI Layout Editor</h1>
        <div className="header-actions">
          <button
            className={`history-btn ${widgetsState.canUndo ? '' : 'disabled'}`}
            onClick={widgetsState.undo}
            title="Undo (Cmd+Z)"
          >
            ← Undo
          </button>
          <button
            className={`history-btn ${widgetsState.canRedo ? '' : 'disabled'}`}
            onClick={widgetsState.redo}
            title="Redo (Cmd+Shift+Z)"
          >
            Redo →
          </button>
          <button
            className={`orientation-toggle ${landscape ? 'active' : ''}`}
            onClick={() => setLandscape(prev => !prev)}
          >
            {landscape ? 'Landscape' : 'Portrait'}
          </button>
          <button
            className={`grid-toggle ${showGrid ? 'active' : ''}`}
            onClick={() => setShowGrid(prev => !prev)}
          >
            Grid
          </button>
          <button
            className={`snap-toggle ${snapToGrid ? 'active' : ''}`}
            onClick={() => setSnapToGrid(prev => !prev)}
          >
            Snap
          </button>
          <ExportButton widgets={widgetsState.value} orientation={landscape ? 'landscape' : 'portrait'} />
        </div>
      </header>
      <div className="app-body">
        <WidgetPanel onDrop={onAddWidget} />
        <Canvas
          widgets={widgetsState.value}
          selectedIds={selectedIds}
          onSelect={onSelect}
          onSelectMany={onSelectMany}
          onAddWidget={onAddWidget}
          onUpdate={onUpdateSilent}
          onUpdateMany={onUpdateManySilent}
          onCommitDrag={onCommitDrag}
          screenW={screenW}
          screenH={screenH}
          showGrid={showGrid}
          snapToGrid={snapToGrid}
        />
        <div className="right-sidebar">
          <Properties
            widget={selectedWidget}
            selectedIds={selectedIds}
            widgets={widgetsState.value}
            onUpdate={onUpdate}
            onUpdateMany={onUpdateMany}
            onDelete={onDelete}
          />
          <LayersPanel
            widgets={widgetsState.value}
            selectedIds={selectedIds}
            onSelect={onSelect}
            onReorder={onReorder}
          />
        </div>
      </div>
    </div>
  )
}
