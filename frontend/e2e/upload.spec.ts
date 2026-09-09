import { Buffer } from 'node:buffer';
import { expect, test, type Page } from '@playwright/test';
import { buildImage } from './image';

// Seeded by e2e/backend.sh, the only thing that creates an account: no route
// does.
const ADMIN = { username: 'admin', password: 'e2e-password' };

// A model and a binary of its own per test. The cases share one database, so a
// fixed pair would make the duplicate case depend on the publish case having
// run first, and a retry would re-run a publish into the 409 it is not about.
let sequence = 0;

function uniqueBuild() {
  sequence += 1;
  return { model: `E2E-${process.pid}-${sequence}`, image: buildImage(0x10 + sequence) };
}

async function login(page: Page) {
  await page.goto('/login');
  // By autocomplete rather than by label: the labels are not bound to the
  // inputs, and what they read is still being settled.
  await page.locator('input[autocomplete="username"]').fill(ADMIN.username);
  await page.locator('input[autocomplete="current-password"]').fill(ADMIN.password);
  await page.getByRole('button', { name: '登入', exact: true }).click();
  await expect(page).toHaveURL('/');
}

async function publish(
  page: Page,
  { model, version, filename, bytes }: {
    model: string;
    version: string;
    filename: string;
    bytes: Buffer;
  },
) {
  // By form field name, which is the half of the contract the backend reads.
  await page.locator('input[type="file"]').setInputFiles({
    name: filename,
    mimeType: 'application/octet-stream',
    buffer: bytes,
  });
  await page.locator('input[name="model"]').fill(model);
  await page.locator('input[name="version"]').fill(version);
  await page.getByRole('button', { name: '上傳並發布' }).click();
}

test('an admin publishes a firmware and finds it in the list', async ({ page }) => {
  const { model, image } = uniqueBuild();

  await login(page);
  await publish(page, { model, version: '1.0.0', filename: 'main.ino.bin', bytes: image });

  // A dropped bearer header lands on the 401 branch instead, which is the
  // whole of what makes this assertion worth writing. The notice names what
  // the server published rather than what was typed, so an upload stored under
  // anything else fails here rather than on the list below.
  await expect(page.locator('.alert-info')).toHaveText(`韌體已發布：${model} 1.0.0。`);

  // No reload: a successful publish refetches the list, so what shows up here
  // came back from the server rather than from what the form believes it sent.
  const group = page.locator('.fw-group-card').filter({ hasText: model });
  await expect(group.getByText('最新 v1.0.0')).toBeVisible();
});

test('a file that is not an image reports why, not its status code', async ({ page }) => {
  const { model } = uniqueBuild();

  await login(page);
  // Named .bin so the input's accept filter is not what rejects it.
  await publish(page, {
    model,
    version: '1.0.0',
    filename: 'notes.bin',
    bytes: Buffer.alloc(2048, 0x78),
  });

  // The positive assertion has to come first: it is what waits for the alert
  // to exist, and `not.toContainText` against a locator that never appears
  // passes on nothing.
  const alert = page.locator('.alert-error');
  await expect(alert).toContainText('Not an ESP32 image');
  await expect(alert).not.toContainText('HTTP 400');
});

test('re-uploading one binary under a second version names the first', async ({ page }) => {
  const { model, image } = uniqueBuild();

  await login(page);
  await publish(page, { model, version: '1.0.0', filename: 'main.ino.bin', bytes: image });
  await expect(page.locator('.alert-info')).toBeVisible();

  await publish(page, { model, version: '1.0.1', filename: 'main.ino.bin', bytes: image });

  const alert = page.locator('.alert-error');
  await expect(alert).toContainText('already uploaded as version 1.0.0');
  await expect(alert).not.toContainText('HTTP 409');
});
