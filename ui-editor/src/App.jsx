import { useState, useCallback, useEffect, useRef } from 'react'
import './App.css'
import Canvas, { STATUS_BAR_H } from './Canvas'
import WidgetPanel from './WidgetPanel'
import Properties from './Properties'
import ExportButton from './ExportButton'
import useUndoableState from './useUndoableState'
import LayersPanel from './LayersPanel'
import PageLinksOverlay from './PageLinksOverlay'

/** Screen size for rotation degrees 0/90/180/270 (CYD 240×320 panel). */
function screenSizeForRotation(deg) {
  return (deg % 180 === 0) ? { w: 240, h: 320 } : { w: 320, h: 240 }
}

/** Normalize loaded layout rotation → degrees 0|90|180|270. */
export function normalizeRotationDeg(data) {
  if (data && data.rotation != null) {
    const r = Number(data.rotation)
    if (r === 90 || r === 180 || r === 270) return r
    if (r === 0 || r === 1 || r === 2 || r === 3) return r * 90
  }
  if (data && data.orientation === 'landscape') return 90
  return 0
}

const ROTATION_STORAGE_KEY = 'esp32-td-rotation-deg'

function loadStoredRotationDeg() {
  try {
    const raw = localStorage.getItem(ROTATION_STORAGE_KEY)
    if (raw == null) return 0
    const n = Number(raw)
    if (n === 0 || n === 90 || n === 180 || n === 270) return n
  } catch {
    /* private mode / SSR */
  }
  return 0
}

function storeRotationDeg(deg) {
  try {
    localStorage.setItem(ROTATION_STORAGE_KEY, String(deg))
  } catch {
    /* ignore quota / private mode */
  }
}

const WIDGET_TEMPLATES = {
  Button:     { type: 'Button',     w: 105, h: 80 },
  Toggle:     { type: 'Toggle',     w: 105, h: 80 },
  Slider:     { type: 'Slider',     w: 30,  h: 140 },
  HSlider:    { type: 'HSlider',    w: 140, h: 30 },
  PageButton: { type: 'PageButton', w: 60,  h: 30 },
}

