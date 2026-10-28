import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../../',import.meta.url));
const temp=await mkdtemp(join(tmpdir(),'kolhoz-ui-check-'));
const apiPort=Number(process.env.KOLHOZ_TEST_API_PORT||8017),webPort=Number(process.env.KOLHOZ_TEST_WEB_PORT||5187),debugPort=Number(process.env.KOLHOZ_TEST_CDP_PORT||9337);
const baseUrl=`http://127.0.0.1:${webPort}`;
process.env.NO_PROXY=[process.env.NO_PROXY,'127.0.0.1','localhost'].filter(Boolean).join(',');
const children=[];
function start(command,args,options={}){const child=spawn(command,args,{stdio:['ignore','pipe','pipe'],...options});children.push(child);child.stdout.on('data',()=>{});child.stderr.on('data',data=>{if(data.toString().includes('Address already in use'))process.stderr.write(data);});child.on('error',error=>console.error(error.message));return child;}
async function ready(url){for(let i=0;i<100;i++){try{if((await fetch(url)).ok)return;}catch{}await new Promise(resolve=>setTimeout(resolve,200));}throw new Error(`Не запустился сервис: ${url}. Проверьте свободные порты и установленный Chromium.`);}
try{
 start(join(root,'backend/venv/bin/python'),['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(apiPort)],{cwd:join(root,'backend'),env:{...process.env,KOLHOZ_DB_PATH:join(temp,'verification.sqlite')}});
 start(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(webPort),'--strictPort'],{cwd:join(root,'frontend'),env:{...process.env,KOLHOZ_BACKEND_PORT:String(apiPort)}});
 await ready(`http://127.0.0.1:${apiPort}/api/health`);await ready(baseUrl);
 start(process.env.KOLHOZ_CHROMIUM_PATH||'chromium',['--headless=new','--no-sandbox','--enable-unsafe-swiftshader',`--remote-debugging-port=${debugPort}`,`--user-data-dir=${join(temp,'browser')}`,'about:blank']);
 await ready(`http://127.0.0.1:${debugPort}/json/version`);
 const browser=await chromium.connectOverCDP(`http://127.0.0.1:${debugPort}`);
 for(const page of browser.contexts()[0]?.pages()||[])await page.close();
const context=await browser.newContext({viewport:{width:1536,height:1024}});const page=await context.newPage();const errors=[];
page.on('pageerror',e=>errors.push(e.message));
const nav=async label=>{await page.locator('.desktop-sidebar').getByRole('button',{name:label,exact:true}).click();};
const awaitPost=(path)=>page.waitForResponse(r=>r.url().includes(path)&&r.request().method()==='POST');
try{
await page.goto(baseUrl);await page.getByRole('button',{name:'Запустить сценарий',exact:true}).waitFor();await page.locator('.greenhouse-webgl canvas').waitFor();
await page.getByRole('button',{name:'Остановить вращение'}).click();await page.waitForTimeout(800);
const hero=await page.locator('.greenhouse-hero').boundingBox();assert(hero.width>850&&hero.height>400&&hero.height<460);
await page.screenshot({path:join(temp,'overview-3d.png')});
const canvas=page.locator('.greenhouse-webgl canvas');const hash=buffer=>createHash('sha256').update(buffer).digest('hex');const before=hash(await canvas.screenshot());await canvas.focus();await page.keyboard.press('ArrowRight');await page.waitForTimeout(400);assert.notEqual(before,hash(await canvas.screenshot()));
await page.getByRole('button',{name:'Вращать теплицу'}).click();await page.waitForTimeout(400);const rotation=hash(await canvas.screenshot());await page.waitForTimeout(700);assert.notEqual(rotation,hash(await canvas.screenshot()));await page.getByRole('button',{name:'Остановить вращение'}).click();
const anchor=page.locator('[data-anchor=zone] .scene-pin');const anchorBefore=await anchor.boundingBox();await canvas.focus();await page.keyboard.press('ArrowRight');await page.waitForTimeout(400);const anchorAfter=await anchor.boundingBox();assert(Math.abs(anchorBefore.x-anchorAfter.x)+Math.abs(anchorBefore.y-anchorAfter.y)>.1,'World anchor must move with the camera');
await page.getByRole('button',{name:'Оборудование',exact:true}).click();assert(await page.locator('.scene-anchor').count()===4);await page.getByRole('button',{name:'Без стекла',exact:true}).click();await page.getByRole('button',{name:/Вентиляция.*%/}).click();await page.locator('.scene-detail').waitFor();await page.getByRole('button',{name:'Закрыть сведения о модели'}).click();await page.screenshot({path:join(temp,'overview-equipment.png')});
await canvas.focus();for(let turn=0;turn<4;turn++){await page.keyboard.press('ArrowRight');await page.waitForTimeout(100);}const callouts=await page.locator('.scene-callout').evaluateAll(nodes=>nodes.filter(n=>getComputedStyle(n.parentElement).visibility==='visible').map(n=>n.getBoundingClientRect().toJSON()));for(let i=0;i<callouts.length;i++)for(let j=i+1;j<callouts.length;j++){const a=callouts[i],b=callouts[j];assert(!(a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top),'Equipment labels must not overlap');}
await page.getByLabel('Время на модели',{exact:true}).fill('20');assert((await page.locator('.scene-timeline label').innerText()).includes('Журнал'));await page.getByRole('button',{name:'Сейчас',exact:true}).click();await page.getByRole('button',{name:'Климат',exact:true}).click();console.log('3D: spatial labels, equipment, cutaway, journal timeline and keyboard rotation passed.');
await page.getByRole('button',{name:'Фото',exact:true}).click();await page.screenshot({path:join(temp,'overview-photo.png')});
await page.getByRole('button',{name:'План',exact:true}).click();assert(await page.locator('.greenhouse-plan svg').count()===1);
await page.getByRole('button',{name:'Фото',exact:true}).click();
await page.getByRole('button',{name:'Увеличить: Температура (уставка)',exact:true}).click();
let pending=awaitPost('/experiments/simulate');await page.getByRole('button',{name:'Запустить сценарий',exact:true}).click();const homeResult=await (await pending).json();assert(homeResult.id&&homeResult.parameters.heating_temp===22.5);console.log('Overview: dimensions, photo/3D/plan and scenario launch passed.');
await nav('Сценарии');await page.getByRole('button',{name:'Запустить моделирование',exact:true}).waitFor();
await page.getByRole('button',{name:'Сохранить вариант A'}).click();const modal=page.getByRole('dialog');await modal.getByLabel('Название',{exact:true}).fill('Проверка интерфейса');assert(await modal.getByLabel('Название',{exact:true}).evaluate(el=>el===document.activeElement));pending=awaitPost('/experiments/scenarios');await modal.getByRole('button',{name:'Сохранить',exact:true}).click();assert((await pending).ok());await modal.waitFor({state:'hidden'});
assert(await page.getByRole('button',{name:'Сохранить вариант A'}).evaluate(el=>el===document.activeElement));
pending=awaitPost('/experiments/simulate');await page.getByRole('button',{name:'Запустить моделирование',exact:true}).click();const result=await (await pending).json();assert(result.id);
await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.innerText.includes('Зафиксировать решение')&&!b.disabled));
await page.getByRole('button',{name:'Зафиксировать решение',exact:true}).click();await page.getByRole('dialog').getByLabel('Обоснование').fill('Сравнены климат и расходы.');pending=awaitPost('/reports/decisions');await page.getByRole('dialog').getByRole('button',{name:'Записать решение'}).click();assert((await pending).ok());console.log('Scenarios: save, model, compare and record decision passed.');
await nav('Отчёты');await page.getByRole('tab',{name:/Журнал решений/}).click();await page.getByText('Сравнены климат и расходы.',{exact:true}).waitFor();
await page.getByRole('tab',{name:/Эксперименты/}).click();await page.locator('.report-document').waitFor();await page.emulateMedia({media:'print'});await page.pdf({path:join(temp,'report.pdf'),format:'A4',printBackground:true});await page.emulateMedia({media:'screen'});console.log('Reports: saved experiments, decision details and printable PDF passed.');
await nav('Модель и данные');await page.getByRole('button',{name:'Выбрать файл',exact:true}).waitFor();
let rows=['timestamp,temp_air,humidity,co2,ppfd,heating_valve,outdoor_temp'];for(let i=0;i<36;i++)rows.push(`${new Date(Date.UTC(2026,9,10,9,10*i)).toISOString()},${22+i*.02},67,810,320,40,6`);
pending=awaitPost('/data/upload');await page.getByLabel('Загрузить CSV',{exact:true}).setInputFiles({name:'ui-measurements.csv',mimeType:'text/csv',buffer:Buffer.from(rows.join('\n'))});const quality=await (await pending).json();assert(quality.applied&&quality.valid_rows===36);
await page.getByRole('tab',{name:'Калибровка и прогноз'}).click();pending=awaitPost('/model/calibrate');await page.getByRole('button',{name:'Калибровать и проверить'}).click();const calibration=await (await pending).json();assert(calibration.train_rows===28&&calibration.test_rows===8);await page.getByText('Версия forecast-1',{exact:false}).waitFor();
await page.getByRole('tab',{name:'Версии модели'}).click();await page.getByRole('cell',{name:'forecast-1',exact:true}).waitFor();console.log('Data: CSV import, calibration and model history passed.');
await nav('Настройки');await page.getByLabel('Название теплицы',{exact:true}).fill('Теплица проверки');await page.getByLabel('Температура на обзорных графиках').selectOption('°F');pending=awaitPost('/settings/');await page.getByRole('button',{name:'Сохранить настройки'}).click();assert((await pending).ok());
await nav('Обзор');await page.getByRole('button',{name:'Фото',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.headline-metric')?.innerText.includes('°F'));assert((await page.locator('.app-header h1').innerText()).includes('Теплица проверки'));
await nav('Текущий климат');await page.getByRole('heading',{name:'Температура воздуха, °F',exact:true}).waitFor();await page.getByRole('checkbox',{name:'Прогноз',exact:true}).uncheck();assert(!(await page.locator('.chart-legend').first().innerText()).includes('Прогноз'));console.log('Settings/climate: persisted metadata, unit conversion and series filters passed.');
await nav('Экономика');await page.getByLabel('Тепло, ₽/МВт·ч',{exact:true}).fill('3000');pending=awaitPost('/economics/tariffs');await page.getByRole('button',{name:'Сохранить тарифы'}).click();assert((await pending).ok());
await page.getByRole('combobox',{name:'Период экономики'}).selectOption('quarter');await page.getByText('Расчётные затраты за квартал',{exact:true}).first().waitFor();const download=page.waitForEvent('download');await page.getByRole('button',{name:'Экспорт CSV'}).click();assert((await download).suggestedFilename()==='economics.csv');console.log('Economics: tariff edits, period and CSV export passed.');
await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Открыть меню'}).click();await page.getByRole('dialog').getByRole('button',{name:'Обзор',exact:true}).click();await page.getByRole('button',{name:'Фото',exact:true}).click();await page.screenshot({path:join(temp,'mobile.png')});assert(await page.locator('.workspace').evaluate(el=>el.scrollWidth<=el.clientWidth));
await page.getByRole('button',{name:'Открыть меню'}).click();await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});await page.waitForFunction(()=>document.querySelector('.mobile-menu-button')===document.activeElement);
await page.getByRole('button',{name:'3D',exact:true}).click();await page.locator('.greenhouse-webgl canvas').waitFor();await page.getByRole('button',{name:'Оборудование',exact:true}).click();await page.waitForTimeout(400);assert(await page.locator('.workspace').evaluate(el=>el.scrollWidth<=el.clientWidth));const mobileLabels=await page.locator('.scene-callout').evaluateAll(nodes=>nodes.filter(n=>getComputedStyle(n.parentElement).visibility==='visible').map(n=>n.getBoundingClientRect().toJSON()));const viewControls=await page.locator('.view-controls').boundingBox();for(const a of mobileLabels)assert(!(a.left<viewControls.x+viewControls.width&&a.right>viewControls.x&&a.top<viewControls.y+viewControls.height&&a.bottom>viewControls.y),'Mobile labels must not hide behind view controls');
await page.screenshot({path:join(temp,'mobile-3d.png')});
assert.deepEqual(errors,[]);console.log('Mobile, focus restoration and browser runtime: passed; no page errors.');
}finally{await context.close();await browser.close();}

 console.log(`Screenshots and PDF: ${temp}`);
}finally{
 for(const child of children)if(child.exitCode==null)child.kill('SIGTERM');
 await new Promise(resolve=>setTimeout(resolve,600));
 for(const child of children)if(child.exitCode==null)child.kill('SIGKILL');
 await rm(join(temp,'verification.sqlite'),{force:true});
 await rm(join(temp,'browser'),{recursive:true,force:true}).catch(()=>{});
}
