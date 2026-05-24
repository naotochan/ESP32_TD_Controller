export default function WidgetPanel({ onDrop }) {
  const templates = [
    { type: 'Button',    icon: '⬜', desc: 'トグルボタン' },
    { type: 'Slider',    icon: '🎚️', desc: '0-255 スライダー' },
    { type: 'RGBPicker', icon: '🎨', desc: 'R/G/B ピッカー' },
  ]

  const onDragStart = (e, type) => {
    e.dataTransfer.setData('widgetType', type)
    e.dataTransfer.effectAllowed = 'copy'
  }

  return (
    <div className="widget-panel">
      <h3>ウィジェット</h3>
      <p className="panel-hint">キャンバスにドラッグ</p>
      {templates.map(t => (
        <div
          key={t.type}
          className="template-item"
          draggable
          onDragStart={(e) => onDragStart(e, t.type)}
          onClick={() => onDrop(t.type)}
        >
          <span className="template-icon">{t.icon}</span>
          <div className="template-info">
            <strong>{t.type}</strong>
            <span>{t.desc}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
