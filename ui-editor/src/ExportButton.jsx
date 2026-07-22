import { useState, useRef, useEffect } from 'react'

const NEEDS_OSC = new Set(['Button', 'Toggle', 'Slider', 'HSlider', 'HSVPicker'])

/** Returns warning strings for layout issues (empty OSC, duplicates, bad PageButton targets). */
function validateLayout(pages) {
  const warnings = []
  const addrMap = new Map() // addr → [{page, label, type}]

  pages.forEach((pageWidgets, pageIdx) => {
    ;(pageWidgets || []).forEach((w) => {
      if (NEEDS_OSC.has(w.type)) {
        const addr = (w.osc_addr || '').trim()
        if (!addr) {
          warnings.push(`Page ${pageIdx + 1}: ${w.type}「${w.label || '?'}」の OSC アドレスが空です`)
        } else {
          if (!addrMap.has(addr)) addrMap.set(addr, [])
          addrMap.get(addr).push({ page: pageIdx + 1, label: w.label || w.type, type: w.type })
        }
      }
      if (w.type === 'PageButton' && (w.nav_mode || 'goto') === 'goto') {
        const target = w.target_page ?? 0
        if (target < 0 || target >= pages.length) {
          warnings.push(
            `Page ${pageIdx + 1}: PageButton「${w.label || '?'}」の target_page=${target} が範囲外 (0〜${pages.length - 1})`
          )
        }
      }
    })
  })

  for (const [addr, list] of addrMap) {
    if (list.length > 1) {
      const where = list.map((x) => `P${x.page}:${x.label}`).join(', ')
      warnings.push(`OSC アドレス重複「${addr}」: ${where}`)
    }
  }
  return warnings
}

export default function ExportButton({ pages, orientation = 'portrait', onLoad }) {
  const [status, setStatus] = useState('')
  // null = server down; object from /status when up
  const [deviceStatus, setDeviceStatus] = useState(null)
  const fileHandleRef = useRef(null)

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch('http://localhost:3737/status')
        const data = await res.json()
        setDeviceStatus(data)
      } catch {
        setDeviceStatus(null)
      }
    }
    poll()
    const id = setInterval(poll, 3000)
    return () => clearInterval(id)
  }, [])

  const showStatus = (msg, ms = 3000) => {
    setStatus(msg)
    setTimeout(() => setStatus(''), ms)
  }

  const buildJson = () => {
    const rotation = orientation === 'landscape' ? 1 : 0
    return { orientation, rotation, pages }
  }

  const confirmWarnings = (actionLabel) => {
    const warnings = validateLayout(pages)
    if (warnings.length === 0) return true
    return window.confirm(
      `レイアウトに問題があります:\n\n${warnings.join('\n')}\n\nこのまま${actionLabel}しますか？`
    )
  }

  const handleLoadJson = async () => {
    try {
      const [handle] = await window.showOpenFilePicker({
        types: [{ description: 'Layout JSON', accept: { 'application/json': ['.json'] } }],
      })
      fileHandleRef.current = handle
      const file = await handle.getFile()
      const text = await file.text()
      const data = JSON.parse(text)
      if (!data.pages) { showStatus('無効なファイルです'); return }
      onLoad(data)
      showStatus('読み込みました')
    } catch (e) {
      if (e.name !== 'AbortError') showStatus('読み込み失敗')
    }
  }

  const handleDeploy = async () => {
    if (!confirmWarnings('Deploy')) return

    if (deviceStatus?.ambiguous) {
      const ports = (deviceStatus.ports || []).join('\n  ')
      const ok = window.confirm(
        `複数のシリアルポートが見つかります (${deviceStatus.count}):\n  ${ports}\n\n` +
        `曖昧なため自動 Deploy は失敗する可能性があります。\n` +
        `余分な機器を外すか、CLI でポート指定してください。\n\n続行しますか？`
      )
      if (!ok) return
    }

    const data = buildJson()
    setStatus('送信中...')
    try {
      const res = await fetch('http://localhost:3737/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      const msg = await res.text()
      showStatus(res.ok ? `✓ ${msg}` : `✗ ${msg}`, 5000)
    } catch {
      showStatus('✗ サーバー未起動 (start.sh)')
    }
  }

  const handleSaveJson = async () => {
    if (!confirmWarnings('保存')) return
    const json = JSON.stringify(buildJson(), null, 2)
    try {
      let handle = fileHandleRef.current
      if (!handle) {
        handle = await window.showSaveFilePicker({
          suggestedName: 'layout.json',
          types: [{ description: 'Layout JSON', accept: { 'application/json': ['.json'] } }],
        })
        fileHandleRef.current = handle
      }
      const writable = await handle.createWritable()
      await writable.write(json)
      await writable.close()
      showStatus('保存しました')
    } catch (e) {
      if (e.name !== 'AbortError') showStatus('保存失敗')
    }
  }

  let deviceLabel = '○ サーバー未起動'
  let deviceClass = 'device-status offline'
  if (deviceStatus) {
    const count = deviceStatus.count ?? 0
    const port = deviceStatus.port || ''
    if (count === 0) {
      deviceLabel = '○ デバイス未接続'
      deviceClass = 'device-status disconnected'
    } else if (deviceStatus.ambiguous) {
      deviceLabel = `⚠ ${count} ports`
      deviceClass = 'device-status ambiguous'
    } else {
      const short = port.replace(/^\/dev\/(cu\.)?/, '')
      deviceLabel = count > 1 ? `● ${short} (${count})` : `● ${short}`
      deviceClass = 'device-status connected'
    }
  }

  return (
    <div className="export-group">
      <span className={deviceClass} title={
        deviceStatus?.ports?.length
          ? deviceStatus.ports.join('\n')
          : undefined
      }>{deviceLabel}</span>
      <div className="export-sep" />
      <button className="export-btn deploy" onClick={handleDeploy}>
        📡 Deploy
      </button>
      <div className="export-sep" />
      <button className="export-btn secondary" onClick={handleLoadJson}>
        📂 開く
      </button>
      <button className="export-btn secondary" onClick={handleSaveJson}>
        💾 保存
      </button>
      {status && <span className="export-status">{status}</span>}
    </div>
  )
}
