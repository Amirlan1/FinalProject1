let showMA = false;

const el = (id) => document.getElementById(id);

function showError(msg){
  const box = el("err");
  if (!box) return;
  box.textContent = msg;
  box.classList.remove("hidden");
}

function clearError(){
  const box = el("err");
  if (!box) return;
  box.textContent = "";
  box.classList.add("hidden");
}

function money(x){
  if (x === null || x === undefined) return "—";
  return "$" + Number(x).toFixed(2);
}

async function apiGet(url){
  const r = await fetch(url);
  if (!r.ok) {
    let txt = await r.text().catch(()=> "");
    throw new Error(`${r.status} ${r.statusText} :: ${txt}`);
  }
  return await r.json();
}

async function apiPost(url, body=null){
  const opt = { method:"POST" };
  if (body !== null){
    opt.headers = {"Content-Type":"application/json"};
    opt.body = JSON.stringify(body);
  }
  const r = await fetch(url, opt);
  if (!r.ok) {
    let txt = await r.text().catch(()=> "");
    throw new Error(`${r.status} ${r.statusText} :: ${txt}`);
  }
  return await r.json();
}

function sma(arr, n){
  const out = new Array(arr.length).fill(null);
  let sum = 0;
  for (let i = 0; i < arr.length; i++){
    sum += arr[i];
    if (i >= n) sum -= arr[i-n];
    if (i >= n-1) out[i] = sum / n;
  }
  return out;
}

function renderPositions(items){
  const box = el("pos");
  if (!box) return;

  if (!items || items.length === 0){
    box.innerHTML = `<div class="k">No positions</div>`;
    return;
  }

  let html = "";
  for (const p of items){
    html += `
      <div class="row">
        <div class="k">${p.symbol} x${p.qty}</div>
        <div class="v">${money(p.market_value)} (${p.unrealized_pl >= 0 ? "+" : ""}${p.unrealized_pl})</div>
      </div>
    `;
  }
  box.innerHTML = html;
}

function renderOrders(items){
  const box = el("ord");
  if (!box) return;

  if (!items || items.length === 0){
    box.innerHTML = `<div class="k">No orders</div>`;
    return;
  }

  let html = "";
  for (const o of items.slice(0, 30)){
    if (o.type === "deposit" || o.type === "withdraw"){
      html += `
        <div class="row">
          <div class="k">#${o.id} ${o.type.toUpperCase()}</div>
          <div class="v">${money(o.amount)}</div>
        </div>
      `;
    } else {
      html += `
        <div class="row">
          <div class="k">#${o.id} ${o.symbol} ${o.side.toUpperCase()} x${o.qty}</div>
          <div class="v">${o.price}</div>
        </div>
      `;
    }
  }
  box.innerHTML = html;
}

async function refreshSide(){
  const acc = await apiGet("/api/account");
  if (el("cash")) el("cash").textContent = money(acc.cash);
  if (el("eq")) el("eq").textContent = money(acc.equity);
  if (el("mode")) el("mode").textContent = (acc.mode || "—").toUpperCase();

  const pos = await apiGet("/api/positions");
  renderPositions(pos);

  const ord = await apiGet("/api/orders");
  renderOrders(ord);
}

