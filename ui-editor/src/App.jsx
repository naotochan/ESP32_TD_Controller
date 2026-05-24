import { useState, useCallback } from 'react'
import './App.css'
import Canvas from './Canvas'
import WidgetPanel from './WidgetPanel'
import Properties from './Properties'
import ExportButton from './ExportButton'
import useUndoableState from './useUndoableState'

const PORTRAIT = { w: 240, h: 320 }
const LANDSCAPE = { w: 320, h: 240 }

const WIDGET_TEMPLATES = {
  Button:    { type: 'Button',    w: 105, h: 80 },
  Slider:    { type: 'Slider',    w: 30,  h: 140 },
  RGBPicker: { type: 'RGBPicker', w: 90,  h: 140 },
}

export default function App() {
  const widgetsState = useUndoableState([])
  const [selectedId, setSelectedId] = useState(null)
  const [landscape, setLandscape] = useState(false)

  const screenW = landscape ? LANDSCAPE.w : PORTRAIT.w
  const screenH = landscape ? LANDSCAPE.h : PORTRAIT.h

  const onAddWidget = useCallback((templateType, x, y) => {
    const tmpl = WIDGET_TEMPLATES[templateType]
    const count = widgetsState.value.filter(w => w.type === templateType).length + 1
    let nx = Math.max(0, Math.min(screenW - tmpl.w, x || 10))
    let ny = Math.max(0, Math.min(screenH - tmpl.h, y || 10))

    const newWidget = {
      id: Date.now(),
      type: templateType,
      x: nx,
      y: ny,
      w: tmpl.w,
      h: tmpl.h,
      label: templateType === 'Button' ? 'BTN ' + count : '',
      osc_addr: templateType === 'Button'
        ? `/esp32/button/${count}`
        : templateType === 'Slider'
          ? `/esp32/slider/${count}`
          : `/esp32/color/${count}`,
    }
    if (templateType === 'Slider')  newWidget.default = 127
    if (templateType === 'RGBPicker') newWidget.default = [127, 127, 127]

    const overlap = widgetsState.value.find(w => w.x === nx && w.y === ny)
    if (overlap) {
      newWidget.x += tmpl.w + 5
    }

    widgetsState.set(prev => [...prev, newWidget])
    setSelectedId(newWidget.id)
  }, [widgetsState.value, screenW, screenH, widgetsState.set])

  const onUpdate = useCallback((id, changes) => {
    widgetsState.set(prev => prev.map(w => w.id === id ? { ...w, ...changes } : w))
  }, [widgetsState.set])

  const onDelete = useCallback((id) => {
    widgetsState.set(prev => prev.filter(w => w.id !== id))
    setSelectedId(null)
  }, [widgetsState.set])

  const selectedWidget = widgetsState.value.find(w => w.id === selectedId) || null

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
            {landscape ? '🌄 Landscape' : '📱 Portrait'}
          </button>
          <ExportButton widgets={widgetsState.value} orientation={landscape ? 'landscape' : 'portrait'} />
        </div>
      </header>
      <div className="app-body">
        <WidgetPanel onDrop={onAddWidget} />
        <Canvas
          widgets={widgetsState.value}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onAddWidget={onAddWidget}
          onUpdate={onUpdate}
          screenW={screenW}
          screenH={screenH}
        />
        <Properties
          widget={selectedWidget}
          onUpdate={onUpdate}
          onDelete={onDelete}
        />
      </div>
    </div>
  )
}
