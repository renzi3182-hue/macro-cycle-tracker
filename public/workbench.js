"use strict";
const privateMode = () => ["localhost","127.0.0.1"].includes(location.hostname);
let privateFunds = {};
async function loadPrivateFunds() {
  if (!privateMode()) return;
  try {
    const response = await fetch("/api/strumenti");
    if (response.ok) privateFunds = await response.json();
  } catch { /* Il catalogo pubblico funziona anche senza archivio locale. */ }
}
const durations = new Map();
const fmt = (n, digits=2) => n.toLocaleString("it-IT",{maximumFractionDigits:digits});
const day = iso => iso.slice(0,10).split("-").reverse().join("/");
const instrumentUrl = key => "/strumento?id=" + encodeURIComponent(key);
const catalogAssets = () => ({...DATA?.catalog?.assets, ...privateFunds});
const unit = asset => asset.currency || "USD";
const priceLabel = asset => asset.kind==="Fondo" ? "NAV di classe" : asset.currency ? "Quotazione caricata" : "Chiusura rettificata";
function maxMonths(asset) {
  if (!asset.maturity || !asset.history.length) return 480;
  const start=new Date(asset.history.at(-1)[0]+"T12:00:00Z"), end=new Date(asset.maturity+"T12:00:00Z");
  return Math.max(0, Math.min(480,(end.getUTCFullYear()-start.getUTCFullYear())*12+end.getUTCMonth()-start.getUTCMonth()-(end.getUTCDate()<start.getUTCDate()?1:0)));
}

function spark(history) {
  const values = history.slice(-60).map(row=>row[1]);
  const min=Math.min(...values), range=Math.max(...values)-min || 1;
  return '<svg class="spark" viewBox="0 0 220 42" preserveAspectRatio="none" aria-hidden="true"><polyline fill="none" stroke="currentColor" stroke-width="2" points="' +
    values.map((v,i)=> (i*220/Math.max(values.length-1,1))+','+(39-(v-min)*36/range)).join(' ')+'"/></svg>';
}

function marketPage(page,name) {
  const assets=catalogAssets(), key=params().get("id");
  page.innerHTML='<section class="desk"></section>';
  const desk=page.firstChild;
  if (name==="strumento" && key && assets[key]) return instrumentPage(desk,key,assets[key]);
  if (name==="panoramica") {
    const regions=[["USA","SPY"],["Europa · eurozona","EZU"],["Cina","MCHI"],["Emergenti","EEM"]];
    desk.innerHTML='<div class="mast"><p class="lbl">Macro Cycle Tracker</p><h1>Panoramica dei mercati</h1><p>Ultima seduta disponibile per i quattro mercati azionari.</p></div><div class="tiles">'+
      regions.map(([region,symbol])=>{
        const prices=assets[symbol]?.history || [], last=prices.at(-1), prev=prices.at(-2);
        if (!prev) return '<div class="tile">'+region+' · Serie indisponibile</div>';
        const change=100*(last[1]/prev[1]-1);
        return '<a class="tile" href="'+instrumentUrl(symbol)+'"><b>'+region+'</b><small>'+symbol+' · '+day(last[0])+'</small><span class="number">'+(change>=0?'+':'')+fmt(change)+'%</span>'+spark(prices)+'<small>Rispetto al '+day(prev[0])+'</small></a>';
      }).join("")+'</div>';
    const upcoming = (DATA?.catalog?.events || [])
      .filter(event => Date.parse(event.date) >= Date.now())
      .sort((a,b) => Date.parse(a.date) - Date.parse(b.date)).slice(0,3);
    desk.insertAdjacentHTML("beforeend", '<section class="panel"><h2>Prossimi eventi</h2>' +
      (upcoming.map(event => '<p>'+day(event.date)+' · '+esc(event.country)+' · '+esc(event.title)+'</p>').join("") ||
        '<p>Nessun evento futuro nei dati disponibili.</p>') +
      '<a href="/panoramica?vista=calendario">Apri il calendario</a></section>');
    return;
  }
  desk.insertAdjacentHTML("beforeend",'<div class="panel"><h2>Catalogo strumenti</h2><input aria-label="Cerca strumento" placeholder="Cerca per nome, ticker o ISIN"><div class="rows"></div></div>');
  const input=$("input",desk), list=$(".rows",desk);
  const rank = new Map((DATA?.asset_order || []).map((ticker, i) => [ticker, i]));
  function filter() {
    list.innerHTML=Object.entries(assets).sort(([a], [b]) => (rank.get(a) ?? Infinity) - (rank.get(b) ?? Infinity)).filter(([k,a])=>(k+" "+a.name).toLowerCase().includes(input.value.toLowerCase())).map(([k,a])=>
      '<a class="row" href="'+instrumentUrl(k)+'"><strong>'+esc(a.name)+'</strong><span>'+esc(a.kind)+' · '+esc(k)+' →</span></a>').join("") || "<p>Nessuno strumento disponibile.</p>";
  }
  input.oninput=filter; filter();
  if (name==="strumento" && privateMode()) importForm(desk);
}

