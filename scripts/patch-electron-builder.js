// Patch electron-builder to fix "Cannot use 'in' operator" bug
const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'node_modules', 'app-builder-lib', 'out', 'codeSign', 'windowsCodeSign.js');

if (!fs.existsSync(filePath)) {
  console.log('windowsCodeSign.js not found - skipping patch');
  process.exit(0);
}

let content = fs.readFileSync(filePath, 'utf8');

// Check if already patched
if (content.includes('configuration.cscInfo && "file" in configuration.cscInfo')) {
  console.log('electron-builder already patched');
  process.exit(0);
}

// Apply patch
const originalLine = 'const vmRequired = configuration.path.endsWith(".appx") || !("file" in configuration.cscInfo);';
const patchedLine = 'const vmRequired = configuration.path.endsWith(".appx") || !(configuration.cscInfo && "file" in configuration.cscInfo);';

if (content.includes(originalLine)) {
  content = content.replace(originalLine, patchedLine);
  fs.writeFileSync(filePath, content, 'utf8');
  console.log('Successfully patched electron-builder windowsCodeSign.js');
} else {
  console.log('WARNING: Could not find line to patch - electron-builder may have been updated');
}














