// Use PLAYWRIGHT_MODULE to point to an existing Playwright installation.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs');
(async () => {
  const browser = await chromium.launch({headless:true, ...(process.env.CHROME_PATH ? {executablePath:process.env.CHROME_PATH} : {})});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1100}});
    const failures=[];
    page.on('pageerror',e=>failures.push(String(e)));
    await page.goto(process.env.BASE_URL || 'http://127.0.0.1:8010');
    await page.getByRole('heading',{name:'Certificate Admin',exact:true}).waitFor();
    await page.getByRole('button',{name:'Issue certificates',exact:true}).click();
    await page.getByRole('heading',{name:/Operation #/}).waitFor();
    if (!await page.getByRole('status').last().innerText().then(t=>t.includes('COMPLETED'))) throw Error('Issue operation not completed');
    await page.reload();
    await page.getByRole('cell',{name:'Alex Lee',exact:true}).waitFor();
    await page.getByRole('button',{name:'View',exact:true}).first().click();
    await page.getByRole('heading',{name:'Certificate detail',exact:true}).waitFor();
    await page.getByText('Australia/Sydney',{exact:false}).waitFor();
    await page.screenshot({path:'verification/browser-main.png',fullPage:true});
    const body=await page.locator('body').innerText();
    if(failures.length) throw Error(failures.join('\n'));
    fs.writeFileSync('verification/browser-main.txt',new Date().toISOString()+'\nPASS: browser issue, reload, detail; no page errors.\n'+body);
    console.log('PASS: browser issue, reload, detail; no page errors.');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1)});