function scenarioFigure(asset, months) {
  const history=asset.history.slice(-252), last=history.at(-1)[1], model=asset.model;
  const bounds=(m,z)=>last*Math.exp(model.drift*m+z*model.vol*Math.sqrt(m));
  const future=Array.from({length:61},(_,i)=>months*i/60);
  const all=history.map(r=>r[1]).concat(future.flatMap(m=>[bounds(m,-1.644854),bounds(m,1.644854)]));
  const low=Math.log(Math.min(...all)), span=Math.log(Math.max(...all))-low || 1;
  const y=v=>210-(Math.log(v)-low)*190/span;
  const x=i=>320+440*i/60;
  const line=(z)=>future.map((m,i)=>x(i)+','+y(bounds(m,z)));
  const past=history.map((r,i)=>(320*i/Math.max(history.length-1,1))+','+y(r[1]));
  const tested=model.checks.filter(([i])=>i+months<model.levels.length);
  const hits=tested.filter(([i,mu,vol])=>Math.abs(Math.log(model.levels[i+months]/model.levels[i])-mu*months)<=1.644854*vol*Math.sqrt(months)).length;
  const currency = esc(unit(asset));
  const minPrice = Math.min(...all), maxPrice = Math.max(...all);
  const roughStep = (maxPrice - minPrice) / 9 || minPrice / 10;
  const magnitude = 10 ** Math.floor(Math.log10(roughStep));
  const step = [1, 2, 2.5, 5, 10].find(n => n * magnitude >= roughStep) * magnitude;
  const candidates = [];
  if (span < Math.log(10)) {
    for (let i = Math.ceil(minPrice / step); i <= Math.floor(maxPrice / step); i++) candidates.push(i * step);
  } else {
    for (let power = Math.floor(Math.log10(minPrice)); power <= Math.ceil(Math.log10(maxPrice)); power++) {
      for (const factor of [1, 2, 5]) candidates.push(factor * 10 ** power);
    }
  }
  const levels = [];
  for (const value of candidates) {
    if (value >= minPrice && value <= maxPrice && Math.abs(y(value) - y(last)) > 13 &&
        (!levels.length || y(levels.at(-1)) - y(value) > 14)) levels.push(value);
  }
  const priceFormat = new Intl.NumberFormat("it-IT", {maximumSignificantDigits: 8});
  const dateFormat = new Intl.DateTimeFormat("it-IT", {month:"short", year:"2-digit", timeZone:"UTC"});
  const lastDate = new Date(history.at(-1)[0]);
  const ticks = [0, 0.5, 1].map(fraction => ({
    x: 320 * fraction,
    date: new Date(history[Math.round(fraction * (history.length - 1))][0])
  }));
  const divisions = Math.min(4, months);
  for (let i = 1; i <= divisions; i++) {
    const offset = Math.round(months * i / divisions);
    const date = new Date(lastDate);
    date.setUTCDate(1);
    date.setUTCMonth(date.getUTCMonth() + offset);
    ticks.push({x:320 + 440 * offset / months, date});
  }
  const timeGrid = ticks.map(t => `<line x1="${t.x}" x2="${t.x}" y1="0" y2="230" stroke="var(--line)" stroke-dasharray="2 3"/>`).join("");
  const timeAxis = ticks.map(t => `<span style="left:${100*t.x/760}%">${dateFormat.format(t.date)}</span>`).join("");
  const grid = levels.map(value => `<line x1="0" x2="760" y1="${y(value)}" y2="${y(value)}" stroke="var(--line)"/>`).join("");
  const label = (value, current = false) => `<span class="${current ? "last-price" : ""}" style="top:${100*y(value)/230}%">${priceFormat.format(value)}</span>`;
  return '<div class="price-chart"><svg class="figure" viewBox="0 0 760 230" preserveAspectRatio="none" role="img" aria-label="Storico e scenario a '+months+' mesi, prezzi in '+currency+', scala logaritmica">'+grid+timeGrid+
    `<line x1="0" x2="760" y1="${y(last)}" y2="${y(last)}" stroke="var(--accent)" stroke-dasharray="3 4"/>`+
    '<polygon fill="currentColor" opacity=".17" points="'+line(1.644854).concat(line(-1.644854).reverse()).join(' ')+'"/><polyline fill="none" stroke="var(--fg)" stroke-width="2" points="'+past.join(' ')+'"/><line x1="320" x2="320" y1="6" y2="218" stroke="var(--muted)" stroke-dasharray="3 4"/><polyline fill="none" stroke="currentColor" stroke-width="3" points="'+line(0).join(' ')+'"/></svg><div class="price-scale"><small>'+currency+'</small>'+levels.map(value => label(value)).join("")+label(last, true)+'</div><div class="time-scale">'+timeAxis+'</div></div>'+
    '<p><b>'+fmt(bounds(months,0))+' '+unit(asset)+'</b> al centro · fascia '+fmt(bounds(months,-1.644854))+' – '+fmt(bounds(months,1.644854))+' '+unit(asset)+'.</p>'+
    '<p class="meta">Scala logaritmica. Storico e proiezione hanno scale temporali distinte. Scenario a '+months+' mesi con media e volatilità costanti, stimate sugli ultimi 36 rendimenti mensili completi. La fascia teorica al 90% assume rendimenti logaritmici indipendenti e normali. Un cambio di regime può invalidare queste ipotesi.</p>'+
    '<p class="meta">'+(tested.length?'Verifica storica progressiva: '+hits+' esiti nella fascia su '+tested.length+' finestre sovrapposte a '+months+' mesi.':'Storico insufficiente per verificare la copertura a questa durata.')+'</p>';
}

