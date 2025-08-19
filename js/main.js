/* ---------- BLOCKLY INIT ------------------------------------------------- */
const workspace = Blockly.inject('blocklyDiv', { toolbox });

/* ---------- Live dropdowns for global keys ------------------------------ */
function refreshGlobalKeyDropdowns(){
  const keys=new Set();
  workspace.getAllBlocks(false).forEach(b=>{
    if(b.type==='globals_values_create'){
      const k=b.getFieldValue('KEY');
      if(k) keys.add(k);
    }
  });
  keys.forEach(k=>{
    if(!(k in globals_values)) globals_values[k]=undefined;
  });
  workspace.getAllBlocks(false).forEach(b=>{
    if(b.type==='globals_values_get'||b.type==='globals_values_set'){
      const field=b.getField('KEY');
      const cur=field.getValue();
      if(field?.replaceOptions){
        field.replaceOptions(keys.size?[...keys].map(k=>[k,k]):[['','']]);
      }
      if(!keys.has(cur)){
        field.setValue(keys.size?[...keys][0]:'');
      }
    }
  });
}
workspace.addChangeListener(e=>{
  if(e.type===Blockly.Events.CREATE||(e.type===Blockly.Events.CHANGE&&e.name==='KEY'))
    refreshGlobalKeyDropdowns();
});
refreshGlobalKeyDropdowns();

/* ---------- Local Storage ---------------------------------------------- */
const XML={
  textToDom:Blockly.utils?.xml?.textToDom||Blockly.Xml.textToDom,
  domToText:Blockly.utils?.xml?.domToText||Blockly.Xml.domToText,
  domToWorkspace:Blockly.Xml.domToWorkspace,
  workspaceToDom:Blockly.Xml.workspaceToDom,
};
const LS_KEY='csv_strategy_builder_workspace';
{
  const txt=localStorage.getItem(LS_KEY);
  if(txt){
    try{ XML.domToWorkspace(XML.textToDom(txt),workspace);}
    catch(e){ console.warn('Corrupted XML in LS – cleared',e); localStorage.removeItem(LS_KEY);}
  }
}
const saveWorkspaceNow=()=>{
  localStorage.setItem(LS_KEY,XML.domToText(XML.workspaceToDom(workspace)));
};
workspace.addChangeListener(e=>{ if(e.type!==Blockly.Events.UI) saveWorkspaceNow();});
window.addEventListener('beforeunload',saveWorkspaceNow);

/* ---------- CSV PARSE ---------------------------------------------------- */
let csvData=[];
document.getElementById('csvFile').addEventListener('change',e=>{
  Papa.parse(e.target.files[0],{
    header:true,dynamicTyping:true,skipEmptyLines:true,
    complete:r=>csvData=r.data
  });
});

/* ---------- GLOBAL helpers --------------------------------------------- */
const globals_values_set =(k,v)=>globals_values[k]=v;
const globals_values_get =k=>Number(globals_values[k]);
const globals_values_create=k=>{ if(!globals_values?.[k]) globals_values[k]=undefined;};

/* ---------- BALANCE CHART ---------------------------------------------- */
let balanceChart=null;
function renderBalanceChart(labels,data){
  const ctx=document.getElementById('balanceChart').getContext('2d');
  if(balanceChart) balanceChart.destroy();
  balanceChart=new Chart(ctx,{
    type:'line',
    data:{
      labels,
      datasets:[{
        label:'Balance (cash)',
        data,
        borderWidth:2,
        fill:false,
        borderColor:'#10b981',
        tension:0.1
      }]
    },
    options:{
      responsive:true,
      maintainAspectRatio:false,
      scales:{
        x:{title:{display:true,text:'Time'}},
        y:{title:{display:true,text:'Balance'}}
      }
    }
  });
}

