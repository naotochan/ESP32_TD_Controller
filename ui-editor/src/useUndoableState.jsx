import { useReducer, useCallback, useEffect } from 'react'

const MAX_HISTORY = 50

function resolve(next, prev) {
  return typeof next === 'function' ? next(prev) : next
}

function trim(past) {
  return past.length > MAX_HISTORY ? past.slice(past.length - MAX_HISTORY) : past
}

/**
 * Pure reducer — history lives in state, not in refs mutated from a setState
 * updater (which StrictMode double-invokes, duplicating every entry).
 */
function reducer(state, action) {
  switch (action.type) {
    case 'set': {
      const value = resolve(action.next, state.value)
      if (value === state.value) return state
      return { value, past: trim([...state.past, state.value]), future: [] }
    }
    case 'setSilent': {
      const value = resolve(action.next, state.value)
      if (value === state.value) return state
      return { ...state, value }
    }
    // Commit a snapshot taken before a silent burst (e.g. a canvas drag)
    case 'pushToHistory':
      return { ...state, past: trim([...state.past, action.snapshot]), future: [] }
    case 'undo': {
      if (state.past.length === 0) return state
      return {
        value: state.past[state.past.length - 1],
        past: state.past.slice(0, -1),
        future: [...state.future, state.value],
      }
    }
    case 'redo': {
      if (state.future.length === 0) return state
      return {
        value: state.future[state.future.length - 1],
        past: [...state.past, state.value],
        future: state.future.slice(0, -1),
      }
    }
    default:
      return state
  }
}

export default function useUndoableState(initialValue) {
  const [state, dispatch] = useReducer(
    reducer,
    undefined,
    () => ({ value: initialValue, past: [], future: [] }),
  )

  const set = useCallback((next) => dispatch({ type: 'set', next }), [])
  const setSilent = useCallback((next) => dispatch({ type: 'setSilent', next }), [])
  const pushToHistory = useCallback((snapshot) => dispatch({ type: 'pushToHistory', snapshot }), [])
  const undo = useCallback(() => dispatch({ type: 'undo' }), [])
  const redo = useCallback(() => dispatch({ type: 'redo' }), [])

  useEffect(() => {
    const handler = (e) => {
      // Text fields keep their own native undo stack
      const t = e.target
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      const mod = e.ctrlKey || e.metaKey
      if (!mod || (e.key !== 'z' && e.key !== 'Z')) return
      e.preventDefault()
      if (e.shiftKey) redo()
      else undo()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [undo, redo])

  return {
    value: state.value,
    set,
    setSilent,
    pushToHistory,
    undo,
    redo,
    canUndo: state.past.length > 0,
    canRedo: state.future.length > 0,
  }
}
