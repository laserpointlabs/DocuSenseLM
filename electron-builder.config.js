require('dotenv').config();

module.exports = {
  appId: "com.ndatool.lite",
  productName: process.env.APP_NAME || "NDA Tool Lite",
  directories: {
    output: "dist"
  },
  files: [
    "dist-electron/**/*",
    "dist/**/*",
    "config.yaml",
    "build/icon.png" 
  ],
  extraResources: [
    {
      from: "python/dist/server",
      to: "python/server"
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
      "nsis"
    ],
    publisherName: process.env.APP_NAME || "NDA Tool Lite"
  },
  nsis: {
    oneClick: false,
    perMachine: false,
    allowToChangeInstallationDirectory: true
  },
  linux: {
    target: "AppImage",
    icon: "build/icon.png",
    category: "Utility"
  },
  publish: {
    provider: "github",
    owner: "jdehart",
    repo: "ndaTool"
  }
};

