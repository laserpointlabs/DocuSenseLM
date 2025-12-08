require('dotenv').config();

module.exports = {
  appId: "com.docusenselm.app",
  productName: "DocuSenseLM",
  directories: {
    output: "dist"
  },
  files: [
    "dist-electron/**/*",
    "dist/**/*",
    "config.yaml",
    "build/icon.png" 
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
    publisherName: "DocuSenseLM"
  },
  nsis: {
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

