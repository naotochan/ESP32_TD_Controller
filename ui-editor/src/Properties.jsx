function rgbToHex([r, g, b]) {
  return '#' + [r, g, b].map(v => Math.min(255, Math.max(0, v)).toString(16).padStart(2, '0')).join('')
}

function hexToRgb(hex) {
  return [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16))
}

function AlignPanel({ selectedIds, widgets, onUpdateMany }) {
  const sel = widgets.filter(w => selectedIds.includes(w.id))

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

  // Fixed-gap arrangement: sort by position, then stack with specified gap
  const arrangeH = () => {
    const sorted = [...sel].sort((a, b) => a.x - b.x)
    const updates = {}
    let cursor = sorted[0].x
    for (const w of sorted) {
      updates[w.id] = cursor
      cursor += w.w + gap
    }
    onUpdateMany(prev => prev.map(w => w.id in updates ? { ...w, x: updates[w.id] } : w))
  }
  const arrangeV = () => {
    const sorted = [...sel].sort((a, b) => a.y - b.y)
    const updates = {}
    let cursor = sorted[0].y
    for (const w of sorted) {
      updates[w.id] = cursor
      cursor += w.h + gap
    }
    onUpdateMany(prev => prev.map(w => w.id in updates ? { ...w, y: updates[w.id] } : w))
  }

  return (
    <div className="properties-panel">
      <h3>{sel.length} 個選択中</h3>

      <div className="prop-section">
        <label>横方向</label>
        <div className="align-buttons">
          <button className="align-btn" onClick={alignLeft} title="左揃え">⇤</button>
          <button className="align-btn" onClick={alignCenterH} title="中央揃え（横）">⇔</button>
          <button className="align-btn" onClick={alignRight} title="右揃え">⇥</button>
          {sel.length >= 3 && (
            <button className="align-btn" onClick={distributeH} title="均等配置（横）">⟺</button>
          )}
        </div>
      </div>

      <div className="prop-section">
        <label>縦方向</label>
        <div className="align-buttons">
          <button className="align-btn" onClick={alignTop} title="上揃え">⇡</button>
          <button className="align-btn" onClick={alignMiddleV} title="中央揃え（縦）">⇕</button>
          <button className="align-btn" onClick={alignBottom} title="下揃え">⇣</button>
          {sel.length >= 3 && (
            <button className="align-btn" onClick={distributeV} title="均等配置（縦）">⟷</button>
          )}
        </div>
      </div>

      {sel.length >= 3 && (
        <div className="prop-section">
          <label>均等配置</label>
          <div className="align-buttons">
            <button className="align-btn arrange-btn" onClick={distributeH} title="横に均等配置">⟺ 横</button>
            <button className="align-btn arrange-btn" onClick={distributeV} title="縦に均等配置">⟷ 縦</button>
          </div>
        </div>
      )}

      <p className="align-hint">Delete で一括削除 / Esc で選択解除</p>
    </div>
  )
}

export default function Properties({ widget, selectedIds, widgets, onUpdate, onUpdateMany, onDelete }) {
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

  return (
    <div className="properties-panel">
      <h3>{widget.type}</h3>
      {field('Label', 'label')}
      {field('OSC Address', 'osc_addr')}
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
