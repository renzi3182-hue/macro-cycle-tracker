// Serie mensili illustrative, dicembre 2025 – novembre 2026. Nessun calcolo del modello macro.
const overviewEconomies = [
  ["Stati Uniti", 67, 3], ["Eurozona", 54, 1], ["Italia", 48, -2],
  ["Emergenti", 65, 2], ["Globale", 62, 1]
];
const overviewSeries = [52, 54, 53, 56, 59, 57, 55, 58, 60, 59, 61, 62];
const overviewMonths = ["Dic", "Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov"];
const opportunityNames = ["Titoli di Stato", "Quality Equity", "Oro"];
const riskNames = ["Inflazione persistente", "Rallentamento industriale", "Ampliamento degli spread"];

function applyOverviewTheme(choice) {
  try {
    if (choice) localStorage.setItem("overview-theme", choice);
    choice ||= localStorage.getItem("overview-theme");
  } catch { /* Le preferenze possono essere bloccate nel browser. */ }
  document.documentElement.dataset.overviewTheme = ["dark","light"].includes(choice) ? choice : dark.matches ? "dark" : "light";
}

function overviewTrend(months) {
  const start = overviewSeries.length - months;
  const points = overviewSeries.slice(start).map((value, i) => ({
    x: 40 + i * 464 / (months - 1), y: 154 - (value - 45) * 5,
    label: overviewMonths[start + i], value
  }));
  const path = points.map(p => p.x + "," + p.y).join(" ");
  return '<svg viewBox="0 0 530 186" role="img" aria-label="Macro Score globale dimostrativo negli ultimi '+months+' mesi">' +
    [50,60,70].map(v => '<line x1="40" x2="504" y1="'+(154-(v-45)*5)+'" y2="'+(154-(v-45)*5)+'"/><text x="4" y="'+(158-(v-45)*5)+'">'+v+'</text>').join("") +
    '<polygon points="40,154 '+path+' 504,154"/><polyline points="'+path+'"/>' +
    points.map(p => '<circle tabindex="0" cx="'+p.x+'" cy="'+p.y+'" r="5" aria-label="'+p.label+' '+p.value+'"><title>'+p.label+' · '+p.value+'/100</title></circle><text text-anchor="middle" x="'+p.x+'" y="178">'+p.label+'</text>').join("") + '</svg>';
}

function overviewEvents() {
  const events = (DATA?.catalog?.events || []).filter(e => Date.parse(e.date) >= Date.now())
    .sort((a,b) => Date.parse(a.date) - Date.parse(b.date)).slice(0,3);
  return events.length ? events.map(e => '<p><strong>'+esc(e.title)+'</strong><br>'+esc(new Date(e.date).toLocaleString("it-IT",{timeZone:"Europe/Rome"}))+' · '+esc(e.country)+' · Impatto '+esc(e.impact || "indisponibile")+'</p>').join("")
    : '<p>Nessun evento futuro disponibile nell’ultimo export.</p>';
}