/* ---------- INDICATOR HELPERS ------------------------------------------ */
function computeSMA(data,f,p,idx){
  if(idx<p-1) return 0;
  let s=0; for(let i=idx-p+1;i<=idx;i++) s+=Number(data[i][f]);
  return s/p;
}
function computeMACD(data,f,fast,slow,idx){
  return computeSMA(data,f,fast,idx)-computeSMA(data,f,slow,idx);
}
function computeStdDev(data,f,p,idx){
  if(idx<p-1) return 0;
  let s=0,ss=0;
  for(let i=idx-p+1;i<=idx;i++){
    const v=Number(data[i][f]); s+=v; ss+=v*v;
  }
  const m=s/p;
  return Math.sqrt((ss/p)-m*m);
}
function computeBB(data,f,p=20,m=2,idx){
  const mid=computeSMA(data,f,p,idx);
  const sd=computeStdDev(data,f,p,idx);
  return{upper:mid+m*sd,middle:mid,lower:mid-m*sd};
}
const computeBBUpper =(d,f,p,m,i)=>computeBB(d,f,p,m,i).upper;
const computeBBMiddle=(d,f,p,m,i)=>computeBB(d,f,p,m,i).middle;
const computeBBLower =(d,f,p,m,i)=>computeBB(d,f,p,m,i).lower;

/* ---------- SUPERTREND -------------------------------------------------- */
const supertrendCache={};
function trueRange(data,i){
  if(i===0) return data[0].High-data[0].Low;
  return Math.max(
    data[i].High-data[i].Low,
    Math.abs(data[i].High-data[i-1].Close),
    Math.abs(data[i].Low -data[i-1].Close)
  );
}
function computeATR(data,p,i){
  if(i<p) return 0;
  let s=0; for(let k=i-p+1;k<=i;k++) s+=trueRange(data,k); return s/p;
}
function buildSupertrendDir(data,p,f){
  const key=`${p}_${f}`; if(supertrendCache[key]) return supertrendCache[key];
  const n=data.length, dir=new Array(n).fill(true), st=new Array(n).fill(0);
  for(let i=0;i<n;i++){
    const atr=computeATR(data,p,i), hl2=(data[i].High+data[i].Low)/2;
    const upper=hl2+f*atr, lower=hl2-f*atr;
    if(i===0){ dir[i]=true; st[i]=lower; continue;}
    if(data[i].Close>st[i-1]) dir[i]=true;
    else if(data[i].Close<st[i-1]) dir[i]=false;
    else dir[i]=dir[i-1];
    st[i]=dir[i]?lower:upper;
  }
  supertrendCache[key]=dir; return dir;
}
function computeSupertrendUp(data,p,f,i){
  return buildSupertrendDir(data,p,f)[i];
}

