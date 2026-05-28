import { useState, useCallback, useEffect, useRef } from 'react'
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
  Button:     { type: 'Button',     w: 105, h: 80 },
  Slider:     { type: 'Slider',     w: 30,  h: 140 },
  HSlider:    { type: 'HSlider',    w: 140, h: 30 },
  HSVPicker:  { type: 'HSVPicker',  w: 90,  h: 140 },
  IPDisplay:  { type: 'IPDisplay',  w: 120, h: 30 },
  PageButton: { type: 'PageButton', w: 60,  h: 30 },
}

export default function App() {
  // pagesState holds [[widget, ...], [widget, ...], ...] — one array per page
  const pagesState = useUndoableState([[]])
  const [currentPage, setCurrentPage] = useState(0)
  const [selectedIds, setSelectedIds] = useState([])
  const [clipboard, setClipboard] = useState([])
  const [landscape, setLandscape] = useState(false)
  const [showGrid, setShowGrid] = useState(true)
  const [snapToGrid, setSnapToGrid] = useState(true)

  const screenW = landscape ? LANDSCAPE.w : PORTRAIT.w
  const screenH = landscape ? LANDSCAPE.h : PORTRAIT.h

  // Stable refs so callbacks always read the latest values without deps
  const currentPageRef = useRef(currentPage)
  currentPageRef.current = currentPage
  const pagesRef = useRef(pagesState.value)
  pagesRef.current = pagesState.value

  const widgets = pagesState.value[currentPage] || []

  // --- Helpers: operate only on the current page ---
  const updatePage = useCallback((updater) => {
    pagesState.set(prev => {
      const pi = currentPageRef.current
      const next = [...prev]
      next[pi] = updater(next[pi] || [])
      return next
    })
  }, [pagesState.set])

  const updatePageSilent = useCallback((updater) => {
    pagesState.setSilent(prev => {
      const pi = currentPageRef.current
      const next = [...prev]
      next[pi] = updater(next[pi] || [])
      return next
    })
  }, [pagesState.setSilent])

  // --- Page management ---
  const addPage = useCallback(() => {
    const newIdx = pagesRef.current.length
    pagesState.set(prev => [...prev, []])
    setCurrentPage(newIdx)
    setSelectedIds([])
  }, [pagesState.set])

  const removePage = useCallback((idx) => {
    const len = pagesRef.current.length
    if (len <= 1) return
    const widgetCount = pagesRef.current[idx]?.length ?? 0
    if (widgetCount > 0) {
      const ok = window.confirm(`Page ${idx + 1} には ${widgetCount} 個のウィジェットがあります。\n削除してよいですか？`)
      if (!ok) return
    }
    pagesState.set(prev => prev.filter((_, i) => i !== idx))
    setCurrentPage(prev => {
      if (idx < prev) return prev - 1
      return Math.min(prev, len - 2)
    })
    setSelectedIds([])
  }, [pagesState.set])

  const switchPage = useCallback((idx) => {
    setCurrentPage(idx)
    setSelectedIds([])
  }, [])

  // --- Widget management ---
  const onAddWidget = useCallback((templateType, x, y) => {
    const tmpl = WIDGET_TEMPLATES[templateType]
    const currentWidgets = pagesRef.current[currentPageRef.current] || []
    const count = currentWidgets.filter(w => w.type === templateType).length + 1
    let nx = Math.max(0, Math.min(screenW - tmpl.w, x || 10))
    let ny = Math.max(0, Math.min(screenH - tmpl.h, y || 10))

    const labels = {
      Button: 'BTN ', Slider: 'SLIDER ', HSlider: 'HSLIDER ',
      HSVPicker: 'HSV ', IPDisplay: 'IP:', PageButton: 'PAGE ',
    }
    const newWidget = {
      id: Date.now(),
      type: templateType,
      x: nx, y: ny, w: tmpl.w, h: tmpl.h,
      label: (labels[templateType] || '') + count,
      osc_addr: templateType === 'Button'      ? `/esp32/button/${count}`
               : templateType === 'Slider'     ? `/esp32/slider/${count}`
               : templateType === 'HSlider'    ? `/esp32/hslider/${count}`
               : templateType === 'HSVPicker'  ? `/esp32/color/${count}`
               : templateType === 'IPDisplay'  ? `/esp32/ip/1`
               : '',
    }
    if (templateType === 'Slider' || templateType === 'HSlider') newWidget.default = 127
    if (templateType === 'HSVPicker') newWidget.default = [127, 127, 127]
    if (templateType === 'PageButton') { newWidget.target_page = 1; newWidget.nav_mode = 'goto' }

    const overlap = currentWidgets.find(w => w.x === nx && w.y === ny)
    if (overlap) newWidget.x += tmpl.w + 5

    updatePage(prev => [...prev, newWidget])
    setSelectedIds([newWidget.id])
  }, [updatePage, screenW, screenH])

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

  const onSelectMany = useCallback((ids) => setSelectedIds(ids), [])

  // History-recording versions (Properties panel)
  const onUpdate = useCallback((id, changes) => {
    updatePage(prev => prev.map(w => w.id === id ? { ...w, ...changes } : w))
  }, [updatePage])

  const onUpdateMany = useCallback((updaterFn) => {
    updatePage(updaterFn)
  }, [updatePage])

  // Silent versions (Canvas drag — no per-frame history)
  const onUpdateSilent = useCallback((id, changes) => {
    updatePageSilent(prev => prev.map(w => w.id === id ? { ...w, ...changes } : w))
  }, [updatePageSilent])

  const onUpdateManySilent = useCallback((updaterFn) => {
    updatePageSilent(updaterFn)
  }, [updatePageSilent])

  // Canvas calls this to snapshot ALL pages at drag start, then commits on drag end
  const onGetSnapshot = useCallback(() => pagesRef.current, [])
  const onCommitDrag = useCallback((snapshot) => {
    pagesState.pushToHistory(snapshot)
  }, [pagesState.pushToHistory])

  const onReorder = useCallback((id, direction) => {
    updatePage(prev => {
      const idx = prev.findIndex(w => w.id === id)
      if (idx === -1) return prev
      const swapIdx = direction === 'up' ? idx + 1 : idx - 1
      if (swapIdx < 0 || swapIdx >= prev.length) return prev
      const next = [...prev]
      ;[next[idx], next[swapIdx]] = [next[swapIdx], next[idx]]
      return next
    })
  }, [updatePage])

  const onDelete = useCallback((id) => {
    updatePage(prev => prev.filter(w => w.id !== id))
    setSelectedIds(prev => prev.filter(sid => sid !== id))
  }, [updatePage])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return

      if (e.key === 'Escape') { setSelectedIds([]); return }

      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedIds.length > 0) {
        updatePage(prev => prev.filter(w => !selectedIds.includes(w.id)))
        setSelectedIds([])
        return
      }

      const mod = e.ctrlKey || e.metaKey
      const currentWidgets = pagesRef.current[currentPageRef.current] || []

      if (mod && e.key === 'a') {
        e.preventDefault()
        setSelectedIds(currentWidgets.map(w => w.id))
        return
      }

      if (mod && e.key === 'c' && selectedIds.length > 0) {
        e.preventDefault()
        setClipboard(
          currentWidgets
            .filter(w => selectedIds.includes(w.id))
            .map(({ id, ...rest }) => rest) // eslint-disable-line no-unused-vars
        )
        return
      }

      if (mod && e.key === 'x' && selectedIds.length > 0) {
        e.preventDefault()
        setClipboard(
          currentWidgets
            .filter(w => selectedIds.includes(w.id))
            .map(({ id, ...rest }) => rest) // eslint-disable-line no-unused-vars
        )
        updatePage(prev => prev.filter(w => !selectedIds.includes(w.id)))
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
        updatePage(prev => [...prev, ...pasted])
        setSelectedIds(pasted.map(w => w.id))
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [selectedIds, clipboard, updatePage, screenW, screenH])

  const selectedWidget = selectedIds.length === 1
    ? widgets.find(w => w.id === selectedIds[0]) || null
    : null

  const pageCount = pagesState.value.length

  return (
    <div className="app">
      <header className="app-header">
        <h1>ESP32 UI Layout Editor</h1>
        <div className="header-actions">
          <ExportButton
            pages={pagesState.value}
            orientation={landscape ? 'landscape' : 'portrait'}
            onLoad={(data) => {
              pagesState.set(() => data.pages)
              setLandscape(data.orientation === 'landscape')
              setCurrentPage(0)
              setSelectedIds([])
            }}
          />
        </div>
      </header>

      <div className="page-tabs">
        {pagesState.value.map((_, idx) => (
          <button
            key={idx}
            className={`page-tab ${idx === currentPage ? 'active' : ''}`}
            onClick={() => switchPage(idx)}
          >
            Page {idx + 1}
            {pageCount > 1 && (
              <span
                className="page-tab-close"
                onClick={e => { e.stopPropagation(); removePage(idx) }}
              >×</span>
            )}
          </button>
        ))}
        <button className="page-tab-add" onClick={addPage}>+ Page</button>
      </div>

      <div className="app-body">
        <WidgetPanel onDrop={onAddWidget} />
        <div className="canvas-area">
          <div className="canvas-overlay-toolbar">
            <button
              className={`canvas-tool-btn ${pagesState.canUndo ? '' : 'disabled'}`}
              onClick={pagesState.undo}
              title="Undo (Cmd+Z)"
            >↩ Undo</button>
            <button
              className={`canvas-tool-btn ${pagesState.canRedo ? '' : 'disabled'}`}
              onClick={pagesState.redo}
              title="Redo (Cmd+Shift+Z)"
            >Redo ↪</button>
            <div className="canvas-toolbar-sep" />
            <button
              className={`canvas-tool-btn ${landscape ? 'active' : ''}`}
              onClick={() => setLandscape(prev => !prev)}
              title="向きを切り替え"
            >{landscape ? 'Land' : 'Port'}</button>
            <button
              className={`canvas-tool-btn ${showGrid ? 'active' : ''}`}
              onClick={() => setShowGrid(prev => !prev)}
              title="グリッド表示"
            >Grid</button>
            <button
              className={`canvas-tool-btn ${snapToGrid ? 'active' : ''}`}
              onClick={() => setSnapToGrid(prev => !prev)}
              title="スナップ"
            >Snap</button>
          </div>
          <Canvas
            widgets={widgets}
            selectedIds={selectedIds}
            onSelect={onSelect}
            onSelectMany={onSelectMany}
            onAddWidget={onAddWidget}
            onUpdate={onUpdateSilent}
            onUpdateMany={onUpdateManySilent}
            onCommitDrag={onCommitDrag}
            onGetSnapshot={onGetSnapshot}
            screenW={screenW}
            screenH={screenH}
            showGrid={showGrid}
            snapToGrid={snapToGrid}
          />
        </div>
        <div className="right-sidebar">
          <Properties
            widget={selectedWidget}
            selectedIds={selectedIds}
            widgets={widgets}
            pageCount={pageCount}
            onUpdate={onUpdate}
            onUpdateMany={onUpdateMany}
            onDelete={onDelete}
          />
          <LayersPanel
            widgets={widgets}
            selectedIds={selectedIds}
            onSelect={onSelect}
            onReorder={onReorder}
          />
        </div>
      </div>
    </div>
  )
}
