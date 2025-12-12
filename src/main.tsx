import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

console.log('✅ main.tsx: React module loaded and executing');

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element not found!');
}

console.log('✅ main.tsx: Root element found, creating React root');

const root = ReactDOM.createRoot(rootElement);
console.log('✅ main.tsx: React root created, rendering App');

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

console.log('✅ main.tsx: App rendered successfully');

