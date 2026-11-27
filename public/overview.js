// Overview: mostra DATA.overview (src/scheduler/export_site.overview_data). Nessun calcolo del modello qui.
const OV_MONTHS = ["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"];
const ovMonth = ym => { const [y,m] = ym.split("-"); return OV_MONTHS[m-1]+" "+y.slice(2); };
const ovMonthLong = ym => { const [y,m] = ym.split("-"); return ["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"][m-1]+" "+y; };
const ovBand = s => s >= 60 ? "pos" : s < 40 ? "neg" : "mid";
const ovBandText = s => s >= 60 ? "Solido" : s < 40 ? "Debole" : "Nella media";
const ovDelta = d => d == null ? "n.d." : (d > 0 ? "+" : d < 0 ? "−" : "±") + Math.abs(d);
const OV_LINES = {Globale:"var(--accent)", "Stati Uniti":"#4f8fd8", Eurozona:"#c6a14c", Italia:"#299b76", Emergenti:"#bd6262"};

function applyOverviewTheme(choice) {
  try {
    if (choice) localStorage.setItem("overview-theme", choice);
    choice ||= localStorage.getItem("overview-theme");
  } catch { /* Le preferenze possono essere bloccate nel browser. */ }
  document.documentElement.dataset.overviewTheme = ["dark","light"].includes(choice) ? choice : dark.matches ? "dark" : "light";
}

// Arco di 270 gradi: traccia, tre fasce (debole, media, solido) e valore. Testo dentro l'SVG, quindi non esce mai.
function overviewGauge(score, delta, month) {
  const r = 84, c = 2*Math.PI*r, arc = c*0.75, cx = 100, cy = 100;
  const seg = (from, to, cls) => '<circle class="'+cls+'" cx="'+cx+'" cy="'+cy+'" r="'+r+'" stroke-dasharray="'+(arc*(to-from)/100-2)+' '+c+'" stroke-dashoffset="'+(-arc*from/100)+'"/>';
  const angle = (135 + 270*score/100) * Math.PI/180;
  const kx = cx + r*Math.cos(angle), ky = cy + r*Math.sin(angle);
  return '<figure class="ov-gauge" aria-label="Global Macro Score '+score+' su 100"><svg viewBox="0 0 200 200" role="img">'+
    '<g transform="rotate(135 100 100)">'+seg(0,40,"b-neg")+seg(40,60,"b-mid")+seg(60,100,"b-pos")+
    '<circle class="g-val" cx="100" cy="100" r="'+r+'" stroke-dasharray="'+(arc*score/100)+' '+c+'"/></g>'+
    '<circle class="g-knob" cx="'+kx.toFixed(1)+'" cy="'+ky.toFixed(1)+'" r="7"/>'+
    '<text class="g-num" x="100" y="108" text-anchor="middle">'+score+'</text>'+
    '<text class="g-sub" x="100" y="134" text-anchor="middle">su 100 · '+ovDelta(delta)+' sul mese</text>'+
    '<text class="g-end" x="38" y="182" text-anchor="middle">0</text><text class="g-end" x="162" y="182" text-anchor="middle">100</text></svg>'+
    '<figcaption><b>Global Macro Score</b><span>'+ovBandText(score)+' · '+ovMonthLong(month)+'</span></figcaption></figure>';
}

