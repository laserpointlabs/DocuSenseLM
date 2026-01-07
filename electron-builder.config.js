require('dotenv').config();

module.exports = {
  appId: "com.docusenselm.app",
  productName: "DocuSenseLM",
  // Ensure Windows shows a sane name in Task Manager "Processes" list.
  // electron-builder uses package metadata for PE version strings; we force description here too.
  extraMetadata: {
    description: "DocuSenseLM",
  },
  directories: {
    output: "release"
  },
  files: [
    "dist-electron/**/*",
    "web-dist/**/*",
    "config.yaml",
    "build/icon.png" 
  ],
  extraResources: [
    {
      from: "python",
      to: "python",
      filter: [
        "**/*",
        "!**/__pycache__/**",
        "!**/build/**",
        "!**/dist/**",
        "!**/*.spec",
        "!**/hook-*.py"
      ]
    },
    {
      from: "config.default.yaml",
      to: "config.default.yaml"
    },
    {
      from: "prompts.default.yaml",
      to: "prompts.default.yaml"
    }
  ],
  mac: {
    category: "public.app-category.productivity",
    icon: "build/icon.icns",
    target: [
      "dmg",
      "zip"
    ],
    hardenedRuntime: true,
    gatekeeperAssess: false,
    entitlements: "build/entitlements.mac.plist",
    entitlementsInherit: "build/entitlements.mac.plist"
  },
  win: {
    icon: "build/icon.ico",
    target: [
      "nsis",
      "dir"
    ],
    artifactName: "DocuSenseLM-Setup-${version}.${ext}",
    sign: false, // disable signing to avoid winCodeSign download
    signingHashAlgorithms: []
  },
  nsis: {
    artifactName: "DocuSenseLM-Setup-${version}.${ext}",
    oneClick: false,
    perMachine: false,
    allowToChangeInstallationDirectory: true
  },
  linux: {
    target: "AppImage",
    category: "Utility"
  },
  publish: {
    provider: "github",
    owner: "laserpointlabs",
    repo: "DocuSenseLM"
  }
};

