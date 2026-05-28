function rgbToHex([r, g, b]) {
  return '#' + [r, g, b].map(v => Math.min(255, Math.max(0, v)).toString(16).padStart(2, '0')).join('')
}

function hexToRgb(hex) {
  return [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16))
}

function AlignIcon({ type }) {
  const s = { display: 'block', pointerEvents: 'none' }
  if (type === 'left') return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" style={s}>
      <rect x="0.5" y="0.5" width="1.5" height="13"/>
      <rect x="3" y="2" width="8" height="3" rx="0.5"/>
      <rect x="3" y="9" width="5" height="3" rx="0.5"/>
    </svg>
  )
  if (type === 'centerH') return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" style={s}>
      <rect x="6.25" y="0.5" width="1.5" height="13"/>
      <rect x="2" y="2" width="10" height="3" rx="0.5"/>
      <rect x="3.5" y="9" width="7" height="3" rx="0.5"/>
    </svg>
  )
  if (type === 'right') return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" style={s}>
      <rect x="12" y="0.5" width="1.5" height="13"/>
      <rect x="3" y="2" width="8" height="3" rx="0.5"/>
      <rect x="6" y="9" width="5" height="3" rx="0.5"/>
    </svg>
  )
  if (type === 'distH') return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" style={s}>
      <rect x="0.5" y="0.5" width="1.5" height="13"/>
      <rect x="12" y="0.5" width="1.5" height="13"/>
      <rect x="5.5" y="2.5" width="3" height="9" rx="0.5"/>
    </svg>
  )
  if (type === 'top') return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" style={s}>
      <rect x="0.5" y="0.5" width="13" height="1.5"/>
      <rect x="2" y="3" width="3" height="8" rx="0.5"/>
      <rect x="9" y="3" width="3" height="5" rx="0.5"/>
    </svg>
  )
  if (type === 'middleV') return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" style={s}>
      <rect x="0.5" y="6.25" width="13" height="1.5"/>
      <rect x="2" y="2" width="3" height="10" rx="0.5"/>
      <rect x="9" y="3.5" width="3" height="7" rx="0.5"/>
    </svg>
  )
  if (type === 'bottom') return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" style={s}>
      <rect x="0.5" y="12" width="13" height="1.5"/>
      <rect x="2" y="3" width="3" height="8" rx="0.5"/>
      <rect x="9" y="6" width="3" height="5" rx="0.5"/>
    </svg>
  )
  if (type === 'distV') return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" style={s}>
      <rect x="0.5" y="0.5" width="13" height="1.5"/>
      <rect x="0.5" y="12" width="13" height="1.5"/>
      <rect x="2.5" y="5.5" width="9" height="3" rx="0.5"/>
    </svg>
  )
  return null
}

function AlignPanel({ selectedIds, widgets, onUpdateMany }) {
  const sel = widgets.filter(w => selectedIds.includes(w.id))
  const canDistribute = sel.length >= 3

  const alignLeft = () => {
    const minX = Math.min(...sel.map(w => w.x))
    onUpdateMany(prev => prev.map(w => selectedIds.includes(w.id) ? { ...w, x: minX } : w))
  }
  const alignCenterH = () => {
    const midX = (Math.min(...sel.map(w => w.x)) + Math.max(...sel.map(w => w.x + w.w))) / 2
    onUpdateMany(prev => prev.map(w => selectedIds.includes(w.id) ? { ...w, x: Math.round(midX - w.w / 2) } : w))
  }
  const alignRight = () => {
    const maxX = Math.max(...sel.map(w => w.x + w.w))
    onUpdateMany(prev => prev.map(w => selectedIds.includes(w.id) ? { ...w, x: maxX - w.w } : w))
  }
  const alignTop = () => {
    const minY = Math.min(...sel.map(w => w.y))
    onUpdateMany(prev => prev.map(w => selectedIds.includes(w.id) ? { ...w, y: minY } : w))
  }
  const alignMiddleV = () => {
    const midY = (Math.min(...sel.map(w => w.y)) + Math.max(...sel.map(w => w.y + w.h))) / 2
    onUpdateMany(prev => prev.map(w => selectedIds.includes(w.id) ? { ...w, y: Math.round(midY - w.h / 2) } : w))
  }
  const alignBottom = () => {
    const maxY = Math.max(...sel.map(w => w.y + w.h))
    onUpdateMany(prev => prev.map(w => selectedIds.includes(w.id) ? { ...w, y: maxY - w.h } : w))
  }
  const distributeH = () => {
    if (!canDistribute) return
    const sorted = [...sel].sort((a, b) => a.x - b.x)
    const span = sorted.at(-1).x + sorted.at(-1).w - sorted[0].x
    const g = (span - sorted.reduce((s, w) => s + w.w, 0)) / (sorted.length - 1)
    let cursor = sorted[0].x + sorted[0].w + g
    const updates = {}
    for (let i = 1; i < sorted.length - 1; i++) {
      updates[sorted[i].id] = Math.round(cursor)
      cursor += sorted[i].w + g
    }
    onUpdateMany(prev => prev.map(w => w.id in updates ? { ...w, x: updates[w.id] } : w))
  }
  const distributeV = () => {
    if (!canDistribute) return
    const sorted = [...sel].sort((a, b) => a.y - b.y)
    const span = sorted.at(-1).y + sorted.at(-1).h - sorted[0].y
    const g = (span - sorted.reduce((s, w) => s + w.h, 0)) / (sorted.length - 1)
    let cursor = sorted[0].y + sorted[0].h + g
    const updates = {}
    for (let i = 1; i < sorted.length - 1; i++) {
      updates[sorted[i].id] = Math.round(cursor)
      cursor += sorted[i].h + g
    }
    onUpdateMany(prev => prev.map(w => w.id in updates ? { ...w, y: updates[w.id] } : w))
  }

  return (
    <div className="properties-panel">
      <h3>{sel.length} 個選択中</h3>

      <div className="prop-section">
        <label>横方向</label>
        <div className="align-buttons">
          <button className="align-btn" onClick={alignLeft} title="左揃え">
            <AlignIcon type="left" />
          </button>
          <button className="align-btn" onClick={alignCenterH} title="中央揃え（横）">
            <AlignIcon type="centerH" />
          </button>
          <button className="align-btn" onClick={alignRight} title="右揃え">
            <AlignIcon type="right" />
          </button>
          <button className="align-btn" onClick={distributeH} title="等間隔（横）" disabled={!canDistribute}>
            <AlignIcon type="distH" />
          </button>
        </div>
      </div>

      <div className="prop-section">
        <label>縦方向</label>
        <div className="align-buttons">
          <button className="align-btn" onClick={alignTop} title="上揃え">
            <AlignIcon type="top" />
          </button>
          <button className="align-btn" onClick={alignMiddleV} title="中央揃え（縦）">
            <AlignIcon type="middleV" />
          </button>
          <button className="align-btn" onClick={alignBottom} title="下揃え">
            <AlignIcon type="bottom" />
          </button>
          <button className="align-btn" onClick={distributeV} title="等間隔（縦）" disabled={!canDistribute}>
            <AlignIcon type="distV" />
          </button>
        </div>
      </div>

      <p className="align-hint">Delete で一括削除 / Esc で選択解除</p>
    </div>
  )
}

