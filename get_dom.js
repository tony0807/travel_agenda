const playwright = require('playwright');
(async () => {
  const browser = await playwright.chromium.launch();
  const context = await browser.newContext(playwright.devices['iPhone 12']);
  const page = await context.newPage();
  await page.goto('https://travelagenda.streamlit.app/');
  await page.waitForTimeout(10000);
  const dom = await page.content();
  console.log(dom.length);
  const fs = require('fs');
  fs.writeFileSync('dom.html', dom);
  await browser.close();
})();
