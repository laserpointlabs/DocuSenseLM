import { test, expect, _electron as electron } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import os from 'os';
import { execSync } from 'child_process';

const APP_PORT = 14242;
const APP_PATH = path.join(__dirname, '..', '..', 'release', 'win-unpacked', 'DocuSenseLM.exe');
const SAMPLE_PDF = path.join(__dirname, '..', '..', 'data', 'Distributor_Agreements', 'AAA Fire  Safety Equipment Company DA.pdf');

function killStragglers() {
  try { execSync('taskkill /IM DocuSenseLM.exe /F /T'); } catch {}
  try { execSync('taskkill /IM python.exe /F /T'); } catch {}
}

test.describe('Electron full E2E (no mocks)', () => {
  test.setTimeout(300_000);

  test('upload, process, and chat against real MCP/LLM', async ({}, testInfo) => {
    expect(fs.existsSync(APP_PATH)).toBeTruthy();
    expect(fs.existsSync(SAMPLE_PDF)).toBeTruthy();

    killStragglers();

    const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'docusense-e2e-'));

    let app;
    try {
      app = await electron.launch({
        executablePath: APP_PATH,
        args: [],
        env: {
          ...process.env,
          USER_DATA_DIR: userDataDir,
        },
      });

      const page = await app.firstWindow();

      // Wait for backend health
      await expect.poll(async () => {
        try {
          const res = await fetch(`http://127.0.0.1:${APP_PORT}/health`);
          if (res.ok) {
            const json = await res.json();
            return json.status;
          }
        } catch {
          return null;
        }
        return null;
      }, { timeout: 90_000, intervals: [2000] }).toBe('ok');

      // Go to Documents tab
      await page.getByRole('button', { name: 'Documents', exact: true }).click();

      // Click Upload New and use native file chooser
      const filename = path.basename(SAMPLE_PDF);
      const [fileChooser] = await Promise.all([
        page.waitForEvent('filechooser'),
        page.getByRole('button', { name: 'Upload New', exact: true }).click(),
      ]);
      await fileChooser.setFiles(SAMPLE_PDF);

      // Wait for row showing processed within the table
      const row = page.getByRole('row', { name: new RegExp(filename.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) });
      await expect(row).toBeVisible({ timeout: 150_000 });
      await expect(row.getByText('System: processed', { exact: false })).toBeVisible({ timeout: 150_000 });

      // Switch to Chat & Ask tab
      await page.getByRole('button', { name: 'Chat & Ask', exact: true }).click();

      // Ask a question
      const question = 'Summarize the uploaded distributor agreement and name the parties.';
      const chatInput = page.getByPlaceholder('Ask a question across all documents...');
      await chatInput.click();
      await chatInput.fill(question);
      await page.getByRole('button', { name: 'Send', exact: true }).click();

      // Wait for AI response and sources
      await expect(page.getByText('AI', { exact: false })).toBeVisible({ timeout: 150_000 });
      await expect(page.getByRole('button', { name: filename })).toBeVisible({ timeout: 150_000 });
    } catch (err) {
      if (testInfo) {
        try {
          const outDir = testInfo.outputDir || path.join(process.cwd(), 'test-output');
          await fs.promises.mkdir(outDir, { recursive: true });
          if (app) {
            const page = await app.firstWindow();
            await page.screenshot({ path: path.join(outDir, 'failure.png'), fullPage: true }).catch(() => {});
          }
        } catch {
          // ignore screenshot errors
        }
      }
      throw err;
    } finally {
      if (app) {
        await app.close().catch(() => {});
      }
      killStragglers();
    }
  });
});