export default function Properties({ widget, selectedIds, widgets, pageCount = 1, onUpdate, onUpdateMany, onDelete }) {
  if (selectedIds.length > 1) {
    return (
      <AlignPanel
        selectedIds={selectedIds}
        widgets={widgets}
        onUpdateMany={onUpdateMany}
      />
    )
  }

  if (!widget) {
    return (
      <div className="properties-panel">
        <h3>プロパティ</h3>
        <p className="no-selection">ウィジェットを選択してください</p>
        <p className="no-selection" style={{ marginTop: 4 }}>Cmd+A で全選択</p>
      </div>
    )
  }

  const field = (label, key, type = 'text') => (
    <div className="prop-field">
      <label>{label}</label>
      {type === 'number' ? (
        <input
          type="number"
          value={widget[key]}
          onChange={(e) => onUpdate(widget.id, { [key]: parseInt(e.target.value, 10) || 0 })}
        />
      ) : (
        <input
          type="text"
          value={widget[key] ?? ''}
          onChange={(e) => onUpdate(widget.id, { [key]: e.target.value })}
        />
      )}
    </div>
  )

  const navMode = widget.nav_mode ?? 'goto'

  return (
    <div className="properties-panel">
      <h3>{widget.type}</h3>
      {field('Label', 'label')}
      {widget.type !== 'PageButton' && field('OSC Address', 'osc_addr')}
      {widget.type === 'PageButton' && (
        <>
          <div className="prop-field">
            <label>ナビゲーション</label>
            <div className="nav-mode-group">
              <button
                className={`nav-mode-btn ${navMode === 'prev' ? 'active' : ''}`}
                onClick={() => onUpdate(widget.id, { nav_mode: 'prev' })}
              >← 前</button>
              <button
                className={`nav-mode-btn ${navMode === 'next' ? 'active' : ''}`}
                onClick={() => onUpdate(widget.id, { nav_mode: 'next' })}
              >次 →</button>
              <button
                className={`nav-mode-btn ${navMode === 'goto' ? 'active' : ''}`}
                onClick={() => onUpdate(widget.id, { nav_mode: 'goto' })}
              ># ページ</button>
            </div>
          </div>
          {navMode === 'goto' && (
            <div className="prop-field">
              <label>移動先ページ (0〜{pageCount - 1})</label>
              <input
                type="number"
                min={0}
                max={pageCount - 1}
                value={widget.target_page ?? 1}
                onChange={(e) => {
                  const v = Math.max(0, Math.min(pageCount - 1, parseInt(e.target.value, 10) || 0))
                  onUpdate(widget.id, { target_page: v })
                }}
              />
            </div>
          )}
        </>
      )}
      <div className="prop-section">
        <label>位置 / サイズ</label>
        <div className="pos-grid">
          {field('X', 'x', 'number')}
          {field('Y', 'y', 'number')}
          {field('W', 'w', 'number')}
          {field('H', 'h', 'number')}
        </div>
      </div>

      {(widget.type === 'Slider' || widget.type === 'HSlider') && field('Default Value', 'default', 'number')}

      {widget.type === 'HSVPicker' && (
        <div className="prop-section">
          <label>初期値 (R, G, B)</label>
          <div className="rgb-defaults">
            {['R', 'G', 'B'].map((ch, i) => (
              <input
                key={ch}
                type="number"
                min={0}
                max={255}
                value={widget.default?.[i] ?? 127}
                onChange={(e) => {
                  const vals = [...(widget.default || [127, 127, 127])]
                  vals[i] = Math.min(255, Math.max(0, parseInt(e.target.value, 10) || 0))
                  onUpdate(widget.id, { default: vals })
                }}
              />
            ))}
          </div>
          <div className="color-picker-row">
            <label>カラーピッカー</label>
            <input
              type="color"
              className="color-picker-input"
              value={rgbToHex(widget.default || [127, 127, 127])}
              onChange={(e) => onUpdate(widget.id, { default: hexToRgb(e.target.value) })}
            />
          </div>
        </div>
      )}

      <button className="delete-btn" onClick={() => onDelete(widget.id)}>
        削除
      </button>
    </div>
  )
}
