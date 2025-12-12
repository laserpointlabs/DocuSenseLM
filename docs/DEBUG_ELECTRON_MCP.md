## Electron MCP Debugging Guide

This captures how we enabled the Electron MCP helper tools (window info, screenshots, send command, read logs) for troubleshooting via Chrome DevTools on port 9222.

### Prereqs
- Node/npm installed
- PowerShell shell (commands below assume PS)

### Install MCP helper
```powershell
npm install -g electron-mcp-server
```

### Generate and set screenshot key (required)
```powershell
# Generate 32-byte hex key
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# Example export for current shell (replace with your key)
$env:SCREENSHOT_ENCRYPTION_KEY="YOUR_32_BYTE_HEX_KEY"
```

### Allow the MCP server in Cursor
Add/ensure an entry in `.cursor/mcp.json`:
```json
{
  "name": "electron-mcp-server",
  "command": "npx",
  "args": ["-y", "electron-mcp-server"],
  "env": {
    "SCREENSHOT_ENCRYPTION_KEY": "YOUR_32_BYTE_HEX_KEY"
  }
}
```

### Start the app with remote debugging (simplest: `run-debug.ps1`)
Use the helper script to start both React and Electron with a fixed DevTools port. It will auto-generate a screenshot key for the session if one isn’t set.
```powershell
cd C:\Users\JohnDeHart\working\insightLM-LT
.\run-debug.ps1                  # defaults: port 9222, auto temp key if none
# or explicitly:
.\run-debug.ps1 -Port 9223 -ScreenshotKey "<your_hex_key>"
```

If you prefer manual commands:
```powershell
cd C:\Users\JohnDeHart\working\insightLM-LT
npm run dev:react
npm run dev:electron -- --remote-debugging-port=9222 --enable-logging
```

Verify the port:
```powershell
netstat -ano | findstr 9222
```
You should see `LISTENING` and the Electron PID. Logs should show:
- `DevTools listening on ws://127.0.0.1:9222/...`
- MCP discovery starting servers (workbook-rag, dashboard, manager; jupyter is extension-managed).

### Use the MCP tools
Available tools (via Cursor MCP):
- `get_electron_window_info` — enumerate windows/targets and DevTools port.
- `take_screenshot` — capture Electron window (optionally save to path).
- `send_command_to_electron` — `get_page_structure`, `click_by_text`, `fill_input`, `eval`, etc.
- `read_electron_logs` — fetch main/renderer/console logs.

When the app is up, `get_electron_window_info` should report `automationReady: true` and show the `localhost:5173` window plus the DevTools window.

### Security level (optional)
The package defaults to `BALANCED`. To force `DEVELOPMENT` (allow all function calls, disables sandbox/screenshot encryption):
- Patch `dist/security/config.js` in the installed module to return `SecurityLevel.DEVELOPMENT` from `getDefaultSecurityLevel()`, **or**
- Call `securityManager.setSecurityLevel('development')` inside the server bootstrap. (No env toggle is provided upstream.)

If you patch the default, future runs will start in development mode automatically.

### Quick restart checklist
1) Export `SCREENSHOT_ENCRYPTION_KEY` in the shell.
2) Run `npm run dev:react` (optional if already running).
3) Run `npm run dev:electron -- --remote-debugging-port=9222 --enable-logging`.
4) Run `get_electron_window_info` (MCP) to confirm targets.
5) Use `send_command_to_electron`, `take_screenshot`, or `read_electron_logs` to debug the UI.