function renderOverview(page) {
  const demo = '<small class="ov-demo">Demo</small>';
  const rows = [[1,0,1,1,0],[0,0,-1,1,0],[-1,0,-1,0,-1],[1,-1,1,0,1],[1,0,0,1,0]];
  // Market Snapshot: chiusure reali dall'export (ETF rettificati da Yahoo, cambio FRED DEXUSEU in cache).
  const assets = DATA?.catalog?.assets || {};
  const markets = [
    ["S&P 500","SPY","USD","Chiusura rettificata ETF",assets.SPY?.history],
    ["Azioni eurozona","EZU","USD","Chiusura rettificata ETF",assets.EZU?.history],
    ["Oro","GLD","USD","Chiusura rettificata ETF",assets.GLD?.history],
    ["EUR/USD","Cambio","USD per EUR","Cambio di riferimento",DATA?.catalog?.fx?.EURUSD]
  ];
  const snapshotCard = ([name,symbol,unit,source,history]) => {
    const last = history?.at(-1), prev = history?.at(-2);
    if (!prev) return '<article><h3>'+name+'</h3><span>Serie indisponibile nell’ultimo export</span></article>';
    const change = 100*(last[1]/prev[1]-1), digits = symbol === "Cambio" ? 4 : 2;
    return '<article><h3>'+name+' <small>'+symbol+'</small></h3><strong>'+fmt(last[1],digits)+'</strong> <small>'+unit+'</small>'+spark(history)+
      '<span>'+(change>=0?'+':'−')+fmt(Math.abs(change))+'% il '+day(last[0])+'</span><small>Rispetto al '+day(prev[0])+' · '+source+'</small></article>';
  };
  page.innerHTML = '<div class="overview"><div class="ov-head"><h1>Overview</h1><div class="ov-tools"><button data-theme></button><button data-panel="Notifiche" aria-label="Apri notifiche"><svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M5 17h14l-2-3V9a5 5 0 0 0-10 0v5zM10 20a2 2 0 0 0 4 0"/></svg> Notifiche</button><button data-panel="AI Assistant">AI Assistant</button><button data-panel="Watchlist">Watchlist</button></div></div>'+
    '<section class="ov-hero"><div class="ov-eyebrow">Daily AI Briefing · 26 novembre 2026 '+demo+'</div><div class="ov-brief"><div><h2>Crescita moderata,<br>mercati selettivi.</h2><p>Nello scenario illustrativo la crescita americana sostiene le azioni di qualità. In Europa, la debolezza industriale invita a osservare credito e spread.</p></div><div class="ov-gauge"><strong>62</strong><span>Global Macro Score / 100</span></div></div>'+
    '<div class="ov-facts"><span>Regime <b>Slowdown</b></span><span>Rischio <b>Moderato</b></span></div><details><summary>Leggi il briefing completo</summary><p><b>Ultime 24 ore nello scenario.</b> Azioni USA e oro in rialzo, azioni europee e cambio EUR/USD in lieve calo. La domanda difensiva è una possibile spiegazione del movimento dell’oro.</p><p><b>Portafoglio.</b> Confrontare qualità azionaria, duration e diversificazione valutaria negli scenari di rallentamento. Opportunità e rischi principali sono riportati sotto.</p><p><b>Eventi da seguire.</b> Inflazione e decisioni sui tassi possono cambiare queste ipotesi.</p><label>Archivio briefing <input type="date" data-date value="2026-11-26"></label><p data-archive role="status">Unica edizione dimostrativa disponibile.</p><button disabled>Aggiornamento AI non collegato</button></details></section>'+
    '<section><h2>Macro Score delle economie '+demo+'</h2><div class="ov-scores">'+overviewEconomies.map(([name,score,delta])=>'<article><h3>'+name+'</h3><strong>'+score+'</strong> <small>/ 100</small><meter min="0" max="100" value="'+score+'" aria-label="Score '+name+'"></meter><span>'+(delta>0?'+':'')+delta+' pt sul mese</span></article>').join("")+'</div></section>'+
    '<div class="ov-pair">'+[[opportunityNames,'Opportunità'],[riskNames,'Rischi']].map(([names,title])=>'<section class="ov-card"><h2>'+title+' '+demo+'</h2><ul>'+names.map(n=>'<li>'+n+'</li>').join("")+'</ul></section>').join("")+'</div>'+
    '<div class="ov-pair"><section class="ov-card"><h2>Global Macro Trend '+demo+'</h2><label>Periodo <select data-months><option value="12">12 mesi</option><option value="6">6 mesi</option><option value="3">3 mesi</option></select></label><div class="ov-chart">'+overviewTrend(12)+'</div></section>'+
    '<section class="ov-card"><h2>Macro Heatmap '+demo+'</h2><div class="ov-table"><table><thead><tr>'+['Economia','PIL','Infl.','PMI','Lavoro','Credito'].map(v=>'<th>'+v+'</th>').join('')+'</tr></thead><tbody>'+rows.map((row,i)=>'<tr><th>'+overviewEconomies[i][0]+'</th>'+row.map(v=>'<td data-signal="'+v+'" title="'+['Negativo','Neutrale','Positivo'][v+1]+'">'+['−','=','+'][v+1]+'</td>').join('')+'</tr>').join('')+'</tbody></table></div><small>+ positivo · = neutrale · − negativo</small></section></div>'+
    '<section><h2>Market Snapshot</h2><div class="ov-market">'+markets.map(snapshotCard).join('')+'</div></section>'+
    '<section class="ov-card"><h2>Upcoming Events</h2>'+overviewEvents()+'<a href="/panoramica?vista=calendario">Apri il calendario →</a></section><dialog><form method="dialog"><button>Chiudi</button></form><h2></h2><div data-content></div></dialog></div>';
  const themeButton = page.querySelector("[data-theme]");
  function themeLabel() {
    themeButton.textContent = document.documentElement.dataset.overviewTheme === "dark" ? "Tema chiaro" : "Tema scuro";
  }
  themeLabel();
  themeButton.onclick = () => { applyOverviewTheme(document.documentElement.dataset.overviewTheme === "dark" ? "light" : "dark"); setLogo(); themeLabel(); };
  page.querySelector("[data-months]").onchange = e => { page.querySelector(".ov-chart").innerHTML = overviewTrend(Number(e.target.value)); };
  page.querySelector("[data-date]").onchange = e => { page.querySelector("[data-archive]").textContent = e.target.value === "2026-11-26" ? "Edizione dimostrativa visualizzata." : "Nessun briefing archiviato per questa data."; };
  const dialog = page.querySelector("dialog");
  page.querySelectorAll("[data-panel]").forEach(button => button.onclick = () => {
    const name = button.dataset.panel;
    dialog.querySelector("h2").textContent = name;
    const content = dialog.querySelector("[data-content]");
    content.textContent = name === "Notifiche" ? "Nessuna notifica disponibile." : "Il collegamento a Ollama è in preparazione.";
    if (name === "Watchlist") {
      content.innerHTML = '<p>Mercati del Market Snapshot · ultima chiusura in cache</p>';
      markets.forEach(([label,symbol,unit,source,history]) => {
        const value = history?.length ? fmt(history.at(-1)[1], symbol === "Cambio" ? 4 : 2) : "n.d.";
        const item = document.createElement("label"), input = document.createElement("input");
        input.type = "checkbox";
        try { input.checked = localStorage.getItem("overview-watch-"+label) === "1"; } catch {}
        input.onchange = () => { try { localStorage.setItem("overview-watch-"+label,input.checked?"1":"0"); } catch {} };
        item.append(input," "+label+" · "+value+" "+unit); content.append(item);
      });
    }
    dialog.showModal();
  });
}