function instrumentPage(desk,key,asset) {
  const h=asset.history,last=h.at(-1);
  desk.innerHTML='<div class="mast"><a href="/strumento">← Catalogo</a><h1>'+esc(asset.name)+'</h1><p>'+esc(asset.kind)+' · '+esc(key)+(last?' · '+priceLabel(asset)+' '+fmt(last[1])+' '+unit(asset)+' al '+day(last[0]):' · NAV di classe indisponibile')+'</p></div>';
  if (asset.cot) desk.insertAdjacentHTML("beforeend", '<section class="panel"><h2>Posizionamento COT</h2>'+'<p>COT · '+esc(asset.contract)+' · Non-commercial · Variazione settimanale della posizione netta '+fmt(asset.cot[1])+' punti di open interest. Rilevazione '+day(asset.cot[0])+'. Data effettiva di pubblicazione indisponibile. Peso nello scenario pari a zero.</p></section>');
  if (!last) return;
  const limit=maxMonths(asset);
  if (asset.maturity) desk.insertAdjacentHTML("beforeend",'<p>Rimborso previsto il '+day(asset.maturity)+'. Durate selezionabili fino all’ultimo mese intero prima del rimborso.</p>');
  if (!limit || !asset.model) {
    desk.insertAdjacentHTML("beforeend",'<div class="panel"><h2>Storico</h2>'+spark(h)+'<p>'+day(h[0][0])+' – '+day(last[0])+'. Scenario indisponibile per questa serie o scadenza.</p></div>');return;
  }
  const m=Math.min(limit,durations.get(key) || 12);
  desk.insertAdjacentHTML("beforeend",'<section class="panel"><h2>Storico e scenari</h2><div class="tools"><label>Durata in mesi <input type="number" min="1" step="1" max="'+limit+'" value="'+m+'"></label>'+[5,10,30,40].filter(n=>12*n<=limit).map(n=>'<button class="btn" data-years="'+n+'">'+n+' anni</button>').join('')+'</div><div id="scenario"></div></section>');
  const input=$("input",desk), result=$("#scenario",desk);
  function draw() {
    const n=input.valueAsNumber;
    if (!Number.isInteger(n)||n<1||n>limit) {result.textContent="Scegli una durata da 1 a "+limit+" mesi."; return;}
    durations.set(key,n);
    result.innerHTML=asset.model?'<p class="lbl">'+(n<=12?'Breve':n<=120?'Medio':'Lungo')+' termine · '+n+' mesi</p>'+scenarioFigure(asset,n):'Storico insufficiente per la stima.';
  }
  input.oninput=draw;
  desk.querySelectorAll("[data-years]").forEach(b=>b.onclick=()=>{input.value=12*Number(b.dataset.years);draw();}); draw();
  const prior=h.slice(-22,-2).map(r=>r[1]), prev=h.at(-2)?.[1];
  let reading="Nessuna rottura seguita da rientro rispetto alle 20 sedute precedenti.";
  if (prior.length===20 && ((prev>Math.max(...prior) || prev<Math.min(...prior)) && last[1]>=Math.min(...prior) && last[1]<=Math.max(...prior))) reading="Il prezzo è uscito dall’intervallo delle precedenti 20 sedute ed è rientrato nell’ultima seduta.";
  desk.insertAdjacentHTML("beforeend",'<section class="panel"><h2>Prezzi e posizionamento</h2><p>'+reading+' Volumi e flussi indisponibili per confermare accumulo o distribuzione.</p>'+
    '</section>');
  const events=(DATA.catalog.events || []).filter(e=>e.country===asset.country).slice(-5).reverse();
  desk.insertAdjacentHTML("beforeend",'<section class="panel"><h2>Calendario del mercato</h2>'+ (events.map(e=>'<div class="row"><div><strong>'+esc(e.title)+'</strong><p>'+day(e.date)+' · Forex Factory</p><small>Precedente '+esc(e.previous||"n.d.")+' · Atteso '+esc(e.forecast||"n.d.")+' · Pubblicato n.d.</small></div></div>').join('') || '<p>Nessun evento associato in cache.</p>')+'<p class="meta">La cache non contiene una misura della reazione alla pubblicazione.</p></section>');
}

