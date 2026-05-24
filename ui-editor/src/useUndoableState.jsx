import { useState, useCallback, useRef, useEffect } from 'react'

const MAX_HISTORY = 50

export default function useUndoableState(initialValue) {
  const [value, setValue] = useState(initialValue)
  const pastRef = useRef([])
  const futureRef = useRef([])

  const setAndRecord = useCallback((next) => {
    setValue(prev => {
      if (typeof next === 'function') next = next(prev)
      pastRef.current.push(prev)
      if (pastRef.current.length > MAX_HISTORY) pastRef.current.shift()
      futureRef.current = []
      return next
    })
  }, [])

  const undo = useCallback(() => {
    setValue(prev => {
      if (pastRef.current.length === 0) return prev
      futureRef.current.push(prev)
      const previous = pastRef.current.pop()
      return previous
    })
  }, [])

  const redo = useCallback(() => {
    setValue(prev => {
      if (futureRef.current.length === 0) return prev
      pastRef.current.push(prev)
      const next = futureRef.current.pop()
      return next
    })
  }, [])

  useEffect(() => {
    const handler = (e) => {
      const mod = e.ctrlKey || e.metaKey
      if (mod && e.shiftKey && (e.key === 'z' || e.key === 'Z')) {
        e.preventDefault()
        redo()
      } else if (mod && (e.key === 'z' || e.key === 'Z')) {
        e.preventDefault()
        undo()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [undo, redo])

  const canUndo = pastRef.current.length > 0
  const canRedo = futureRef.current.length > 0

  return { value, set: setAndRecord, undo, redo, canUndo, canRedo }
}
