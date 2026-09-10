import { expect, test, type Page } from '@playwright/test';

// A fresh account per test. Registration is open, so the suite makes its own
// rather than sharing the seeded one: the point of most of these is what an
// account that owns nothing sees, and a shared account owns whatever the last
// test left behind.
function uniqueEmail() {
  return `e2e-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

const PASSWORD = 'e2e-password';

async function register(page: Page, email: string) {
  await page.goto('/register');
  await page.locator('input[autocomplete="username"]').fill(email);
  await page.locator('input[autocomplete="new-password"]').fill(PASSWORD);
  await page.getByRole('button', { name: '建立帳號' }).click();
  // Straight into the dashboard: the account is usable the moment it exists.
  await expect(page).toHaveURL('/');
}

test('a new account signs up and lands on an empty fleet', async ({ page }) => {
  await register(page, uniqueEmail());

  // The seeded account has published firmware and this one must not see it.
  await expect(page.locator('.fw-group-card')).toHaveCount(0);
  await page.goto('/devices');
  await expect(page.getByText('還沒有註冊任何裝置')).toBeVisible();
});

test('a new account cannot publish until it sets a public key', async ({ page }) => {
  // The server holds no private key, so there is nothing an upload could be
  // verified against. Saying so up front beats filling the form in for a 400.
  await register(page, uniqueEmail());

  await expect(page.getByText('尚未設定')).toBeVisible();
  await expect(page.getByRole('button', { name: '要先設定簽章公鑰' })).toBeDisabled();
});

test('registering a device shows its secret once and lists it', async ({ page }) => {
  await register(page, uniqueEmail());
  await page.goto('/devices');

  await page.getByPlaceholder('裝置型號，例如 ESP32').fill('ESP32');
  await page.getByRole('button', { name: '註冊', exact: true }).click();

  // Both values, in the shape they go into config.json. This is the only time
  // the secret exists anywhere but that unit's flash.
  const block = page.locator('.dev-secret-block');
  await expect(block).toContainText('device_id');
  await expect(block).toContainText('device_secret');

  await expect(page.locator('.data-table tbody tr')).toHaveCount(1);
  // Never checked in, so its state is unknown rather than offline. By the badge
  // and not by the text: the version cell reads 未知 for the same reason.
  await expect(page.locator('.data-table tbody tr .badge-warning')).toHaveText('未知');
});

test('a registered device can be disabled and enabled again', async ({ page }) => {
  await register(page, uniqueEmail());
  await page.goto('/devices');
  await page.getByPlaceholder('裝置型號，例如 ESP32').fill('ESP32');
  await page.getByRole('button', { name: '註冊', exact: true }).click();
  await expect(page.locator('.data-table tbody tr')).toHaveCount(1);

  await page.getByRole('button', { name: '停用' }).click();

  // Disabled outranks online state: whatever the clock says, the server is
  // answering that unit 401 on its next poll.
  await expect(page.getByText('已停用')).toBeVisible();
  await page.getByRole('button', { name: '重新啟用' }).click();
  await expect(page.getByText('已停用')).toHaveCount(0);
});

test('signing out and back in keeps the account it belongs to', async ({ page }) => {
  const email = uniqueEmail();
  await register(page, email);

  await page.getByRole('button', { name: '登出' }).click();
  await expect(page).toHaveURL('/login');

  await page.locator('input[autocomplete="username"]').fill(email);
  await page.locator('input[autocomplete="current-password"]').fill(PASSWORD);
  await page.getByRole('button', { name: '登入', exact: true }).click();

  await expect(page).toHaveURL('/');
  await expect(page.getByText(email)).toBeVisible();
});
