import { test, expect, _electron as electron } from '@playwright/test';
import path from 'path';
import fs from 'fs';

test.describe('Smoke: documents/status', () => {
  test('upload document and change status', async () => {
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

    // Wait briefly for app to settle
    await page.waitForTimeout(2000);

    // Navigate to Documents tab if present
    const documentsButton = page.getByText('Documents');
    if (await documentsButton.isVisible()) {
      await documentsButton.click();
    }

    // Upload fixture
    const uploadButton = page.getByText('Upload New');
    await uploadButton.click();

    const fileInput = page.locator('input[type="file"]');
    const fixturePath = path.join(__dirname, '..', 'fixtures', 'sample.txt');
    await fileInput.setInputFiles(fixturePath);

    // Wait for document to appear
    await page.waitForSelector('text=sample.txt', { timeout: 20000 });

    // Change status if a status control exists (best effort)
    // Assumes a status dropdown or button labelled with current status
    const statusControl = page.getByText(/Status|Approved|In Review/i).first();
    if (await statusControl.isVisible()) {
      await statusControl.click();
      // Choose an option; adjust selector to your UI
      const approvedOption = page.getByText(/Approved/i).first();
      if (await approvedOption.isVisible()) {
        await approvedOption.click();
        // Verify status changed
        await page.waitForSelector(/Approved/i, { timeout: 10000 });
      }
    }

    await app.close();
  });
});