function buildPlot(bars, symbol){
  const t = bars.map(b => b.t);
  const o = bars.map(b => b.o);
  const h = bars.map(b => b.h);
  const l = bars.map(b => b.l);
  const c = bars.map(b => b.c);
  const v = bars.map(b => b.v);

  const candle = {
    type: "candlestick",
    x: t,
    open: o,
    high: h,
    low: l,
    close: c,
    name: symbol,
    increasing: {line:{color:"#22c55e"}},
    decreasing: {line:{color:"#ef4444"}},
  };

  const vol = {
    type: "bar",
    x: t,
    y: v,
    name: "Volume",
    yaxis: "y2",
    opacity: 0.25,
    marker: {color:"#93c5fd"}
  };

  const traces = [candle, vol];

  if (showMA){
    traces.push({
      type: "scatter",
      x: t,
      y: sma(c, 20),
      mode: "lines",
      name: "MA20",
      line: {width: 1.5, color:"#60a5fa"}
    });
    traces.push({
      type: "scatter",
      x: t,
      y: sma(c, 50),
      mode: "lines",
      name: "MA50",
      line: {width: 1.5, color:"#f59e0b"}
    });
  }

  const layout = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: {l: 50, r: 25, t: 20, b: 40},
    xaxis: {
      rangeslider: {visible: false},
      gridcolor: "rgba(23,58,99,.45)",
      showline: true,
      linecolor: "rgba(23,58,99,.8)",
      zeroline: false
    },
    yaxis: {
      gridcolor: "rgba(23,58,99,.45)",
      showline: true,
      linecolor: "rgba(23,58,99,.8)",
      zeroline: false
    },
    yaxis2: {
      overlaying: "y",
      side: "right",
      showgrid: false,
      visible: false
    },
    legend: {orientation:"h", y: 1.05, x: 0},
    dragmode: "pan",
    newshape: {
      line: {color:"#e5e7eb", width: 2},
      fillcolor: "rgba(229,231,235,.08)"
    }
  };

  const config = {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
    modeBarButtonsToAdd: ["drawline","drawopenpath","drawrect","drawcircle","eraseshape"],
    modeBarButtonsToRemove: ["lasso2d","select2d"]
  };

  Plotly.newPlot("chart", traces, layout, config);
}

async function loadChart(){
  if (!el("chart")) return;

  clearError();

  const sym = el("sym").value.trim().toUpperCase();
  const tf = el("tf").value;
  const lim = el("lim").value;

  if (el("title")) el("title").textContent = `Chart: ${sym} (${tf})`;

  const url = `/api/bars?symbol=${encodeURIComponent(sym)}&timeframe=${encodeURIComponent(tf)}&limit=${encodeURIComponent(lim)}`;
  const data = await apiGet(url);

  if (!data.bars || data.bars.length === 0){
    showError("No bars returned");
    return;
  }

  buildPlot(data.bars, data.symbol);
}

async function placeOrder(side){
  clearError();
  const symEl = el("sym");
  if (!symEl) return;
  const sym = symEl.value.trim().toUpperCase();
  await apiPost(`/api/order?symbol=${encodeURIComponent(sym)}&qty=1&side=${encodeURIComponent(side)}`);
  await refreshSide();
}

async function resetAll(){
  clearError();
  await apiPost("/api/reset");
  await refreshSide();
}

async function setMode(mode){
  clearError();
  await apiPost(`/api/mode?mode=${encodeURIComponent(mode)}`);
  await refreshSide();
}

function menuInit(){
  const btn = el("btnAccount");
  const menu = el("accountMenu");
  if (!btn || !menu) return;

  menu.style.position = "fixed";
  menu.style.zIndex = "1000001";
  menu.style.display = "none";

  const pad = 12;

  function openMenu(){
    const r = btn.getBoundingClientRect();

    menu.style.display = "block";
    menu.classList.remove("hidden");
    menu.hidden = false;
    menu.removeAttribute("hidden");

    const mw = menu.offsetWidth || 220;
    const mh = menu.offsetHeight || 200;

    let left = r.right - mw;

    if (left < pad) left = pad;
    if (left + mw > window.innerWidth - pad) left = window.innerWidth - pad - mw;

    let top = r.bottom + 8;

    if (top + mh > window.innerHeight - pad) {
      top = Math.max(pad, r.top - mh - 8);
    }

    menu.style.left = left + "px";
    menu.style.top = top + "px";
  }

  function closeMenu(){
    menu.style.display = "none";
    menu.classList.add("hidden");
  }

  function isOpen(){
    return menu.style.display === "block";
  }

  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (isOpen()) closeMenu();
    else openMenu();
  });

  menu.addEventListener("click", (e) => {
    e.stopPropagation();
  });

  document.addEventListener("click", () => {
    closeMenu();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeMenu();
  });

  window.addEventListener("resize", () => {
    if (isOpen()) openMenu();
  });

  window.addEventListener("scroll", () => {
    if (isOpen()) openMenu();
  }, true);
}