export default function App() {
  // pagesState holds [[widget, ...], [widget, ...], ...] — one array per page
  const pagesState = useUndoableState([[]])
  const [currentPage, setCurrentPage] = useState(0)
  const [selectedIds, setSelectedIds] = useState([])
  const [clipboard, setClipboard] = useState([])
  const [rotationDeg, setRotationDeg] = useState(loadStoredRotationDeg)
  const [showGrid, setShowGrid] = useState(true)
  const [snapToGrid, setSnapToGrid] = useState(true)

  const { w: screenW, h: screenH } = screenSizeForRotation(rotationDeg)

  useEffect(() => {
    storeRotationDeg(rotationDeg)
  }, [rotationDeg])

  // Stable refs so callbacks always read the latest values without deps
  const currentPageRef = useRef(currentPage)
  currentPageRef.current = currentPage
  const pagesRef = useRef(pagesState.value)
  pagesRef.current = pagesState.value
  const pagesRowRef = useRef(null)

  const widgets = pagesState.value[currentPage] || []

  // --- Helpers: operate on a specific page (defaults to current) ---
  const updatePageAt = useCallback((pageIdx, updater) => {
    pagesState.set(prev => {
      const next = [...prev]
      next[pageIdx] = updater(next[pageIdx] || [])
      return next
    })
  }, [pagesState.set])

  const updatePageAtSilent = useCallback((pageIdx, updater) => {
    pagesState.setSilent(prev => {
      const next = [...prev]
      next[pageIdx] = updater(next[pageIdx] || [])
      return next
    })
  }, [pagesState.setSilent])

  const updatePage = useCallback((updater) => {
    updatePageAt(currentPageRef.current, updater)
  }, [updatePageAt])

  const updatePageSilent = useCallback((updater) => {
    updatePageAtSilent(currentPageRef.current, updater)
  }, [updatePageAtSilent])

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
      const ok = window.confirm(
        `Page ${idx + 1} には ${widgetCount} 個のウィジェットがあります。\nこのページを削除しますか？`
      )
      if (!ok) return
    }
    pagesState.set(prev => {
      const next = prev.filter((_, i) => i !== idx)
      // Remap PageButton targets after the removed index
      return next.map(pageWidgets =>
        (pageWidgets || []).map(w => {
          if (w.type !== 'PageButton' || (w.nav_mode || 'goto') !== 'goto') return w
          const t = w.target_page ?? 0
          if (t === idx) return { ...w, target_page: Math.min(idx, next.length - 1) }
          if (t > idx) return { ...w, target_page: t - 1 }
          return w
        })
      )
    })
    setCurrentPage(prev => {
      if (idx < prev) return prev - 1
      return Math.min(prev, len - 2)
    })
    setSelectedIds([])
  }, [pagesState.set])

  const switchPage = useCallback((idx) => {
    if (idx === currentPageRef.current) return
    setCurrentPage(idx)
    setSelectedIds([])
  }, [])

  // --- Widget management ---
  const onAddWidgetToPage = useCallback((pageIdx, templateType, x, y) => {
    setCurrentPage(pageIdx)
    const tmpl = WIDGET_TEMPLATES[templateType]
    const currentWidgets = pagesRef.current[pageIdx] || []
    const count = currentWidgets.filter(w => w.type === templateType).length + 1
    let nx = Math.max(0, Math.min(screenW - tmpl.w, x || 10))
    let ny = Math.max(0, Math.min(screenH - STATUS_BAR_H - tmpl.h, y || 10))

    const labels = {
      Button: 'BTN ', Toggle: 'TOG ', Slider: 'SLIDER ', HSlider: 'HSLIDER ',
      PageButton: 'PAGE ',
    }
    const newWidget = {
      id: Date.now(),
      type: templateType,
      x: nx, y: ny, w: tmpl.w, h: tmpl.h,
      label: (labels[templateType] || '') + count,
      osc_addr: templateType === 'Button'      ? `/esp32/button/${count}`
               : templateType === 'Toggle'     ? `/esp32/toggle/${count}`
               : templateType === 'Slider'     ? `/esp32/slider/${count}`
               : templateType === 'HSlider'    ? `/esp32/hslider/${count}`
               : '',
    }
    if (templateType === 'Slider' || templateType === 'HSlider') newWidget.default = 127
    if (templateType === 'Toggle') newWidget.default = 0
    if (templateType === 'PageButton') { newWidget.target_page = 1; newWidget.nav_mode = 'goto' }

    const overlap = currentWidgets.find(w => w.x === nx && w.y === ny)
    if (overlap) newWidget.x += tmpl.w + 5

    updatePageAt(pageIdx, prev => [...prev, newWidget])
    setSelectedIds([newWidget.id])
  }, [updatePageAt, screenW, screenH])

  const onAddWidget = useCallback((templateType, x, y) => {
    onAddWidgetToPage(currentPageRef.current, templateType, x, y)
  }, [onAddWidgetToPage])

  const onSelectOnPage = useCallback((pageIdx, id, additive = false) => {
    setCurrentPage(pageIdx)
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

  const onSelect = useCallback((id, additive = false) => {
    onSelectOnPage(currentPageRef.current, id, additive)
  }, [onSelectOnPage])

  const onSelectManyOnPage = useCallback((pageIdx, ids) => {
    setCurrentPage(pageIdx)
    setSelectedIds(ids)
  }, [])

  const onSelectMany = useCallback((ids) => {
    onSelectManyOnPage(currentPageRef.current, ids)
  }, [onSelectManyOnPage])

  // History-recording versions (Properties panel)
  const onUpdate = useCallback((id, changes) => {
    updatePage(prev => prev.map(w => w.id === id ? { ...w, ...changes } : w))
  }, [updatePage])

  const onUpdateMany = useCallback((updaterFn) => {
    updatePage(updaterFn)
  }, [updatePage])

  // Silent versions for a specific page (Canvas drag)
  const onUpdateSilentOnPage = useCallback((pageIdx, id, changes) => {
    updatePageAtSilent(pageIdx, prev => prev.map(w => w.id === id ? { ...w, ...changes } : w))
  }, [updatePageAtSilent])

  const onUpdateManySilentOnPage = useCallback((pageIdx, updaterFn) => {
    updatePageAtSilent(pageIdx, updaterFn)
  }, [updatePageAtSilent])

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
          y: Math.min(screenH - STATUS_BAR_H - w.h, w.y + 10),
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
        <h1>ESP32 UI Layout Editor <span className="app-version">v0.3.3</span></h1>
        <div className="header-actions">
          <ExportButton
            pages={pagesState.value}
            rotationDeg={rotationDeg}
            onLoad={(data) => {
              pagesState.set(() => data.pages)
              setRotationDeg(normalizeRotationDeg(data))
              setCurrentPage(0)
              setSelectedIds([])
            }}
          />
        </div>
      </header>

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
            <div className="canvas-rotation-group" title="回転">
              <button
                type="button"
                className="canvas-tool-btn canvas-rot-btn"
                onClick={() => setRotationDeg((d) => (d + 90) % 360)}
                title="左回転"
                aria-label="左回転"
              >↶</button>
              <span className="canvas-rot-deg">{rotationDeg}°</span>
              <button
                type="button"
                className="canvas-tool-btn canvas-rot-btn"
                onClick={() => setRotationDeg((d) => (d + 270) % 360)}
                title="右回転"
                aria-label="右回転"
              >↷</button>
            </div>
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
            <div className="canvas-toolbar-sep" />
            <button
              className="canvas-tool-btn canvas-tool-btn-page"
              onClick={addPage}
              title="ページを追加"
            >＋ ページ</button>
            {pageCount > 1 && (
              <button
                className="canvas-tool-btn canvas-tool-btn-page-del"
                onClick={() => removePage(currentPage)}
                title="選択中のページを削除"
              >− ページ削除</button>
            )}
          </div>

          <div className="pages-row" ref={pagesRowRef}>
            <PageLinksOverlay
              containerRef={pagesRowRef}
              pages={pagesState.value}
              selectedIds={selectedIds}
              currentPage={currentPage}
              revision={`${rotationDeg}-${screenW}x${screenH}-${pageCount}`}
            />
            {pagesState.value.map((pageWidgets, idx) => {
              const active = idx === currentPage
              return (
                <div
                  key={idx}
                  className={`page-slot ${active ? 'active' : ''}`}
                  data-page-slot={idx}
                  onMouseDown={() => switchPage(idx)}
                >
                  <Canvas
                    widgets={pageWidgets}
                    selectedIds={active ? selectedIds : []}
                    onSelect={(id, additive) => onSelectOnPage(idx, id, additive)}
                    onSelectMany={(ids) => onSelectManyOnPage(idx, ids)}
                    onAddWidget={(type, x, y) => onAddWidgetToPage(idx, type, x, y)}
                    onUpdate={(id, changes) => onUpdateSilentOnPage(idx, id, changes)}
                    onUpdateMany={(fn) => onUpdateManySilentOnPage(idx, fn)}
                    onCommitDrag={onCommitDrag}
                    onGetSnapshot={onGetSnapshot}
                    screenW={screenW}
                    screenH={screenH}
                    showGrid={showGrid}
                    snapToGrid={snapToGrid}
                    rotationDeg={rotationDeg}
                    appVersion="0.3.3"
                    showPortLabels={idx === 0}
                    pageIdx={idx}
                  />
                  <div className="page-slot-footer">
                    <span className="page-slot-name">Page {idx + 1}</span>
                    {pageCount > 1 && (
                      <button
                        type="button"
                        className="page-slot-remove"
                        title="このページを削除"
                        onClick={(e) => { e.stopPropagation(); removePage(idx) }}
                      >削除</button>
                    )}
                  </div>
                </div>
              )
            })}
            <button
              type="button"
              className="page-slot page-slot-add"
              onClick={addPage}
              title="ページを追加"
            >
              <span className="page-slot-add-plus">+</span>
              <span className="page-slot-add-label">ページを追加</span>
            </button>
          </div>
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
