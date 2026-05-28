import { useState, useRef, useEffect } from 'react'

export default function ExportButton({ pages, orientation = 'portrait', onLoad }) {
  const [status, setStatus] = useState('')
  const [devicePort, setDevicePort] = useState(null)  // null = サーバー未起動, '' = 未接続, '/dev/...' = 接続中
  const fileHandleRef = useRef(null)

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch('http://localhost:3737/status')
        const data = await res.json()
        setDevicePort(data.port || '')
      } catch {
        setDevicePort(null)
      }
    }
    poll()
    const id = setInterval(poll, 3000)
    return () => clearInterval(id)
  }, [])

  const showStatus = (msg) => {
    setStatus(msg)
    setTimeout(() => setStatus(''), 2000)
  }

  const buildJson = () => {
    const rotation = orientation === 'landscape' ? 1 : 0
    return { orientation, rotation, pages }
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
    const data = buildJson()
    setStatus('送信中...')
    try {
      const res = await fetch('http://localhost:3737/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      const msg = await res.text()
      showStatus(res.ok ? `✓ ${msg}` : `✗ ${msg}`)
    } catch {
      showStatus('✗ サーバー未起動 (start.sh)')
    }
  }

  const handleSaveJson = async () => {
    const json = JSON.stringify(buildJson(), null, 2)
    try {
      // 既存ハンドルがあればそのまま上書き
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

  const deviceLabel =
    devicePort === null ? '○ サーバー未起動' :
    devicePort === ''   ? '○ デバイス未接続' :
    `● ${devicePort.replace('/dev/cu.', '')}`

  const deviceClass =
    devicePort === null ? 'device-status offline' :
    devicePort === ''   ? 'device-status disconnected' :
    'device-status connected'

  return (
    <div className="export-group">
      <span className={deviceClass}>{deviceLabel}</span>
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