let meeting=null;
async function clientApi(path,body) {
  const response=await fetch("/api/clienti"+path,body ? {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)} : {cache:"no-store"});
  if (response.status===503) throw Error((await response.json()).error);
  if (!response.ok) throw Error(response.status===409?"La scheda è cambiata. Riaprila prima di salvare.":"Operazione non riuscita. Verifica i dati e il server locale.");
  return path.endsWith("/report") ? response.blob() : response.json();
}

function newMeeting() {
  return {current:[],proposed:[],scenarios:{},goal:"",date:"",notes:""};
}

function meetingData(root) {
  const [current,proposed]=advice.portfolios().map(el=>advice.read(el));
  if (!current||!proposed) throw Error("Controlla gli importi delle posizioni.");
  const scenarios={};
  for (const check of root.querySelectorAll("[data-include]:checked")) {
    const months=root.querySelector('[data-months="'+check.dataset.include+'"]').valueAsNumber;
    if (!Number.isInteger(months)||months<1||months>maxMonths(catalogAssets()[check.dataset.include])) throw Error("Verifica la durata dello scenario e la scadenza dello strumento.");
    scenarios[check.dataset.include]=months;
  }
  const savings=$("#monthly-saving",root);
  if (!savings.validity.valid) throw Error("Inserisci un accantonamento mensile positivo o pari a zero, con al massimo due decimali.");
  const monthlySavingCents=savings.value==="" ? null : Math.round(savings.valueAsNumber*100);
  return {current,proposed,scenarios,goal:meeting.data.goal||"",date:meeting.data.date||"",monthlySavingCents,notes:$("#meeting-notes",root).value};
}

