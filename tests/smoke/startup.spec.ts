import { test, expect, _electron as electron } from '@playwright/test';
import path from 'path';
import fs from 'fs';

test.describe('Smoke: startup', () => {
  // Cold-starts on Windows (especially after a fresh install / first run) can be slow.
  // Give this smoke test enough budget so it doesn't flake on slower machines.
  test.describe.configure({ timeout: 240_000 });

  test('backend becomes healthy (with OpenAI mocked)', async () => {
    const appPath = path.join(__dirname, '..', '..', 'release', 'win-unpacked', 'DocuSenseLM.exe');
    expect(fs.existsSync(appPath)).toBeTruthy();

    const app = await electron.launch({
      executablePath: appPath,
      args: []
    });

    const page = await app.firstWindow();

    // Mock OpenAI to avoid external calls
    await page.route('https://api.openai.com/**', async (route) => {
      const url = route.request().url();
      if (url.includes('/v1/embeddings')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ data: [{ embedding: Array(768).fill(0.01) }], model: 'mock-embedding' })
        });
      }
      if (url.includes('/v1/chat/completions')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            choices: [
              { message: { role: 'assistant', content: 'Mocked response for testing.' } }
            ],
            model: 'gpt-4o-mini'
          })
        });
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    });

    // Wait a moment for app to start
    await new Promise((r) => setTimeout(r, 2000));

    // Poll backend health from Node (not renderer) until ok or timeout
    const startedAt = Date.now();
    const deadline = startedAt + 180_000; // allow slow cold starts in CI/Windows
    let healthOk = false;
    while (Date.now() < deadline) {
      try {
        const res = await fetch('http://127.0.0.1:14242/health');
        if (res.ok) {
          const json = await res.json();
          if (json && json.status === 'ok') {
            healthOk = true;
            break;
          }
        }
      } catch {
        // ignore and retry
      }
      await new Promise((r) => setTimeout(r, 2000));
    }

    expect(healthOk).toBeTruthy();

    const msToHealth = Date.now() - startedAt;
    console.log(`[metric] smoke_startup_backend_health_ms=${msToHealth}`);
    // Guardrail: should not exceed 3 minutes (if it does, we consider startup "stuck" for MVP)
    expect(msToHealth).toBeLessThan(180_000);

    await app.close();
  });
});

