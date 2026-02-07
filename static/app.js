let showMA = false;

const el = (id) => document.getElementById(id);

function showError(msg){
  const box = el("err");
  box.textContent = msg;
  box.classList.remove("hidden");
}

function clearError(){
  const box = el("err");
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

async function apiPost(url){
  const r = await fetch(url, {method:"POST"});
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
  if (!items || items.length === 0){
    el("pos").innerHTML = `<div class="k">No positions</div>`;
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
  el("pos").innerHTML = html;
}

function renderOrders(items){
  if (!items || items.length === 0){
    el("ord").innerHTML = `<div class="k">No orders</div>`;
    return;
  }

  let html = "";
  for (const o of items.slice(0, 20)){
    html += `
      <div class="row">
        <div class="k">#${o.id} ${o.symbol} ${o.side.toUpperCase()} x${o.qty}</div>
        <div class="v">${o.price}</div>
      </div>
    `;
  }
  el("ord").innerHTML = html;
}

async function refreshSide(){
  const acc = await apiGet("/api/account");
  el("cash").textContent = money(acc.cash);
  el("eq").textContent = money(acc.equity);

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
    hoverlabel: {font:{color:"#071529"}}
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
    const ma20 = sma(c, 20);
    const ma50 = sma(c, 50);

    traces.push({
      type: "scatter",
      x: t,
      y: ma20,
      mode: "lines",
      name: "MA20",
      line: {width: 1.5, color:"#60a5fa"}
    });

    traces.push({
      type: "scatter",
      x: t,
      y: ma50,
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
    modeBarButtonsToAdd: [
      "drawline",
      "drawopenpath",
      "drawrect",
      "drawcircle",
      "eraseshape"
    ],
    modeBarButtonsToRemove: ["lasso2d", "select2d"]
  };

  Plotly.newPlot("chart", traces, layout, config);
}

async function loadChart(){
  clearError();

  const sym = el("sym").value.trim().toUpperCase();
  const tf = el("tf").value;
  const lim = el("lim").value;

  el("title").textContent = `Chart: ${sym} (${tf})`;

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
  const sym = el("sym").value.trim().toUpperCase();
  const url = `/api/order?symbol=${encodeURIComponent(sym)}&qty=1&side=${encodeURIComponent(side)}`;
  await apiPost(url);
  await refreshSide();
}

async function resetAll(){
  clearError();
  await apiPost("/api/reset");
  await refreshSide();
}

function wire(){
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
}

(async function init(){
  wire();
  try{
    await refreshSide();
    await loadChart();
  }catch(e){
    showError(e.message);
  }
})();
