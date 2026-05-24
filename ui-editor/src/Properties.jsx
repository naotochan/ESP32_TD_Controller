export default function Properties({ widget, onUpdate, onDelete }) {
  if (!widget) {
    return (
      <div className="properties-panel">
        <h3>プロパティ</h3>
        <p className="no-selection">ウィジェットを選択してください</p>
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

      {widget.type === 'Slider' && field('Default Value', 'default', 'number')}
      {widget.type === 'RGBPicker' && (
        <div className="prop-section">
          <label>初期値 (R, G, B)</label>
          <div className="rgb-defaults">
            {['r', 'g', 'b'].map((ch, i) => (
              <input
                key={ch}
                type="number"
                min={0}
                max={255}
                value={widget.default?.[i] ?? 127}
                onChange={(e) => {
                  const vals = [...(widget.default || [127, 127, 127])]
                  vals[i] = parseInt(e.target.value, 10) || 0
                  onUpdate(widget.id, { default: vals })
                }}
              />
            ))}
          </div>
        </div>
      )}

      <button className="delete-btn" onClick={() => onDelete(widget.id)}>
        削除
      </button>
    </div>
  )
}