async function clientPage(page) {
  page.innerHTML='<section class="desk"><div class="mast"><p class="lbl">Consulenza privata</p><h1>Archivio clienti</h1><p>Ricerca per codice · Archivio su questo computer</p></div><div class="panel"><form class="tools"><input aria-label="Codice cliente" required maxlength="24" pattern="[A-Za-z0-9][A-Za-z0-9_\\-]{0,23}" placeholder="Codice cliente"><button class="btn">Apri o crea scheda</button></form><div class="rows"></div><p role="status"></p></div></section>';
  const form=$("form",page), input=$("input",form), list=$(".rows",page), status=$("[role=status]",page);
  try {
    const clients=await clientApi("");
    function filter() {
      const found=clients.filter(c=>c.code.includes(input.value.trim().toUpperCase()));
      list.replaceChildren();
      for (const c of found) {
        const b=document.createElement("button");
        b.type="button"; b.className="btn row"; b.textContent=c.code+" · Patrimonio "+advice.euros(c.total)+" · Liquidità "+advice.euros(c.cash);
        b.onclick=()=>openClient(c.code);list.append(b);
      }
      if (!found.length) list.textContent="Nessuna scheda trovata.";
    }
    async function openClient(code) {
      try {
        if (meeting?.code===code) return go("/consulenza");
        if (advice.root && (meeting?.dirty || (!meeting && advice.read(advice.portfolios()[0])?.length)) &&
            !confirm("Aprire un’altra scheda e lasciare le modifiche non salvate?")) return;
        let record=clients.some(c=>c.code===code)?await clientApi("/"+code):{revision:0,data:newMeeting()};
        if (!form.isConnected) return;
        meeting={code,...record,dirty:false}; advice.root=null; go("/consulenza");
      } catch(error) {status.textContent=error.message;}
    }
    form.onsubmit=e=>{e.preventDefault();openClient(input.value.trim().toUpperCase());};
    input.oninput=filter;filter();
  } catch(error) {status.textContent=error.message;}
}

