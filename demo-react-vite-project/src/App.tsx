import React from 'react'

export default function App() {
  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: '2rem', textAlign: 'center' }}>
      <h1 style={{ color: '#007acc' }}>CmdBuddy Demo App</h1>
      <p style={{ fontSize: '1.25rem', color: '#333' }}>
        React + Vite + TypeScript
      </p>
      <div style={{ display: 'inline-block', padding: '1rem 2rem', background: '#e6f7ff', border: '1px solid #91d5ff', borderRadius: '8px' }}>
        <strong>Status:</strong> The missing <code>dev</code> script was successfully diagnosed and repaired by <strong>CmdBuddy</strong>!
      </div>
    </div>
  )
}