/* ---------- SIMULATION --------------------------------------------------- */
document.getElementById('startTest').addEventListener('click',()=>{
  let balance=Number(document.getElementById('balanceInput').value||0);
  const initialBalance=balance;
  const isBalanceInitial=()=>Math.abs(balance-initialBalance)<1e-8;
  let coin=0,totalProfit=0;
  let purchasesQty=0,purchasesSum=0;
  let activeGridOrders=[],gridLocked=false;
  let desiredProfitPct=null;

  const code=Blockly.JavaScript.workspaceToCode(workspace);
  document.getElementById('codeBlock').textContent=code;
  const logs=[],chartLabels=[],chartData=[];

  const buy=(pct,price,time)=>{
    const spent=balance*(pct/100); if(spent<=0||spent>balance) return;
    const qty=spent/price;
    balance-=spent; coin+=qty;
    purchasesQty+=qty; purchasesSum+=qty*price;
    logs.push(`${time} BUY  ${pct.toFixed(2)}% → -${spent.toFixed(2)} USDT, +${qty.toFixed(4)} coin`);
    gridLocked=true;
  };
  const buyQty=(qty,price,time)=>{
    const spent=qty*price; if(spent<=0||spent>balance) return;
    balance-=spent; coin+=qty;
    purchasesQty+=qty; purchasesSum+=qty*price;
    logs.push(`${time} BUY  ${qty.toFixed(4)} coin @ ${price.toFixed(2)} → -${spent.toFixed(2)} USDT`);
    gridLocked=true;
  };
  const sell=(pct,price,time)=>{
    const qty=coin*(pct/100); if(qty<=0||qty>coin) return;
    const gained=qty*price;
    coin-=qty; balance+=gained;
    purchasesQty-=qty; purchasesSum-=qty*price;
    logs.push(`${time} SELL ${pct.toFixed(2)}% → +${gained.toFixed(2)} USDT, -${qty.toFixed(4)} coin`);
    if(coin<1e-8){
      if(balance>initialBalance){
        const profit=balance-initialBalance;
        totalProfit+=profit; balance=initialBalance;
        logs.push(`→ PROFIT realised: +${profit.toFixed(2)} USDT (total ${totalProfit.toFixed(2)} USDT)`);
      }
      gridLocked=false; activeGridOrders=[]; desiredProfitPct=null;
      purchasesQty=0; purchasesSum=0;
    }
  };

  function placeGridOrders(c,f,s,a){
    if(gridLocked) return;
    activeGridOrders=[];
    const step=s/100, g=1+f, pr=[];
    for(let n=0;n<c;n++) pr.push(a*(1-n*step));
    let total=0; for(let n=0;n<c;n++) total+=pr[n]*Math.pow(g,n);
    const Q1=initialBalance/total;
    for(let n=0;n<c;n++){
      const qty=Q1*Math.pow(g,n);
      activeGridOrders.push({price:pr[n],qty,filled:false});
    }
  }
  function processGrid(price,time){
    activeGridOrders.forEach(o=>{
      if(!o.filled&&price<=o.price){ buyQty(o.qty,o.price,time); o.filled=true;}
    });
  }

  function setTakeProfit(p){ desiredProfitPct=p;}
  function processTakeProfit(price,time){
    if(desiredProfitPct===null||coin<=0) return;
    const avg=purchasesQty?purchasesSum/purchasesQty:0;
    if(price>=avg*(1+desiredProfitPct/100)) sell(100,price,time);
  }

  /* ---------- MAIN LOOP ------------------------------------------------ */
  csvData.forEach((row,idx)=>{
    /* fresh closePosition closure for current row ---------------------- */
    const closePosition=()=>{
      if(coin>0) sell(100,row.Close,row.Time);
      gridLocked=false;
      activeGridOrders=[];
      desiredProfitPct=null;
    };

    const fn=new Function(
      'data','row','buy','sell','idx','log',
      'globals_values_set','globals_values_get','globals_values_create',
      'computeSMA','computeMACD','computeBBUpper','computeBBMiddle','computeBBLower','computeSupertrendUp','isBalanceInitial',
      'placeGridOrders','setTakeProfit','closePosition',
      code
    );

    fn(csvData,row,
      pct=>buy(pct,row.Close,row.Time),
      pct=>sell(pct,row.Close,row.Time),
      idx,
      m=>logs.push(String(m)),
      globals_values_set,globals_values_get,globals_values_create,
      computeSMA,computeMACD,computeBBUpper,computeBBMiddle,computeBBLower,computeSupertrendUp,isBalanceInitial,
      placeGridOrders,setTakeProfit,closePosition);

    processGrid(row.Close,row.Time);
    processTakeProfit(row.Close,row.Time);

    chartLabels.push(row.Time);
    chartData.push(balance);
  });

  const summary=`=== RESULT ===
Cash:  ${balance.toFixed(2)}
Coin:  ${coin.toFixed(4)}
Net:   ${(balance+coin*(csvData.at(-1)?.Close||0)).toFixed(2)}
Total profit: ${totalProfit.toFixed(2)}`;
  document.getElementById('summary').textContent=summary;
  logs.push(summary);
  document.getElementById('output').textContent=logs.length?logs.join('\n'):'No actions';

  renderBalanceChart(chartLabels,chartData);
});

/* ---------- RESET WORKSPACE -------------------------------------------- */
document.getElementById('resetWs').onclick=()=>{
  localStorage.removeItem('csv_strategy_builder_workspace');
  workspace.clear();
  document.getElementById('codeBlock').textContent='';
  document.getElementById('summary').textContent='';
  document.getElementById('output').textContent='';
  if(balanceChart){ balanceChart.destroy(); balanceChart=null; }
};