function profileInit(){
  const u = el("username");
  const save = el("saveUser");
  if (!u || !save) return;

  save.addEventListener("click", async ()=>{
    try{
      clearError();
      const name = u.value.trim();
      await apiPost(`/api/profile?username=${encodeURIComponent(name)}`);
      await refreshSide();
    } catch(e){ showError(e.message); }
  });

  const sd = el("switchDemo");
  const sr = el("switchReal");
  if (sd) sd.addEventListener("click", async()=>{ try{ await setMode("demo"); }catch(e){ showError(e.message);} });
  if (sr) sr.addEventListener("click", async()=>{ try{ await setMode("real"); }catch(e){ showError(e.message);} });
}

function luhnOk(num){
  const s = (num||"").replace(/\D/g,"");
  let total = 0;
  const rev = s.split("").reverse();
  for (let i=0;i<rev.length;i++){
    let d = rev[i].charCodeAt(0) - 48;
    if (i % 2 === 1){
      d *= 2;
      if (d > 9) d -= 9;
    }
    total += d;
  }
  return (total % 10) === 0;
}

function genFakeInvalidCard(){
  let base = "9999";
  for (let i=0;i<11;i++){
    base += Math.floor(Math.random()*10).toString();
  }

  let last = Math.floor(Math.random()*10);
  let num = base + last.toString();

  if (luhnOk(num)){
    last = (last + 5) % 10;
    num = base + last.toString();
  }

  return num.replace(/(\d{4})(?=\d)/g, "$1 ");
}

function fundingInit(){
  const gen = el("genCard");
  const dep = el("doDeposit");
  const wd = el("doWithdraw");

  if (gen && el("ccNum")){
    gen.addEventListener("click", ()=>{
      el("ccNum").value = genFakeInvalidCard();
    });
  }

  if (dep){
    dep.addEventListener("click", async ()=>{
      try{
        clearError();
        const body = {
          amount: Number(el("depAmount").value),
          name: el("ccName").value,
          number: el("ccNum").value,
          exp: el("ccExp").value,
          cvc: el("ccCvc").value,
        };
        await apiPost("/api/deposit", body);
        await refreshSide();
      } catch(e){ showError(e.message); }
    });
  }

  if (wd){
    wd.addEventListener("click", async ()=>{
      try{
        clearError();
        const a = Number(el("wdAmount").value);
        await apiPost(`/api/withdraw?amount=${encodeURIComponent(a)}`);
        await refreshSide();
      } catch(e){ showError(e.message); }
    });
  }

  const sd = el("switchDemo");
  const sr = el("switchReal");
  if (sd) sd.addEventListener("click", async()=>{ try{ await setMode("demo"); }catch(e){ showError(e.message);} });
  if (sr) sr.addEventListener("click", async()=>{ try{ await setMode("real"); }catch(e){ showError(e.message);} });
}

function chartInit(){
  if (!el("btnLoad")) return;

  el("btnLoad").addEventListener("click", async () => {
    try{
      await loadChart();
      await refreshSide();
    }catch(e){ showError(e.message); }
  });

  el("btnMA").addEventListener("click", async () => {
    try{
      showMA = !showMA;
      await loadChart();
    }catch(e){ showError(e.message); }
  });

  el("btnBuy").addEventListener("click", async () => {
    try{ await placeOrder("buy"); }catch(e){ showError(e.message); }
  });

  el("btnSell").addEventListener("click", async () => {
    try{ await placeOrder("sell"); }catch(e){ showError(e.message); }
  });

  el("btnReset").addEventListener("click", async () => {
    try{ await resetAll(); }catch(e){ showError(e.message); }
  });

  el("sym").addEventListener("keydown", async (ev) => {
    if (ev.key === "Enter"){
      try{
        await loadChart();
        await refreshSide();
      }catch(e){ showError(e.message); }
    }
  });

  const toDemo = el("toDemo");
  const toReal = el("toReal");
  if (toDemo) toDemo.addEventListener("click", async ()=>{ try{ await setMode("demo"); }catch(e){ showError(e.message);} });
  if (toReal) toReal.addEventListener("click", async ()=>{ try{ await setMode("real"); }catch(e){ showError(e.message);} });
}

(async function init(){
  menuInit();
  chartInit();
  profileInit();
  fundingInit();

  try{
    if (el("username")){
      const p = await apiGet("/api/profile");
      el("username").value = p.username || "Trader";
    }
    await refreshSide();
    await loadChart();
  }catch(e){
    showError(e.message);
  }
})();
