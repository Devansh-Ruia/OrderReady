const {chromium} = require('C:/Users/super/AppData/Local/npm-cache/_npx/0b9ff77863cb6e9f/node_modules/playwright');
const fs = require('fs');
const assert = require('node:assert/strict');
const expect = locator => ({toBeDisabled: async () => assert(await locator.isDisabled()), toBeVisible: async () => locator.waitFor({state:'visible'})});
const path = require('path');
const source = 'Jordan Rivera, jordan@example.com. We need 30 shirts. S 10, M 10, L 5. Needed September 28';
const dir = path.join(process.cwd(), 'artifacts');
const pause = async page => {await page.waitForTimeout(400); await page.getByTestId('stStatusWidget').waitFor({state:'hidden'});};
async function tick(page, locator) {if(!await locator.isChecked()){await locator.focus();await locator.press('Space');await pause(page);}assert(await locator.isChecked());}
async function fill(page, label, value) {
  const input = page.getByRole('textbox', {name:label, exact:true});
  await input.fill(value); await input.press('Tab'); await pause(page);
}
async function align(page, top) {
  await page.locator('.st-key-review').evaluate((el, y) => {
    const main = document.querySelector('[data-testid="stMain"]');
    main.scrollTop += el.getBoundingClientRect().top - y;
    document.activeElement?.blur();
  }, top);
  await pause(page);
}
async function measurements(page) {
  return page.evaluate(() => {
    const review = document.querySelector('.st-key-review');
    const rect = el => {const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom}};
    const inputs = [...review.querySelectorAll('input')].filter(el => el.type==='text').map(el => {
      const root = el.closest('[data-testid="stTextInputRootElement"]');
      const cs = getComputedStyle(root);return {label:el.getAttribute('aria-label'),value:el.value,fontSize:getComputedStyle(el).fontSize,border:cs.border,background:cs.backgroundColor,box:rect(root)};
    });
    const messages = [...review.querySelectorAll('[data-testid="stAlert"], [data-testid="stCaptionContainer"]')].map(el=>({text:el.textContent,box:rect(el)}));
    const overflows = [...review.querySelectorAll('*')].filter(el=>el.getBoundingClientRect().width && (el.getBoundingClientRect().right>innerWidth+1 || el.getBoundingClientRect().left<0)).map(el=>({tag:el.tagName,text:el.textContent.slice(0,100)}));
    return {viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio,scale:visualViewport.scale},panel:rect(review),inputs,messages,documentOverflow:document.documentElement.scrollWidth>innerWidth,reviewOverflows:overflows};
  });
}
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const report={source,manual:{},mocked:{},browserErrors:[],externalRequests:[]};
 try {
  for (const phase of ['before','after']) {
    const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1,acceptDownloads:true});
    const page=await context.newPage();
    page.on('pageerror', e=>report.browserErrors.push(String(e)));
    page.on('request', r=>{if(!/^https?:\/\/localhost:85(02|03)/.test(r.url()) && !r.url().startsWith('data:'))report.externalRequests.push(r.url())});
    await page.goto('http://localhost:'+(phase==='before'?'8502':'8503'));
    await page.getByRole('heading',{name:'OrderReady',exact:true}).waitFor();
    await fill(page,'Customer message',source);
    await page.getByRole('button',{name:'Start manual entry',exact:true}).click();
    await page.getByRole('textbox',{name:'Size S',exact:true}).waitFor();
    for(const [label,value] of Object.entries({'Size S':'10','Size M':'10','Size L':'5',[phase==='before'?'Requested quantity':'Requested total']:'30','Deadline':'September 28'}))await fill(page,label,value);
    await expect(page.getByRole('button',{name:'Prepare intake ticket',exact:true})).toBeDisabled();
    await page.getByText('deadline is not a real date (YYYY-MM-DD)',{exact:true}).waitFor();
    const metrics={};
    for(const [device,width,height,top] of [['desktop',1440,900,70],['mobile',390,844,65]]) {
      await page.setViewportSize({width,height});await align(page,top);
      metrics[device]=await measurements(page);
      await page.screenshot({path:path.join(dir,`repair-matched-${phase}-${device}-${width}.png`)});
      if(device==='mobile') {
        await page.locator('.st-key-review').getByText('Size quantities',{exact:true}).first().evaluate(el=>{document.querySelector('[data-testid="stMain"]').scrollTop+=el.getBoundingClientRect().top-70;});
        await pause(page);await page.screenshot({path:path.join(dir,`repair-matched-${phase}-mobile-quantities.png`)});
      }
      if(phase==='after') {
        if(metrics[device].documentOverflow || metrics[device].reviewOverflows.length) throw Error('Overflow on '+device);
        for(const field of metrics[device].inputs) {
          if(field.fontSize!=='16px'||field.border!=='1px solid rgb(139, 129, 116)'||field.background!=='rgb(247, 244, 238)'||field.box.height!==40) throw Error('Unexpected input styling '+JSON.stringify(field));
        }
      }
    }
    report.manual[phase]=metrics;
    if(phase==='after') {
      await page.setViewportSize({width:1440,height:900}); await align(page,70);
      await page.getByRole('textbox',{name:'Customer name',exact:true}).focus();
      const order=[];
      for(let i=0;i<25;i++) {
        order.push(await page.evaluate(()=>({label:document.activeElement.getAttribute('aria-label'),tag:document.activeElement.tagName,text:document.activeElement.textContent})));
        if(order.at(-1).label==='I reviewed all fields and resolved the issues.')break;
        await page.keyboard.press('Tab');
      }
      assert.deepEqual(order.filter(x=>x.tag==='INPUT').map(x=>x.label),['Customer name','Email or phone','Size S','Size M','Size L','Requested total','Deadline','I reviewed all fields and resolved the issues.']);
      assert(order.some(x=>x.tag==='SUMMARY' && x.text.includes('View source details')));
      report.manual.tabOrder=order;
      await page.getByRole('textbox',{name:'Customer name',exact:true}).focus();
      await page.keyboard.press('Tab');await pause(page);
      report.manual.focus=await page.getByRole('textbox',{name:'Email or phone',exact:true}).evaluate(el=>({active:el===document.activeElement,border:getComputedStyle(el.closest('[data-testid="stTextInputRootElement"]')).border,shadow:getComputedStyle(el.closest('[data-testid="stTextInputRootElement"]')).boxShadow}));
      await page.screenshot({path:path.join(dir,'repair-keyboard-focus.png')});
      const ack=page.getByRole('checkbox',{name:'I reviewed all fields and resolved the issues.',exact:true});
      await tick(page,ack);
      await expect(page.getByRole('button',{name:'Prepare intake ticket',exact:true})).toBeDisabled();
      report.manual.invalidAcknowledgmentBlocked=true;
      if(await page.getByText('Customer wrote', {exact:false}).count())throw Error('Manual evidence was invented');
      await page.getByText('View source details',{exact:true}).click();
      await expect(page.locator('.st-key-review').getByText(source,{exact:true})).toBeVisible();
      report.manual.originalSourceAccessible=true;
    }
    await context.close();
  }
  const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1,acceptDownloads:true});
  const page=await context.newPage();
  page.on('pageerror',e=>report.browserErrors.push(String(e)));
  await page.goto('http://localhost:8503');
  await page.getByRole('heading',{name:'OrderReady',exact:true}).waitFor();
  await fill(page,'Customer message',source);
  await page.getByRole('button',{name:'Extract with AI',exact:true}).click();
  await page.getByText('AI proposal awaiting your review',{exact:true}).waitFor();
  await pause(page);
  const caption='Customer wrote "Needed September 28"';
  await expect(page.getByText(caption,{exact:true})).toBeVisible();
  const details=page.locator('.st-key-review').getByTestId('stExpander');
  assert.equal(await details.locator('details').getAttribute('open'),null);
  const summary=details.locator('summary');
  await summary.focus();await summary.press('Enter');await pause(page);
  const evidence=[source,'Jordan Rivera','jordan@example.com','S 10, M 10, L 5','Needed September 28','We need 30 shirts'];
  const actual=await details.locator('code').allTextContents();
  assert.deepEqual(actual,evidence);
  report.mocked={explicitlyMocked:true,deadlineCaption:await page.getByText(caption,{exact:true}).textContent(),evidence:actual,keyboardSourceDetails:true};
  await details.scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(dir,'repair-mocked-source-details.png')});
  await summary.click();await pause(page);
  for(const device of ['desktop','mobile']) {
    await page.setViewportSize(device==='desktop'?{width:1440,height:900}:{width:390,height:844});
    await align(page,device==='desktop'?70:65);
    await page.screenshot({path:path.join(dir,`repair-mocked-${device}.png`)});
    report.mocked[device]=await measurements(page);
    assert.equal(report.mocked[device].documentOverflow,false);
    assert.deepEqual(report.mocked[device].reviewOverflows,[]);
  }
  await page.setViewportSize({width:1440,height:900});
  const ack=page.getByRole('checkbox',{name:'I reviewed all fields and resolved the issues.',exact:true});
  await tick(page,ack);
  await expect(page.getByRole('button',{name:'Prepare intake ticket',exact:true})).toBeDisabled();
  report.mocked.acknowledgmentCannotBypassInvalidData=true;
  await fill(page,'Requested total','25');await fill(page,'Deadline','2099-09-28');
  await tick(page,ack);
  await expect(page.getByRole('button',{name:'Prepare intake ticket',exact:true})).toBeDisabled();
  report.mocked.unresolvedIssuesBlockCorrectFields=true;
  const issues=page.getByRole('checkbox',{name:/^Resolved/});
  const issueNames=await issues.evaluateAll(els=>els.map(el=>el.getAttribute('aria-label')));
  for(const name of issueNames)await tick(page,page.getByRole('checkbox',{name,exact:true}));
  assert.equal(await ack.isChecked(),false);
  report.mocked.issueResolutionInvalidatesAcknowledgment=true;
  await tick(page,ack);
  const prepare=page.getByRole('button',{name:'Prepare intake ticket',exact:true});
  assert.equal(await prepare.isEnabled(),true);await prepare.click();await pause(page);
  const download=page.getByRole('button',{name:'Download intake ticket',exact:true});
  await download.waitFor();
  const dl=page.waitForEvent('download');await download.click();const file=await dl;
  const ticketPath=path.join(dir,'repair-mocked-intake.txt');await file.saveAs(ticketPath);
  const ticket=fs.readFileSync(ticketPath,'utf8');
  const expected=['INTAKE TICKET','='.repeat(34),'Customer : Jordan Rivera','Contact  : jordan@example.com','Garment  : Heavyweight cotton tee','Print    : Front centre','Deadline : 2099-09-28','','Sizes','  S x 10','  M x 10','  L x 5','','TOTAL    : 25 shirts','','Reviewed by founder: yes','','Original inquiry:',source,'','Intake only \u2014 no pricing or artwork review.'].join('\n');
  assert.equal(ticket,expected);
  report.mocked.download={filename:file.suggestedFilename(),bytes:Buffer.byteLength(ticket),matchesExpectedTicket:true};
  for(const input of await page.locator('.st-key-review input[type=text]').all())assert.equal(await input.isDisabled(),true);
  await page.locator('.st-key-ticket').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(dir,'repair-prepared-ticket.png')});
  await page.getByRole('button',{name:'Edit intake',exact:true}).click();await pause(page);
  assert.equal(await ack.isChecked(),false);assert.equal(await download.count(),0);
  await fill(page,'Size L','6');
  await expect(prepare).toBeDisabled();assert.equal(await download.count(),0);
  report.mocked.editInvalidatesApprovalAndDownload=true;
  await fill(page,'Customer message','Changed inquiry with a new deadline');
  assert.equal(await ack.isDisabled(),true);
  await summary.click();await pause(page);
  assert.deepEqual(await details.locator('code').allTextContents(),evidence);
  report.mocked.staleDraftKeepsOriginalSourceAndEvidence=true;
  await page.setViewportSize({width:390,height:844});
  await details.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(dir,'repair-mocked-stale-source-mobile.png')});
  report.mocked.expandedMobile=await measurements(page);
  assert.equal(report.mocked.expandedMobile.documentOverflow,false);
  assert.deepEqual(report.mocked.expandedMobile.reviewOverflows,[]);
  assert.equal(await page.getByTestId('stException').count(),0);
  await context.close();
  fs.writeFileSync(path.join(dir,'repair-browser-verification.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({desktopHeightBefore:report.manual.before.desktop.panel.height,desktopHeightAfter:report.manual.after.desktop.panel.height,tabOrder:report.manual.tabOrder,focus:report.manual.focus,mockedDownload:report.mocked.download,browserErrors:report.browserErrors}));
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