function meetingTools(page) {
  if (!privateMode()) return;
  const root=advice.root;
  if ($(".meeting",root)) return;
  const section=document.createElement("section");section.className="meeting";
  root.firstElementChild.after(section);
  if (!meeting) {
    section.innerHTML='<a href="/clienti">Apri una scheda cliente per salvare il colloquio</a>';return;
  }
  const {code,data}=meeting;
  installClientOverview(root, code);
  root.append(section);
  const [current,proposed]=advice.portfolios();
  if (data.current.length) {current.replaceChildren();data.current.forEach(row=>advice.add(current,row));}
  if (data.proposed.length) {
    data.proposed.forEach(row=>advice.add(proposed,row)); proposed.hidden=false;
    $("#advice-empty",root).hidden=true;$("#advice-add-proposed",root).hidden=false;$("#advice-copy",root).hidden=true;
  }
  const savingBox=$("#advice-goal",root).closest(".box");
  savingBox.innerHTML='<h2>Accantonamento mensile</h2><div class="advice-fields"><label>Importo in euro al mese <input id="monthly-saving" type="number" min="0" max="1000000000000" step=".01" aria-describedby="saving-help"></label></div><p class="cap" id="saving-help">Quanto riesce a mettere da parte il cliente ogni mese mantenendo il suo stile di vita?</p>';
  $("#monthly-saving",root).value=data.monthlySavingCents==null ? "" : data.monthlySavingCents/100;
  advice.invalidate();
  section.innerHTML='<h2>Materiale per il colloquio</h2><details><summary>Strumenti e orizzonti del report</summary>'+
    Object.entries(catalogAssets()).filter(([,a])=>a.model && maxMonths(a)>0).map(([key,a])=>'<div class="tools"><label><input type="checkbox" data-include="'+key+'" '+(data.scenarios[key]?'checked':'')+'> '+esc(a.name)+'</label><label>Mesi <input type="number" min="1" max="'+maxMonths(a)+'" data-months="'+key+'" value="'+Math.min(maxMonths(a),data.scenarios[key]||durations.get(key)||12)+'"></label></div>').join('')+
    '</details><label>Punti da discutere<textarea id="meeting-notes" maxlength="400" rows="2"></textarea></label><div class="tools"><button class="btn" data-save>Salva scheda</button><button class="btn" data-report>Salva e scarica PowerPoint</button><a href="/clienti">Archivio clienti</a></div><small role="status"></small>';
  $("#meeting-notes",root).value=data.notes;
  root.addEventListener("input",()=>{meeting.dirty=true;});
  root.addEventListener("click",e=>{if(e.target.closest("#advice-current button,#advice-proposed button,#advice-reset,#advice-copy")) meeting.dirty=true;});
  async function save(report) {
    const selected=meeting,status=$("[role=status]",section),buttons=section.querySelectorAll("button");
    try {
      const content=meetingData(root);
      buttons.forEach(b=>b.disabled=true);
      const path="/"+selected.code;
      const saved=await clientApi(path,{revision:selected.revision,data:content});
      selected.revision=saved.revision; selected.data=content;
      selected.dirty=JSON.stringify(content)!==JSON.stringify(meetingData(root));
      status.textContent="Scheda salvata.";
      if (report) {
        const blob=await clientApi(path+"/report",{revision:saved.revision});
        const url=URL.createObjectURL(blob), a=document.createElement("a");
        a.href=url;a.download="Colloquio-"+selected.code+".pptx";a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
      }
    } catch(error) {status.textContent=error.message;} finally {buttons.forEach(b=>b.disabled=false);}
  }
  $("[data-save]",section).onclick=()=>save(false);$("[data-report]",section).onclick=()=>save(true);
}

function importForm(desk) {
  const panel=document.createElement("details");panel.className="panel meeting";
  panel.innerHTML='<summary>Aggiungi una serie privata</summary><form><div class="tools"><label>Tipo <select name="kind"><option>Azione</option><option>Fondo</option><option>Obbligazione</option><option>ETF</option></select></label><label>Ticker o ISIN <input name="key" required maxlength="24"></label><label>Nome e classe <input name="name" required maxlength="80"></label><label>Valuta <select name="currency">'+["EUR","USD","GBP","CHF","JPY"].map(c=>'<option>'+c+'</option>').join('')+'</select></label><label hidden>Scadenza <input type="date" name="maturity"></label></div><label>Storico · una riga per osservazione, data e valore separati da punto e virgola<textarea required name="series" placeholder="2026-09-30;100,25"></textarea></label><button class="btn">Importa nel catalogo privato</button><p role="status"></p></form>';
  desk.append(panel);
  const form=$('form',panel), maturity=form.elements.maturity;
  form.elements.kind.onchange=()=>{maturity.required=form.elements.kind.value==="Obbligazione";maturity.parentElement.hidden=!maturity.required;};
  form.onsubmit=async e=>{
    e.preventDefault();const status=$('[role=status]',form);
    try {
      const res=await fetch('/api/strumenti',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});
      if (!res.ok) throw Error(res.status===409?'Identificativo già presente.':'Controlla identificativo, valori, date e scadenza.');
      const {key}=await res.json();await loadPrivateFunds();go(instrumentUrl(key));
    } catch(error){status.textContent=error.message;}
  };
}

