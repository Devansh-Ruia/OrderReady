const {chromium,expect}=require('C:/Users/super/AppData/Local/npm-cache/_npx/0b9ff77863cb6e9f/node_modules/playwright');
const fs=require('fs');
const path=require('path');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const context=await browser.newContext({viewport:{width:1350,height:940},hasTouch:true,acceptDownloads:true});
 const page=await context.newPage(); const errors=[];const requests=[];
 page.on('pageerror',e=>errors.push(String(e)));
 page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
 page.on('request',r=>{if(!r.url().startsWith('http://localhost:8501')&&!r.url().startsWith('ws://localhost:8501'))requests.push(r.url())});
 const dir=path.join(process.cwd(),'artifacts');
 try{
 await page.goto('http://localhost:8501');
 await page.getByRole('heading',{name:'OrderReady',exact:true}).waitFor();
 const source='Jordan Rivera, jordan@example.com. Please print crew-neck T-shirts with a front print. S 10, M 10, L 5. Needed by 2026-10-15.';
 await page.getByLabel('Customer message',{exact:true}).fill(source);
 await page.getByLabel('Customer message',{exact:true}).press('Tab');
 await page.getByRole('button',{name:'Start manual entry',exact:true}).click();
 await page.getByLabel('Customer name',{exact:true}).waitFor();
 const fields={'Customer name':'Jordan Rivera','Email or phone':'jordan@example.com','Size S':'10','Size M':'10','Size L':'5','Deadline':'2026-10-15'};
 for(const [label,value] of Object.entries(fields)){
   const input=page.getByRole('textbox',{name:label,exact:true});
   await input.fill(value);await input.press('Tab');await page.waitForTimeout(170);
 }
 const help=page.getByRole('button',{name:'Size help',exact:true});
 await help.focus();await page.keyboard.press('Space');
 const helpText=page.getByText('Enter every size. Use 0 when none are needed. A blank quantity stays unknown.',{exact:true});
 await helpText.waitFor({state:'visible'});await page.keyboard.press('Escape');await helpText.waitFor({state:'hidden'});
 const review=page.getByRole('checkbox',{name:'I reviewed all fields and resolved the issues.',exact:true});
 await review.focus();await page.keyboard.press('Space');
 await page.getByRole('button',{name:'Prepare intake ticket',exact:true}).click();
 const download=page.getByRole('button',{name:'Download intake ticket',exact:true});await download.waitFor();
 const downloadEvent=page.waitForEvent('download');await download.click();const file=await downloadEvent;
 const ticketPath=path.join(dir,'manual-intake.txt');await file.saveAs(ticketPath);
 const ticket=fs.readFileSync(ticketPath,'utf8');
 if(!ticket.includes('Jordan Rivera')||!ticket.includes(source))throw Error('Downloaded content does not retain customer and original inquiry');
 await page.locator('[data-testid="stMain"]').evaluate(e=>e.scrollTop=0);
 await page.screenshot({path:path.join(dir,'after-desktop-1350.png'),fullPage:true});
 const desktopOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 await page.setViewportSize({width:390,height:844});
 await help.scrollIntoViewIfNeeded();await help.tap();await helpText.waitFor({state:'visible'});await page.keyboard.press('Escape');await helpText.waitFor({state:'hidden'});
 await page.locator('[data-testid="stMain"]').evaluate(e=>e.scrollTop=0);await page.screenshot({path:path.join(dir,'after-mobile-390.png'),fullPage:true});
 const mobileOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 await page.setViewportSize({width:1350,height:940});await page.evaluate(()=>{document.body.style.zoom='2';scrollTo(0,0)});
 await page.locator('[data-testid="stMain"]').evaluate(e=>e.scrollTop=0);
 await page.screenshot({path:path.join(dir,'after-zoom-200.png'),fullPage:true});
 const zoomOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 const exceptions=await page.locator('[data-testid="stException"]').count();
 const result={keyboardHelpOpenEscape:true,touchHelpOpenEscape:true,keyboardAcknowledgment:true,downloadBytes:Buffer.byteLength(ticket),downloadFilename:file.suggestedFilename(),ticket,desktopOverflow,mobileOverflow,zoomOverflow,zoomMethod:'CSS zoom 2 at 1350x940',streamlitExceptions:exceptions,browserErrors:errors,externalRequests:requests};
 fs.writeFileSync(path.join(dir,'browser-verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
