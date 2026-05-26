const TYPE_ICONS = {
  Button:    '⬜',
  Slider:    '🎚️',
  HSlider:   '↔️',
  HSVPicker: '🎨',
  IPDisplay: '🌐',
}

export default function LayersPanel({ widgets, selectedIds, onSelect, onReorder }) {
  const reversed = [...widgets].reverse()

  return (
    <div className="layers-panel">
      <h3>レイヤー</h3>
      <div className="layers-list">
        {reversed.length === 0 && (
          <p className="layers-empty">ウィジェットなし</p>
        )}
        {reversed.map((w) => {
          const origIdx = widgets.findIndex(x => x.id === w.id)
          const isSelected = selectedIds.includes(w.id)
          const isTop    = origIdx === widgets.length - 1
          const isBottom = origIdx === 0
          return (
            <div
              key={w.id}
              className={`layer-item ${isSelected ? 'selected' : ''}`}
              onClick={(e) => onSelect(w.id, e.metaKey || e.ctrlKey)}
            >
              <span className="layer-icon">{TYPE_ICONS[w.type] || '□'}</span>
              <span className="layer-name">{w.label || w.type}</span>
              <div className="layer-actions">
                <button
                  className="layer-btn"
                  onClick={(e) => { e.stopPropagation(); onReorder(w.id, 'up') }}
                  disabled={isTop}
                  title="上へ（前面）"
                >▲</button>
                <button
                  className="layer-btn"
                  onClick={(e) => { e.stopPropagation(); onReorder(w.id, 'down') }}
                  disabled={isBottom}
                  title="下へ（背面）"
                >▼</button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