function installClientOverview(root, code) {
  const intro = root.firstElementChild;
  intro.className = "client-overview";
  intro.innerHTML = `<div class="client-heading"><div><a href="/clienti">← Archivio clienti</a><h1>Scheda cliente <span></span></h1></div>
    <button class="btn" type="button" data-jump="meeting">Prepara il colloquio ↓</button></div>
    <div class="client-spread">
      <section class="wealth"><h2>Patrimonio complessivo</h2><strong data-worth></strong>
        <div class="wealth-facts"><div><small>Conto e depositi</small><b data-cash></b></div><div><small>Accantonamento mensile</small><b data-saving></b></div></div>
      </section>
      <section class="allocation"><h2>Composizione patrimoniale</h2><div class="allocation-body">
        <div class="allocation-ring" aria-hidden="true"><div><b data-count></b><small>posizioni</small></div></div>
        <ul class="allocation-list"></ul></div>
      </section>
    </div>`;
  $("h1 span",intro).textContent = code;
  $("[data-jump]",intro).onclick = () => {
    const heading = $(".meeting h2",root);
    heading.tabIndex = -1;
    heading.focus({preventScroll:true});
    heading.scrollIntoView({block:"center",behavior:still.matches?"instant":"smooth"});
  };
  motion()?.animate($$(".wealth, .allocation",intro), {opacity:[0,1],y:[8,0]},
    {duration:.38, delay:i=>i*.065, ease:EASE});
}

function updateClientOverview(root, rows) {
  const panel = $(".client-overview",root);
  const money = cents => (cents / 100).toLocaleString("it-IT",{style:"currency",currency:"EUR",minimumFractionDigits:cents%100?2:0});
  const total = rows ? advice.total(rows) : 0;
  const sums = new Map();
  for (const row of rows || []) {
    sums.set(row.category,(sums.get(row.category)||0)+row.amount);
  }
  for (const [field,value] of [["worth",total],["cash",sums.get("Conto e depositi")||0]]) {
    $("[data-"+field+"]",panel).textContent = rows ? money(value) : "—";
  }
  const saving=$("#monthly-saving",root);
  $("[data-saving]",panel).textContent=saving?.value && saving.validity.valid ? money(Math.round(saving.valueAsNumber*100)) : "Da indicare";
  $("[data-count]",panel).textContent = rows ? rows.length : "—";
  const colors = ["--accent","--r-defl","--r-gold","--r-refl","--r-stag"];
  const segments = [], items = [];
  let offset = 0;
  for (const [category,amount] of [...sums].sort((a,b)=>b[1]-a[1])) {
    const percent = 100*amount/total;
    const color = "var("+colors[advice.categories.indexOf(category)]+")";
    segments.push(color+" "+offset+"% "+(offset+percent)+"%");
    offset += percent;
    items.push(`<li><i style="background:${color}"></i><span>${esc(category)}<small>${money(amount)}</small></span><b>${fmt(percent,1)}%</b></li>`);
  }
  $(".allocation-ring",panel).style.background = segments.length ? "conic-gradient("+segments.join(",")+")" : "var(--line)";
  $(".allocation-list",panel).innerHTML = items.join("") || '<li class="allocation-empty">'+(rows?"Aggiungi la prima posizione.":"Verifica gli importi delle posizioni.")+'</li>';
}