function overviewTrend(ov, months, chosen) {
  const series = ov.cards.filter(c => chosen.includes(c.name));
  if (!series.length) return '<p class="ov-empty">Seleziona almeno un’economia.</p>';
  const months_ = [...new Set(series.flatMap(s => s.history.map(h => h[0])))].sort().slice(-months);
  const W = 560, H = 220, L = 34, R = 24, T = 12, B = 30;
  const vals = series.flatMap(s => s.history.filter(h => months_.includes(h[0])).map(h => h[1]));
  const lo = Math.max(0, Math.floor((Math.min(...vals, 40)-5)/10)*10), hi = Math.min(100, Math.ceil((Math.max(...vals, 60)+5)/10)*10);
  const x = i => L + i*(W-L-R)/Math.max(months_.length-1,1), y = v => T + (hi-v)*(H-T-B)/(hi-lo);
  const step = Math.ceil(months_.length/8);
  let out = '<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Macro Score negli ultimi '+months+' mesi">'+
    '<rect class="t-band" x="'+L+'" width="'+(W-L-R)+'" y="'+y(60)+'" height="'+(y(40)-y(60))+'"/>'+
    [...new Set([lo,40,60,hi])].filter(v => v===40||v===60||(v-60>=15||40-v>=15)).map(v => '<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y(v)+'" y2="'+y(v)+'"/><text x="'+(L-8)+'" y="'+(y(v)+4)+'" text-anchor="end">'+v+'</text>').join("")+
    months_.map((m,i) => i % step && i !== months_.length-1 ? "" : '<text x="'+x(i)+'" y="'+(H-8)+'" text-anchor="middle">'+ovMonth(m)+'</text>').join("");
  series.forEach(s => {
    const map = Object.fromEntries(s.history), pts = months_.map((m,i) => map[m] == null ? null : [x(i), y(map[m]), m, map[m]]).filter(Boolean);
    out += '<polyline style="stroke:'+OV_LINES[s.name]+'" class="'+(s.name==="Globale"?"main":"")+'" points="'+pts.map(p=>p[0].toFixed(1)+","+p[1].toFixed(1)).join(" ")+'"/>'+
      pts.map(p => '<circle tabindex="0" style="fill:'+OV_LINES[s.name]+'" cx="'+p[0].toFixed(1)+'" cy="'+p[1].toFixed(1)+'" r="3.5"><title>'+s.name+' · '+ovMonthLong(p[2])+' · '+Math.round(p[3])+'/100</title></circle>').join("");
  });
  return out + '</svg>';
}

// Calendario settimanale (impatto alto, se no medio) e date chiave USA dal calendario ufficiale in cache.
function overviewEvents(limit = 4) {
  const now = Date.now(), future = (DATA?.catalog?.events || []).filter(e => Date.parse(e.date) >= now);
  const high = future.filter(e => e.impact === "High");
  const weekly = (high.length ? high : future.filter(e => e.impact === "Medium")).map(e => ({...e, level: e.impact === "High" ? "Alto" : "Medio"}));
  const keys = (DATA?.overview?.key_events || []).map(e => ({...e, date: e.date+"T12:00:00Z", level: "Chiave", allDay: true}))
    .filter(k => !weekly.some(w => w.date.slice(0,10) === k.date.slice(0,10) && w.country === k.country));
  return [...weekly, ...keys].sort((a,b) => Date.parse(a.date) - Date.parse(b.date)).slice(0, limit);
}

function overviewEventsHtml() {
  const events = overviewEvents(5);
  if (!events.length) return '<p class="ov-empty">Nessun evento futuro nell’ultimo export.</p>';
  return '<ul class="ov-events">'+events.map(e => {
    const d = new Date(e.date);
    return '<li><time><b>'+d.toLocaleDateString("it-IT",{day:"2-digit",timeZone:"Europe/Rome"})+'</b>'+d.toLocaleDateString("it-IT",{month:"short",timeZone:"Europe/Rome"})+'</time><div><strong>'+esc(e.title)+'</strong><small>'+
      (e.allDay?'Data ufficiale':d.toLocaleTimeString("it-IT",{hour:"2-digit",minute:"2-digit",timeZone:"Europe/Rome"}))+' · '+esc(e.country)+(e.forecast?' · stima '+esc(e.forecast):'')+(e.previous?' · prec. '+esc(e.previous):'')+'</small></div><span class="ov-impact" data-level="'+e.level+'">'+e.level+'</span></li>';
  }).join("")+'</ul>';
}

function overviewMarkets() {
  const assets = DATA?.catalog?.assets || {};
  return [
    ["S&P 500","SPY","USD","Chiusura rettificata ETF",assets.SPY?.history],
    ["Azioni eurozona","EZU","USD","Chiusura rettificata ETF",assets.EZU?.history],
    ["Oro","GLD","USD","Chiusura rettificata ETF",assets.GLD?.history],
    ["EUR/USD","Cambio","USD per EUR","Cambio di riferimento",DATA?.catalog?.fx?.EURUSD]
  ];
}

function overviewMoves(markets) {
  return markets.filter(m => m[4]?.length > 1).map(([name,,, ,h]) => {
    const ch = 100*(h.at(-1)[1]/h.at(-2)[1]-1);
    return name+' '+(ch>=0?'+':'−')+fmt(Math.abs(ch))+'% ('+day(h.at(-1)[0])+')';
  });
}

async function overviewAsk(payload, out, button) {
  out.textContent = "Gemma sta elaborando, può servire qualche minuto…";
  if (button) button.disabled = true;
  try {
    const res = await fetch("/api/assistente", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
    const body = await res.json().catch(() => ({}));
    if (res.ok) out.textContent = body.answer + "\n\n— " + body.model + " in locale, sui soli dati dell’export.";
    else if (res.status === 503) out.textContent = body.error + ". Avvia Ollama e riprova.";
    else out.textContent = "L’assistente funziona solo dal server locale (scripts/serve_site.py), non dal sito pubblico.";
  } catch { out.textContent = "L’assistente funziona solo dal server locale (scripts/serve_site.py)."; }
  if (button) button.disabled = false;
}

function renderOverview(page) {
  const ov = DATA?.overview;
  const markets = overviewMarkets();
  if (!ov?.cards?.length) {
    page.innerHTML = '<div class="overview"><h1>Overview</h1><p class="ov-empty">Dati della Overview assenti nell’export: esegui <code>python3 -m src.scheduler.export_site</code>.</p></div>';
    return;
  }
  const g = ov.cards.find(c => c.key === "Globale"), b = ov.briefing, risk = ov.risk;
  const briefDate = new Date(ov.date+"T12:00:00").toLocaleDateString("it-IT",{day:"numeric",month:"long",year:"numeric"});
  const auto = '<small class="ov-tag">Dati reali</small>';
  const snapshotCard = ([name,symbol,unit,source,history]) => {
    const last = history?.at(-1), prev = history?.at(-2);
    if (!prev) return '<article><h3>'+name+'</h3><span>Serie indisponibile nell’ultimo export</span></article>';
    const change = 100*(last[1]/prev[1]-1), digits = symbol === "Cambio" ? 4 : 2;
    return '<article class="ov-mk"><h3>'+name+' <small>'+symbol+'</small></h3><strong class="ov-num">'+fmt(last[1],digits)+'</strong> <small>'+unit+'</small>'+spark(history)+
      '<span class="'+(change>=0?'up':'down')+'">'+(change>=0?'+':'−')+fmt(Math.abs(change))+'% il '+day(last[0])+'</span><small>Rispetto al '+day(prev[0])+' · '+source+'</small></article>';
  };
  const scoreCard = c => {
    const hist = c.history.slice(-12).map(h => h[1]), min = 0, max = 100;
    const pts = hist.map((v,i) => (i*100/Math.max(hist.length-1,1)).toFixed(1)+","+(30-(v-min)*30/(max-min)).toFixed(1)).join(" ");
    const sub = c.components ? Object.entries(c.components).map(([k,v]) => k+' '+v).join(' · ') : 'Media di '+(c.members||[]).join(', ');
    return '<article class="ov-score" data-band="'+ovBand(c.score)+'" title="'+esc(sub)+'"><header><h3>'+c.name+'</h3><em>'+ovBandText(c.score)+'</em></header>'+
      '<div class="ov-score-num"><strong class="ov-num">'+c.score+'</strong><small>/ 100</small><span class="'+(c.delta>0?'up':c.delta<0?'down':'')+'">'+ovDelta(c.delta)+' sul mese</span></div>'+
      '<div class="ov-scale" aria-hidden="true"><i style="left:'+c.score+'%"></i></div>'+
      '<svg class="ov-mini" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true"><line x1="0" x2="100" y1="15" y2="15"/><polyline points="'+pts+'"/></svg>'+
      '<small>'+esc(sub)+'</small></article>';
  };
  const list = (items, empty) => items.length ? '<ol>'+items.map(i => '<li><strong>'+esc(i.title)+'</strong><small>'+esc(i.detail || i.source)+'</small></li>').join("")+'</ol>' : '<p class="ov-empty">'+empty+'</p>';
  const moves = overviewMoves(markets);
  const nextEvents = overviewEvents(3);
  const notes = [...(ov.notifications || []).map(n => ({...n})), ...overviewEvents(10).filter(e => e.level !== "Medio" && Date.parse(e.date) - Date.now() < 48*3600e3)
    .map(e => ({title: e.country, text: e.title+' · '+new Date(e.date).toLocaleString("it-IT",{weekday:"short",hour:"2-digit",minute:"2-digit",timeZone:"Europe/Rome"}), kind: "Evento entro 48 ore"}))];
  const heatCell = c => c ? '<td data-signal="'+c.signal+'" title="'+esc(c.text)+'"><span>'+['−','=','+'][c.signal+1]+'</span></td>' : '<td data-signal="na" title="Dato non disponibile">n.d.</td>';

  page.innerHTML = '<div class="overview"><div class="ov-head"><h1>Overview</h1><div class="ov-tools"><button data-theme></button>'+
    '<button data-panel="Notifiche" aria-label="Apri notifiche"><svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M5 17h14l-2-3V9a5 5 0 0 0-10 0v5zM10 20a2 2 0 0 0 4 0"/></svg> Notifiche'+(notes.length?' <b class="ov-count">'+notes.length+'</b>':'')+'</button><button data-panel="AI Assistant">AI Assistant</button><button data-panel="Watchlist">Watchlist</button></div></div>'+
    '<section class="ov-hero"><div class="ov-eyebrow">Daily Briefing · '+briefDate+' <small class="ov-tag">Generato dai dati</small></div><div class="ov-brief"><div><h2>'+esc(b?.title || "Briefing non disponibile")+'</h2><p>'+esc(b?.text || "")+'</p></div>'+(g?overviewGauge(g.score,g.delta,g.month):'')+'</div>'+
    '<div class="ov-facts"><span>Fase prevalente <b>'+esc(b?.phase || "n.d.")+'</b> <small>'+(b?b.phase_count+' paesi su '+b.areas:'')+'</small></span><span>Rischio di mercato <b>'+esc(risk?.label || "n.d.")+'</b> <small>'+(risk?risk.score+'/100 al '+day(risk.date):'')+'</small></span><span>Borse in tendenza <b>'+ov.trend_up+' su '+ov.trend_total+'</b></span></div>'+
    '<details><summary>Leggi il briefing completo</summary><div class="ov-more">'+
    '<p><b>Ultime sedute.</b> '+(moves.length?esc(moves.join(' · '))+'.':'Prezzi non disponibili.')+'</p>'+
    '<p><b>Mercati.</b> '+esc(risk?.say || "Lettura del rischio non disponibile.")+(risk?.canary_alarm?' Canarino TIP in allarme.':'')+'</p>'+
    '<p><b>Opportunità.</b> '+esc(ov.opportunities.map(o=>o.title).join(', ') || 'nessuna')+'. <b>Rischi.</b> '+esc(ov.risks.map(r=>r.title).join('; ') || 'nessuno')+'.</p>'+
    '<p><b>Eventi da seguire.</b> '+(nextEvents.length?esc(nextEvents.map(e=>e.title+' ('+e.country+', '+new Date(e.date).toLocaleDateString("it-IT",{day:"numeric",month:"short",timeZone:"Europe/Rome"})+')').join(', '))+'.':'Nessun evento ad alto impatto in calendario.')+'</p>'+
    '<p><b>Portafogli.</b> La regola di tendenza è positiva su '+ov.trend_up+' borse su '+ov.trend_total+'; la classifica delle classi di asset mette in testa '+esc(ov.opportunities[0]?.title || 'n.d.')+'. Informativo, non è consulenza.</p>'+
    '<div class="ov-ai"><label>Archivio <input type="date" data-date value="'+ov.date+'" max="'+ov.date+'"></label><span data-archive role="status">Edizione dell’ultimo export.</span>'+
    '<button data-regen>Riscrivi con Gemma (locale)</button></div><pre class="ov-ai-out" data-ai-brief hidden></pre></div></details></section>'+
    '<section><div class="ov-sec"><h2>Macro Score delle economie</h2>'+auto+'<button class="ov-link" data-method>Come si calcola</button></div><div class="ov-scores">'+ov.cards.map(scoreCard).join("")+'</div></section>'+
    '<div class="ov-pair"><section class="ov-card ov-list good"><h2>Opportunità</h2>'+list(ov.opportunities,"Nessuna classe di asset in testa con letture concordi.")+'<small>Classifica delle classi di asset, fase del ciclo e tendenza · fine '+(ov.opportunities[0]?ovMonthLong(ov.opportunities[0].month):'n.d.')+'</small></section>'+
    '<section class="ov-card ov-list bad"><h2>Rischi</h2>'+list(ov.risks,"Nessun allarme attivo.")+'<small>Allarmi di mercato, canarino, ciclo, Macro Score e tendenza</small></section></div>'+
    '<div class="ov-pair"><section class="ov-card"><div class="ov-sec"><h2>Global Macro Trend</h2>'+auto+'</div><div class="ov-controls"><div class="ov-seg" data-months>'+[3,6,12,36].map(m=>'<button data-m="'+m+'"'+(m===12?' aria-pressed="true"':'')+'>'+(m===36?'3 anni':m+' mesi')+'</button>').join("")+'</div>'+
    '<div class="ov-chips">'+ov.cards.map(c=>'<label style="--c:'+OV_LINES[c.name]+'"><input type="checkbox" value="'+c.name+'"'+(c.name==="Globale"?' checked':'')+'> '+c.name+'</label>').join("")+'</div></div><div class="ov-chart"></div><small>Fascia evidenziata: 40-60, situazione tipica del decennio. Passa sopra un punto per il valore.</small></section>'+
    '<section class="ov-card"><div class="ov-sec"><h2>Macro Heatmap</h2>'+auto+'</div><div class="ov-table"><table><thead><tr><th>Economia</th>'+ov.heat_columns.map(v=>'<th>'+v+'</th>').join('')+'</tr></thead><tbody>'+
    ov.heat.map(r=>'<tr><th>'+esc(r.area)+'</th>'+ov.heat_columns.map(k=>heatCell(r.cells[k])).join('')+'</tr>').join('')+'</tbody></table></div><small>+ favorevole · = neutrale · − sfavorevole. Passa sopra una cella per il dato. PMI non disponibile: si usa la fiducia delle imprese OCSE; la Borsa sostituisce il credito.</small></section></div>'+
    '<section><div class="ov-sec"><h2>Market Snapshot</h2>'+auto+'</div><div class="ov-market">'+markets.map(snapshotCard).join('')+'</div></section>'+
    '<section class="ov-card"><div class="ov-sec"><h2>Upcoming Events</h2><small>Calendario della settimana e date chiave USA</small></div>'+overviewEventsHtml()+'<a href="/panoramica?vista=calendario">Apri il calendario →</a></section><dialog><form method="dialog"><button>Chiudi</button></form><h2></h2><div data-content></div></dialog></div>';

  const themeButton = page.querySelector("[data-theme]");
  const themeLabel = () => { themeButton.textContent = document.documentElement.dataset.overviewTheme === "dark" ? "Tema chiaro" : "Tema scuro"; };
  themeLabel();
  themeButton.onclick = () => { applyOverviewTheme(document.documentElement.dataset.overviewTheme === "dark" ? "light" : "dark"); setLogo(); themeLabel(); };

  let months = 12, chosen = ["Globale"];
  try { chosen = JSON.parse(localStorage.getItem("overview-trend") || '["Globale"]'); } catch {}
  const draw = () => { page.querySelector(".ov-chart").innerHTML = overviewTrend(ov, months, chosen); };
  page.querySelectorAll(".ov-chips input").forEach(i => {
    i.checked = chosen.includes(i.value);
    i.onchange = () => { chosen = [...page.querySelectorAll(".ov-chips input:checked")].map(x => x.value); try { localStorage.setItem("overview-trend", JSON.stringify(chosen)); } catch {} draw(); };
  });
  page.querySelectorAll("[data-m]").forEach(btn => btn.onclick = () => {
    months = Number(btn.dataset.m);
    page.querySelectorAll("[data-m]").forEach(x => x.setAttribute("aria-pressed", x === btn));
    draw();
  });
  draw();

  page.querySelector("[data-date]").onchange = e => {
    page.querySelector("[data-archive]").textContent = e.target.value === ov.date ? "Edizione dell’ultimo export." : "Archivio non ancora attivo: è disponibile solo l’edizione dell’ultimo export.";
  };
  const aiBrief = page.querySelector("[data-ai-brief]");
  page.querySelector("[data-regen]").onclick = e => { aiBrief.hidden = false; overviewAsk({mode:"briefing"}, aiBrief, e.currentTarget); };

  const dialog = page.querySelector("dialog"), content = dialog.querySelector("[data-content]");
  const open = (name, html) => { dialog.querySelector("h2").textContent = name; content.innerHTML = html; dialog.showModal(); };
  page.querySelector("[data-method]").onclick = () => open("Macro Score", '<p>'+esc(ov.method)+'</p><p>Sopra 60 solido, sotto 40 debole. Emergenti = media di Cina e India. Globale = media a pesi uguali delle nove economie.</p><p>Componenti per paese:</p><ul class="ov-plain">'+
    Object.entries(ov.areas).map(([a,s])=>'<li><b>'+esc(a)+' '+s.score+'</b> · '+esc(Object.entries(s.components||{}).map(([k,v])=>k+' '+v).join(', '))+'</li>').join("")+'</ul>');
  page.querySelectorAll("[data-panel]").forEach(button => button.onclick = () => {
    const name = button.dataset.panel;
    if (name === "Notifiche") return open(name, notes.length ? '<ul class="ov-plain">'+notes.map(n => '<li><small>'+esc(n.kind)+'</small><b>'+esc(n.title)+'</b> · '+esc(n.text)+'</li>').join("")+'</ul>' : '<p>Nessuna notifica.</p>');
    if (name === "AI Assistant") {
      open(name, '<p>Gemma risponde in locale usando solo i dati di questa Overview.</p><form data-ask><textarea rows="4" required placeholder="Es. perché l’Italia ha un Macro Score basso?"></textarea><button>Chiedi</button></form><pre class="ov-ai-out" data-answer></pre>');
      content.querySelector("[data-ask]").onsubmit = e => { e.preventDefault(); overviewAsk({question:e.target.querySelector("textarea").value}, content.querySelector("[data-answer]"), e.submitter); };
      return;
    }
    open(name, '<p>Mercati del Market Snapshot · ultima chiusura in cache</p>');
    markets.forEach(([label,symbol,unit,source,history]) => {
      const value = history?.length ? fmt(history.at(-1)[1], symbol === "Cambio" ? 4 : 2) : "n.d.";
      const item = document.createElement("label"), input = document.createElement("input");
      input.type = "checkbox";
      try { input.checked = localStorage.getItem("overview-watch-"+label) === "1"; } catch {}
      input.onchange = () => { try { localStorage.setItem("overview-watch-"+label,input.checked?"1":"0"); } catch {} };
      item.append(input," "+label+" · "+value+" "+unit); content.append(item);
    });
  });
}
