import { collectUsedNames } from './uniqueNames'

/** Fallback swatch when widget.color is unset (matches editor CSS defaults). */
const DEFAULT_COLOR_BY_TYPE = {
  Button: '#3a5080',
  Toggle: '#1a5c42',
  PageButton: '#1e3a2e',
  Slider: '#64b4ff',
  HSlider: '#64b4ff',
}

const DEFAULT_TOGGLE_ON = '#1a5c42'
const DEFAULT_TOGGLE_OFF = '#2a3038'

function darkenHexPreview(hex, amount = 35) {
  if (!hex || typeof hex !== 'string') return hex
  const s = hex.startsWith('#') ? hex.slice(1) : hex
  if (s.length !== 6) return hex
  const n = Number.parseInt(s, 16)
  if (Number.isNaN(n)) return hex
  const clamp = (v) => Math.max(0, Math.min(255, v))
  const r = clamp(((n >> 16) & 255) - amount)
  const g = clamp(((n >> 8) & 255) - amount)
  const b = clamp((n & 255) - amount)
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`
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

export default function Properties({ widget, selectedIds, widgets, pages = [], pageCount = 1, onUpdate, onUpdateMany, onDelete }) {
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

  const used = collectUsedNames(pages, widget.id)
  const labelDup = (widget.label || '').trim() !== '' && used.labels.has((widget.label || '').trim())
  const oscDup = widget.type !== 'PageButton'
    && (widget.osc_addr || '').trim() !== ''
    && used.oscAddrs.has((widget.osc_addr || '').trim())

  const field = (label, key, type = 'text', opts = {}) => (
    <div className={`prop-field${opts.dup ? ' prop-field-dup' : ''}`}>
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
          aria-invalid={opts.dup || undefined}
        />
      )}
      {opts.dup && <p className="prop-dup-hint">他のウィジェットと重複しています（全ページ共通）</p>}
    </div>
  )

  const navMode = widget.nav_mode ?? 'goto'

  return (
    <div className="properties-panel">
      <h3>{widget.type}</h3>
      {field('Label', 'label', 'text', { dup: labelDup })}
      {widget.type !== 'PageButton' && field('OSC Address', 'osc_addr', 'text', { dup: oscDup })}
      {widget.type === 'Toggle' ? (
        <>
          <div className="prop-field">
            <label>Color ON</label>
            <div className="color-row">
              <input
                type="color"
                className="color-input"
                value={widget.color_on || widget.color || DEFAULT_TOGGLE_ON}
                onChange={(e) => {
                  const patch = { color_on: e.target.value, color: null }
                  if (!widget.color_off && widget.color) {
                    patch.color_off = darkenHexPreview(widget.color)
                  }
                  onUpdate(widget.id, patch)
                }}
                title="ON 時の色"
              />
              <span className="color-hex">
                {widget.color_on || (widget.color ? `${widget.color} (旧)` : 'デフォルト')}
              </span>
              <button
                type="button"
                className="color-reset-btn"
                disabled={!widget.color_on && !widget.color}
                onClick={() => onUpdate(widget.id, { color_on: null, color: null })}
                title="標準色に戻す"
              >デフォルト</button>
            </div>
          </div>
          <div className="prop-field">
            <label>Color OFF</label>
            <div className="color-row">
              <input
                type="color"
                className="color-input"
                value={
                  widget.color_off
                  || (widget.color ? darkenHexPreview(widget.color) : DEFAULT_TOGGLE_OFF)
                }
                onChange={(e) => {
                  const patch = { color_off: e.target.value, color: null }
                  if (!widget.color_on && widget.color) {
                    patch.color_on = widget.color
                  }
                  onUpdate(widget.id, patch)
                }}
                title="OFF 時の色"
              />
              <span className="color-hex">
                {widget.color_off || (widget.color ? '自動 (旧)' : 'デフォルト')}
              </span>
              <button
                type="button"
                className="color-reset-btn"
                disabled={!widget.color_off}
                onClick={() => onUpdate(widget.id, { color_off: null })}
                title="標準色に戻す"
              >デフォルト</button>
            </div>
          </div>
        </>
      ) : (
        <div className="prop-field">
          <label>Color</label>
          <div className="color-row">
            <input
              type="color"
              className="color-input"
              value={widget.color || DEFAULT_COLOR_BY_TYPE[widget.type] || '#3a5080'}
              onChange={(e) => onUpdate(widget.id, { color: e.target.value })}
              title="ウィジェット色"
            />
            <span className="color-hex">
              {widget.color || 'デフォルト'}
            </span>
            <button
              type="button"
              className="color-reset-btn"
              disabled={!widget.color}
              onClick={() => onUpdate(widget.id, { color: null })}
              title="タイプ標準色に戻す"
            >デフォルト</button>
          </div>
        </div>
      )}
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

      {widget.type === 'Toggle' && (
        <div className="prop-field">
          <label>初期状態 / プレビュー</label>
          <div className="nav-mode-group">
            <button
              className={`nav-mode-btn ${!widget.default ? 'active' : ''}`}
              onClick={() => onUpdate(widget.id, { default: 0 })}
            >OFF</button>
            <button
              className={`nav-mode-btn ${widget.default ? 'active' : ''}`}
              onClick={() => onUpdate(widget.id, { default: 1 })}
            >ON</button>
          </div>
          <p className="prop-hint">キャンバスでダブルクリックしても切替できます</p>
        </div>
      )}

      <button className="delete-btn" onClick={() => onDelete(widget.id)}>
        削除
      </button>
    </div>
  )
}
