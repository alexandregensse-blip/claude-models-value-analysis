const MODELS = {
  "fable-5":   {label:"Fable 5",   c:"--fable5"},
  "opus-4.8":  {label:"Opus 4.8",  c:"--opus48"},
  "sonnet-5":  {label:"Sonnet 5",  c:"--sonnet5", tag:true},
  "opus-4.7":  {label:"Opus 4.7",  c:"--opus47"},
  "sonnet-4.6":{label:"Sonnet 4.6",c:"--sonnet46"},
  "haiku-4.5": {label:"Haiku 4.5", c:"--haiku45"},
};
const cvar = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const NS="http://www.w3.org/2000/svg";
const el=(n,a={})=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);return e;};

// per-effort: [rel_cost, ci_lo, ci_hi]
const B = {
  "fable-5":   {intel:75.1, ey:2.2, order:["low","medium","high","xhigh","max"],
    e:{low:[1.37,1.00,1.75],medium:[1.95,1.70,2.10],high:[2.44,1.90,3.20],xhigh:[3.32,2.40,4.60],max:[4.49,3.00,6.30]}},
  "opus-4.8":  {intel:70.4, ey:1.4, order:["low","medium","high","xhigh","max"],
    e:{low:[0.70,0.60,0.80],medium:[1.00,1.00,1.00],high:[1.25,1.15,1.50],xhigh:[1.70,1.50,2.10],max:[2.30,1.70,3.20]}},
  "sonnet-5":  {intel:68.6, ey:2.6, tag:true, order:["low","medium","high","xhigh","max"],
    e:{low:[0.74,0.50,1.15],medium:[1.05,0.70,1.60],high:[1.31,0.85,2.00],xhigh:[1.79,1.15,2.70],max:[2.42,1.50,3.80]}},
  "opus-4.7":  {intel:66.1, ey:2.2, order:["low","medium","high","xhigh","max"],
    e:{low:[0.67,0.45,0.95],medium:[0.95,0.60,1.40],high:[1.19,0.75,1.70],xhigh:[1.62,1.10,2.30],max:[2.19,1.40,3.10]}},
  "sonnet-4.6":{intel:60.1, ey:1.6, order:["low","medium","high","max"],
    e:{low:[0.42,0.35,0.52],medium:[0.60,0.50,0.75],high:[0.75,0.58,0.98],max:[1.38,1.00,1.90]}},
  "haiku-4.5": {intel:40.9, ey:1.9, order:["low","medium","high"],
    e:{low:[0.13,0.08,0.19],medium:[0.19,0.11,0.22],high:[0.24,0.15,0.31]}},
};
// quality offset below the TOP available effort. Concave plateau SHAPE is corroborated by 8 effort-sweep
// sources (OSWorld/swe-rebench/Braintrust/HAL/zenn/qiita + arXiv 2604.18934 & 2603.08640): they agree on
// small gains + plateau on code/agentic (effort pays only on reasoning-math). What is NOT measured is the
// per-MODEL magnitude (no full sweep on Haiku/Fable), so the shape is shared across models as a prior —
// residual uncertainty shows in halo height, not in the qualitative shape.
const OFF5={low:-5.0,medium:-3.2,high:-1.6,xhigh:-0.6,max:0};      // 5-level models (top=max)
const OFF4={low:-5.0,medium:-3.2,high:-1.6,max:0};                  // sonnet-4.6 (top=max, no xhigh)
const OFF3={low:-3.4,medium:-1.6,high:0};                           // haiku (top=high)
function offs(m){return m==="haiku-4.5"?OFF3:(m==="sonnet-4.6"?OFF4:OFF5);}

function drawB(){
  const s=document.getElementById("chartB"); s.innerHTML="";
  const W=760,H=470,mL=58,mR=118,mT=22,mB=56, iw=W-mL-mR, ih=H-mT-mB;
  const xlo=Math.log10(0.09), xhi=Math.log10(6.6);
  const C=79, yBot=35, yTop=77.5;                       // inverted-log Y: dilate the compressed high-intelligence top
  const Ln=v=>Math.log(C-v), lnB=Ln(yBot), lnT=Ln(yTop);
  const X=v=>mL+(Math.log10(v)-xlo)/(xhi-xlo)*iw;
  const Y=v=>mT+(1-(lnB-Ln(Math.max(yBot,Math.min(v,yTop))))/(lnB-lnT))*ih;
  [0.1,0.2,0.5,1.0,2.0,5.0].forEach(t=>{ s.appendChild(el("line",{x1:X(t),y1:mT,x2:X(t),y2:mT+ih,stroke:cvar('--line'),"stroke-width":1}));
    const tx=el("text",{x:X(t),y:mT+ih+20,fill:cvar('--faint'),"font-size":11,"text-anchor":"middle"});tx.textContent=t+"×";s.appendChild(tx);});
  [40,55,63,68,72,75,77].forEach(v=>{ s.appendChild(el("line",{x1:mL,y1:Y(v),x2:mL+iw,y2:Y(v),stroke:cvar('--line'),"stroke-width":1}));
    const ty=el("text",{x:mL-10,y:Y(v)+4,fill:cvar('--faint'),"font-size":11,"text-anchor":"end"});ty.textContent=v;s.appendChild(ty);});
  let a=el("text",{x:mL+iw/2,y:H-12,fill:cvar('--muted'),"font-size":12.5,"text-anchor":"middle"});a.textContent="Coût relatif  (Opus 4.8 @medium = 1,0 · échelle log)";s.appendChild(a);
  a=el("text",{x:16,y:mT+ih/2,fill:cvar('--muted'),"font-size":12.5,"text-anchor":"middle",transform:`rotate(-90 16 ${mT+ih/2})`});a.textContent="Intelligence (indice Vals · échelle log inversée)";s.appendChild(a);
  s.appendChild(el("line",{x1:X(1),y1:mT,x2:X(1),y2:mT+ih,stroke:cvar('--opus48'),"stroke-width":1,"stroke-dasharray":"3 4","stroke-opacity":.5}));

  // draw ribbons first (behind), then curves+points
  const draw=(phase)=>{
    for(const m in B){ const cfg=B[m], col=cvar(MODELS[m].c), off=offs(m);
      const pts=cfg.order.map(e=>{const d=cfg.e[e];return {e,c:d[0],lo:d[1],hi:d[2],y:cfg.intel+off[e]};});
      const ey=cfg.ey;
      if(phase===0){ // 2D CI ribbon: top edge along ci_lo/(y+ey), bottom edge along ci_hi/(y-ey)
        let d="M"+pts.map(p=>X(p.lo)+" "+Y(p.y+ey)).join(" L ");
        d+=" L "+pts.slice().reverse().map(p=>X(p.hi)+" "+Y(p.y-ey)).join(" L ")+" Z";
        s.appendChild(el("path",{d,fill:col,"fill-opacity":.13,stroke:col,"stroke-opacity":.22,"stroke-width":1}));
      } else { // central curve + effort points
        let d=pts.map((p,i)=>(i?"L":"M")+X(p.c)+" "+Y(p.y)).join(" ");
        s.appendChild(el("path",{d,fill:"none",stroke:col,"stroke-width":2.4,"stroke-linejoin":"round"}));
        pts.forEach(p=>{ const r=el("circle",{cx:X(p.c),cy:Y(p.y),r:4.6,fill:col,stroke:cvar('--panel'),"stroke-width":1.5});
          if(cfg.tag) r.setAttribute("stroke-dasharray","2 2"); s.appendChild(r);
          const t=el("text",{x:X(p.c),y:Y(p.y)-9,fill:cvar('--muted'),"font-size":9,"text-anchor":"middle"});t.textContent=p.e;s.appendChild(t);});
        const last=pts[pts.length-1];
        const lb=el("text",{x:X(last.c)+11,y:Y(last.y)+4,fill:cvar('--ink'),"font-size":12.5,"font-weight":600});lb.textContent=MODELS[m].label;s.appendChild(lb);
      }
    }
  };
  draw(0); draw(1);
  const lg=document.getElementById("legendB"); lg.innerHTML=
    Object.keys(MODELS).map(m=>`<span class="lg"><span class="sw" style="background:${cvar(MODELS[m].c)}"></span>${MODELS[m].label}</span>`).join("")
    +`<span class="lg"><span class="sw" style="opacity:.22;background:var(--ink)"></span>halo = IC 2D (coût × qualité)</span>`;
}

// ---------- MATRIX (sorted by intelligence desc) ----------
const M = {
  "fable-5":   {intel:75.1,low:[1.37,"1,10–1,65"],medium:[1.95,"1,70–2,10"],high:[2.44,"2,00–3,00"],xhigh:[3.32,"2,60–4,30"],max:[4.49,"3,20–6,00"]},
  "opus-4.8":  {intel:70.4,low:[0.70,"0,60–0,80"],medium:[1.00,"ancre"],high:[1.25,"1,15–1,50"],xhigh:[1.70,"1,50–2,10"],max:[2.30,"1,70–3,20"]},
  "sonnet-5":  {intel:68.6,tag:true,low:[0.74,"0,50–1,15"],medium:[1.05,"0,70–1,60"],high:[1.31,"0,85–2,00"],xhigh:[1.79,"1,15–2,70"],max:[2.42,"1,50–3,80"]},
  "opus-4.7":  {intel:66.1,low:[0.67,"0,45–0,95"],medium:[0.95,"0,60–1,40"],high:[1.19,"0,75–1,70"],xhigh:[1.62,"1,10–2,30"],max:[2.19,"1,40–3,10"]},
  "sonnet-4.6":{intel:60.1,low:[0.42,"0,35–0,52"],medium:[0.60,"0,50–0,75"],high:[0.75,"0,60–0,95"],xhigh:null,max:[1.38,"1,00–1,90"]},
  "haiku-4.5": {intel:40.9,low:[0.13,"0,08–0,18"],medium:[0.19,"0,11–0,22"],high:[0.24,"0,15–0,30"],xhigh:null,max:null},
};
function heat(v){
  const t=Math.max(0,Math.min(1,(Math.log10(v)-Math.log10(0.12))/(Math.log10(4.5)-Math.log10(0.12))));
  const dark=document.documentElement.getAttribute('data-theme')==='dark'||(window.matchMedia('(prefers-color-scheme:dark)').matches&&document.documentElement.getAttribute('data-theme')!=='light');
  const al=dark?(0.10+t*0.42):(0.07+t*0.40);
  return `background:color-mix(in srgb, var(--opus48) ${Math.round(al*100)}%, transparent)`;
}
function drawMatrix(){
  const tb=document.querySelector("#matrix-tbl tbody"); tb.innerHTML="";
  const rows=Object.keys(M).sort((a,b)=>M[b].intel-M[a].intel);
  for(const m of rows){ const md=MODELS[m], tr=document.createElement("tr");
    let row=`<td class="mdl"><span class="dot" style="background:${cvar(md.c)}"></span>${md.label}${M[m].tag?' <span class="pill">taille-tâche</span>':''}</td>`;
    ["low","medium","high","xhigh","max"].forEach(e=>{ const c=M[m][e];
      row+= c? `<td><div class="cell num" style="${heat(c[0])}">${c[0].toFixed(2).replace('.',',')}<small>${c[1]}</small></div></td>`
             : `<td class="na">—</td>`; });
    row+=`<td class="mdl num">${M[m].intel.toFixed(1).replace('.',',')}</td>`;
    tr.innerHTML=row; tb.appendChild(tr);
  }
}
// ---------- LINKING GRAPH ----------
// nodes = (model,effort) couples ; edges = a source that measured them on the SAME task. Extracted from raw-data.csv groups.
// h = actual run config extracted per source (harness · effort). "défaut harness" = source didn't override
// the harness's out-of-box config (Claude Code & agent frameworks enable thinking; a raw API call does not).
const GROUPS = [
 {s:"artificialanalysis",g:"AA Index",t:"xmodel",h:"AA-Index · max ✓",n:["opus-4.8@max","fable-5@max","opus-4.7@max","sonnet-5@max"]},
 {s:"artificialanalysis",g:"AA /task",t:"xmodel",h:"AA-Index · max ✓",n:["opus-4.8@max","sonnet-4.6@max","sonnet-5@max"]},
 {s:"aireiter",g:"AIReiter",t:"xmodel",w:3,h:"Claude Code · high ✓",n:["opus-4.8@high","sonnet-5@high"]},
 {s:"arxiv 2604.18934",g:"AutomationB.",t:"xmodel",h:"harness+effort NON précisés ✓",n:["opus-4.7@default","haiku-4.5@default","sonnet-4.6@default"]},
 {s:"braintrust",g:"Braintrust",t:"sweep",h:"retrieval · budget T25/T50 ✓",n:["opus-4.8@medium","opus-4.8@high","sonnet-4.6@medium","sonnet-4.6@high"]},
 {s:"arxiv 2606.18543",g:"CEO-Bench",t:"xmodel",h:"terminal-agent · Opus/Sonnet=MAX, Haiku=thinking ✓",n:["opus-4.8@max","opus-4.7@max","sonnet-4.6@max","haiku-4.5@default"]},
 {s:"arxiv 2606.15689",g:"code-review",t:"xmodel",h:"VibeOps · temp 0.1, thinking NS ✓",n:["sonnet-4.6@default","haiku-4.5@default"]},
 {s:"codesota",g:"CodeSOTA",t:"xmodel",h:"prix list blended (pas un run) ✓",n:["opus-4.8@default","sonnet-4.6@default"]},
 {s:"github ctala",g:"ctala",t:"xmodel",h:"Claude Code CLI · reasoning non config, temp 0.7 ✓",n:["opus-4.8@default","fable-5@default","haiku-4.5@default"]},
 {s:"github drona23",g:"drona23",t:"xgen",h:"Claude Code CLI · thinking NS, identique ✓",n:["sonnet-4.6@default","haiku-4.5@default","opus-4.6@default"]},
 {s:"vals.ai",g:"EMB",t:"xmodel",h:"bash+execute · Opus4.8=MAX, Sonnet5 NS ✓",n:["opus-4.8@max","sonnet-5@default"]},
 {s:"ai.georgeliu",g:"george-liu",t:"sweep",h:"Claude Code · low/max ✓",n:["opus-4.7@low","opus-4.7@max"]},
 {s:"hal-princeton",g:"HAL sci",t:"xgen",h:"HAL · high ✓",n:["sonnet-3.7@high","sonnet-4.5@high"]},
 {s:"hal-princeton",g:"HAL swe-mini",t:"xgen",h:"HAL · high vs défaut ✓",n:["sonnet-4.5@default","opus-4.1@default","sonnet-4.5@high"]},
 {s:"ianlpaterson",g:"ianlpaterson",t:"xgen",h:"OpenRouter · reasoning OFF (« no special reasoning ») ✓",n:["sonnet-4.6@default","haiku-4.5@default","opus-4.6@default"]},
 {s:"arxiv 2603.08655",g:"OfficeQA",t:"xgen",h:"Claude Agent SDK · reasoning HIGH ✓",n:["sonnet-4.6@high","haiku-4.5@high","opus-4.6@high"]},
 {s:"anthropic-chart",g:"OSWorld",t:"sweep",h:"Anthropic/AA · balayage low→max ✓",n:["opus-4.8@medium","opus-4.8@low","opus-4.8@high","opus-4.8@xhigh","opus-4.8@max","sonnet-4.6@low","sonnet-4.6@medium","sonnet-4.6@high","sonnet-4.6@max","sonnet-5@low","sonnet-5@medium","sonnet-5@high","sonnet-5@xhigh","sonnet-5@max"]},
 {s:"simonwillison",g:"Willison SVG",t:"sweep",h:"llm CLI · balayage low→max, tâche triviale (SVG) ✓",n:["fable-5@low","fable-5@medium","fable-5@high","fable-5@xhigh","fable-5@max"]},
 {s:"futuresearch",g:"DeepResearch",t:"sweep",h:"Deep Research Bench · low/high ✓",n:["sonnet-4.6@low","sonnet-4.6@high"]},
 {s:"cursorbench",g:"CursorBench",t:"sweep",h:"Cursor 3.1 · balayage low→max, effort apparié ✓ (éditeur=vendeur)",n:["fable-5@low","fable-5@medium","fable-5@high","fable-5@xhigh","fable-5@max","opus-4.8@low","opus-4.8@medium","opus-4.8@high","opus-4.8@xhigh","opus-4.8@max","opus-4.7@low","opus-4.7@medium","opus-4.7@high","opus-4.7@xhigh","opus-4.7@max","sonnet-5@low","sonnet-5@medium","sonnet-5@high","sonnet-5@xhigh","sonnet-5@max","sonnet-4.6@low","sonnet-4.6@medium","sonnet-4.6@high","sonnet-4.6@max"]},
 {s:"github ponytail",g:"ponytail",t:"xgen",h:"Claude Code headless · thinking NS ✓",n:["sonnet-4.6@default","haiku-4.5@default","opus-4.6@default"]},
 {s:"arxiv 2603.08640",g:"PostTrainB.",t:"sweep",h:"papier · medium/high ✓",n:["opus-4.5@medium","opus-4.5@high"]},
 {s:"qiita",g:"qiita",t:"sweep",h:"API brut · low/max ✓",n:["opus-4.7@low","opus-4.7@max"]},
 {s:"arxiv 2602.12670",g:"SkillsBench",t:"xmodel",h:"Claude Code 2.1.19 · temp 0, thinking NS ✓",n:["opus-4.8@default","opus-4.7@default","sonnet-4.6@default"]},
 {s:"arxiv 2603.24755",g:"SlopCode",t:"xgen",h:"Claude Code · Reasoning HIGH ✓",n:["sonnet-4.6@high","opus-4.6@high"]},
 {s:"arxiv 2606.10394",g:"STAGE-Claw",t:"xmodel",h:"OpenClaw · reasoning DISABLED, temp 0 ✓",n:["opus-4.7@default","sonnet-4.6@default"]},
 {s:"swe-rebench",g:"swe-rebench",t:"xgen",h:"ReAct minimal · Opus4.8 xhigh/4.7 high, Sonnet défaut ✓",n:["opus-4.8@xhigh","opus-4.7@high","opus-4.6@high","sonnet-4.6@default"]},
 {s:"arxiv 2605.16909",g:"TOBench",t:"xgen",h:"ReAct · thinking NS ✓",n:["sonnet-4.6@default","haiku-4.5@default","opus-4.6@default"]},
 {s:"truefoundry",g:"TrueFoundry",t:"xmodel",h:"AI Gateway · single-turn sans outils, effort NS ✓",n:["opus-4.8@default","opus-4.7@default"]},
 {s:"whitekumalabo",g:"whitekumalabo",t:"sweep",h:"Claude Code · low/max ✓",n:["opus-4.6@low","opus-4.6@max"]},
 {s:"arxiv 2605.10912",g:"WildClaw",t:"xgen",h:"OpenRouter (4 harness) · thinking NS, identique ✓",n:["opus-4.7@default","opus-4.6@default"]},
 {s:"arxiv 2606.13715",g:"WorkBench",t:"xmodel",h:"ReAct natif · temp 0, like-for-like, thinking NS ✓",n:["opus-4.8@default","fable-5@default","haiku-4.5@default","sonnet-4.6@default"]},
 {s:"zenn QCD",g:"zenn QCD",t:"sweep",h:"API brut · low/xhigh ✓",n:["opus-4.8@low","opus-4.8@xhigh","sonnet-5@low","sonnet-5@xhigh"]},
];
const GMODEL = {
 "fable-5":{l:"Fable 5",c:"--fable5",cur:1},"opus-4.8":{l:"Opus 4.8",c:"--opus48",cur:1},
 "opus-4.7":{l:"Opus 4.7",c:"--opus47",cur:1},"sonnet-5":{l:"Sonnet 5",c:"--sonnet5",cur:1},
 "sonnet-4.6":{l:"Sonnet 4.6",c:"--sonnet46",cur:1},"haiku-4.5":{l:"Haiku 4.5",c:"--haiku45",cur:1},
 "opus-4.6":{l:"Opus 4.6",leg:1},"sonnet-3.7":{l:"Sonnet 3.7",leg:1},"opus-4.5":{l:"Opus 4.5",leg:1},
 "sonnet-4.5":{l:"Sonnet 4.5",leg:1},"opus-4.1":{l:"Opus 4.1",leg:1},
};
const GCOL={sweep:"#2E9C8E",xmodel:"#7C6BB2",xgen:"#B98A3E"};
const GTLAB={sweep:"balayage d'effort (même modèle)",xmodel:"inter-modèles (même génération)",xgen:"pont inter-génération"};
const MEFF={"fable-5":["low","medium","high","xhigh","max"],"opus-4.8":["low","medium","high","xhigh","max"],"sonnet-5":["low","medium","high","xhigh","max"],"opus-4.7":["low","medium","high","xhigh","max"],"sonnet-4.6":["low","medium","high","max"],"haiku-4.5":["solo"]};   // Haiku 4.5 = modèle à EFFORT UNIQUE (pas de paramètre effort discret) → un seul nœud fusionnant toutes ses sources, placé hors des paliers ; coût aussi en §6 (régime no-think, ancre)
const MX={"fable-5":0,"opus-4.8":1,"opus-4.7":2,"sonnet-5":3,"sonnet-4.6":4,"haiku-4.5":5,"opus-4.6":6.4,"sonnet-3.7":6.9,"opus-4.5":7.3,"sonnet-4.5":7.8,"opus-4.1":8.3};
const EORD=["max","xhigh","high","medium","low"];   // corroboration graph: 5 explicit efforts, no default row
const EORD2=["max","xhigh","high","medium","low","default"];   // line-cloud assignment view: adds the 'défaut' row
function buildEdges(){
  const pm=new Map();
  const add=(A,B,g,ty)=>{ if(A===B)return; const t=ty||g.t;
    const k=[A,B].sort().join("|"); let o=pm.get(k);
    if(!o){o={a:k.split("|")[0],b:k.split("|")[1],w:0,ty:{}};pm.set(k,o);}
    const w=g.w||1; o.w+=w; o.ty[t]=(o.ty[t]||0)+w; };
  GROUPS.forEach(g=>{
    const cn=g.n.filter(x=>{const[mm,ee]=x.split("@");return GMODEL[mm]&&GMODEL[mm].cur&&MEFF[mm]&&MEFF[mm].includes(ee);});  // ladder nodes only: effort must be one of the model's own MEFF efforts (excludes @default/@nothink AND Haiku's non-ladder nodes — Haiku's sole effort is 'solo', never in GROUPS)
    if(g.t==="sweep"){
      const byM={}; cn.forEach(x=>{const[m,e]=x.split("@");(byM[m]=byM[m]||[]).push(e);});
      for(const m in byM){ const es=[...new Set(byM[m])].sort((a,b)=>EORD.indexOf(a)-EORD.indexOf(b));
        for(let i=0;i<es.length-1;i++) add(m+"@"+es[i],m+"@"+es[i+1],g); }                 // within-model effort ladder (sweep)
      const byE={}; cn.forEach(x=>{const e=x.split("@")[1];(byE[e]=byE[e]||[]).push(x);});
      for(const e in byE){ const a=byE[e]; for(let i=0;i<a.length;i++)for(let j=i+1;j<a.length;j++) add(a[i],a[j],g,"xmodel"); }  // cross-model at matched effort (e.g. OSWorld Opus4.8/Sonnet5/Sonnet4.6)
    } else { for(let i=0;i<cn.length;i++)for(let j=i+1;j<cn.length;j++) add(cn[i],cn[j],g); }
  });
  return [...pm.values()].map(o=>{ let bt="xmodel",bw=-1; for(const t in o.ty) if(o.ty[t]>bw){bw=o.ty[t];bt=t;} o.type=bt; return o; });
}
function drawGraph(){
  const s=document.getElementById("chartG"); s.innerHTML="";
  const W=780,H=460,mLg=80,mRg=32,mTg=36,mBg=20, iwg=W-mLg-mRg, ihg=H-mTg-mBg;
  const EY={}; EORD.forEach((e,i)=>EY[e]=i);
  const colGap=iwg/5, rowGap=ihg/4;
  const px=m=>mLg+MX[m]*colGap, py=e=>mTg+EY[e]*rowGap;
  const nd=x=>x.split("@");
  // effort rows (5 explicit efforts, no default row)
  EORD.forEach(e=>{ const y=py(e);
    s.appendChild(el("line",{x1:mLg-8,y1:y,x2:mLg+iwg,y2:y,stroke:cvar('--line'),"stroke-width":1}));
    const t=el("text",{x:mLg-14,y:y+4,fill:cvar('--faint'),"font-size":10.5,"text-anchor":"end"});t.textContent=e;s.appendChild(t);});
  // column labels — the 6 current models ONLY (legacy models fully removed from display)
  for(const m in MX){ const g=GMODEL[m]; if(!g.cur||!MEFF[m]) continue;   // Haiku (no MEFF) not shown on the effort ladder
    const t=el("text",{x:px(m),y:mTg-16,fill:cvar(g.c),"font-size":11.5,"font-weight":700,"text-anchor":"middle"});
    t.textContent=g.l;s.appendChild(t);}
  const srcCount={}; GROUPS.forEach(g=>{ const seen=new Set(); g.n.forEach(id=>{ if(!seen.has(id)){seen.add(id); srcCount[id]=(srcCount[id]||0)+1;} }); });
  let hkc=0; GROUPS.forEach(g=>{ if(g.n.some(id=>id.startsWith("haiku-4.5@"))) hkc++; }); srcCount["haiku-4.5@solo"]=hkc;   // Haiku = single merged node: count every source that measured it in any config
  const COLR={g:"#2E9C5A",y:"#D9B23A",o:"#E08A2E",r:"#E0342A"};
  const colFor=c=>c>=3?COLR.g:c===2?COLR.y:c===1?COLR.o:COLR.r;
  const LINK=cvar('--muted');
  buildEdges().forEach(o=>{ const[am,ae]=nd(o.a),[bm,be]=nd(o.b);
    const x1=px(am),y1=py(ae),x2=px(bm),y2=py(be);
    const dx=x2-x1,dy=y2-y1,len=Math.hypot(dx,dy)||1, amt=Math.min(34,0.22*len);
    const cx=(x1+x2)/2+(-dy/len)*amt, cy=(y1+y2)/2+(dx/len)*amt;
    const w=Math.min(7,1.1+0.85*(o.w-1)), op=Math.min(.75,.36+.06*o.w);
    s.appendChild(el("path",{d:`M${x1} ${y1} Q${cx} ${cy} ${x2} ${y2}`,fill:"none",stroke:LINK,"stroke-width":w,"stroke-opacity":op,"stroke-linecap":"round"}));
    if(o.w>=2){ const lx=0.25*x1+0.5*cx+0.25*x2, ly=0.25*y1+0.5*cy+0.25*y2;
      const lb=el("text",{x:lx,y:ly-1,fill:LINK,"font-size":9,"text-anchor":"middle","font-weight":700,"paint-order":"stroke","stroke":cvar('--panel'),"stroke-width":2.6,"stroke-linejoin":"round"});
      lb.textContent="×"+o.w;s.appendChild(lb);}});
  const measured=new Set(); GROUPS.forEach(g=>g.n.forEach(x=>measured.add(x))); measured.add("haiku-4.5@solo");
  const ring=(x,y,r,c)=>s.appendChild(el("circle",{cx:x,cy:y,r,fill:"none",stroke:c,"stroke-width":2.2}));
  const tally={g:0,y:0,o:0,r:0}, bump=c=>{tally[c>=3?'g':c===2?'y':c===1?'o':'r']++;};
  for(const m in MEFF){ MEFF[m].forEach(e=>{ const id=m+"@"+e, x=px(m), y=(e==="solo"?mTg+ihg*0.52:py(e)), col=cvar(GMODEL[m].c), c=srcCount[id]||0;
    if(measured.has(id)){ s.appendChild(el("circle",{cx:x,cy:y,r:5.6,fill:col,stroke:cvar('--panel'),"stroke-width":1.4}));}
    else { s.appendChild(el("circle",{cx:x,cy:y,r:4.8,fill:"none",stroke:cvar('--faint'),"stroke-width":1.3,"stroke-dasharray":"2 2"}));}
    ring(x,y,8.4,colFor(c)); bump(c);
    if(e==="solo"){ const t=el("text",{x,y:y+21,fill:cvar('--faint'),"font-size":9,"text-anchor":"middle","font-style":"italic"}); t.textContent="effort unique"; s.appendChild(t); } });}
  s.appendChild(el("circle",{cx:px("opus-4.8"),cy:py("medium"),r:11.5,fill:"none",stroke:cvar('--opus48'),"stroke-width":1.6,"stroke-dasharray":"1 2"}));
  document.getElementById("graphcap").innerHTML=`<b>5 modèles à effort discret × 5 efforts</b> + <b>Haiku&nbsp;4.5 en point unique</b> (pas de paramètre <code>effort</code> → toutes ses sources fusionnées en un nœud, voir §6&nbsp;; ligne « défaut » retirée&nbsp;; les runs @default alimentent les IC de la matrice §2). Anneau = <b>#sources indépendantes</b>&nbsp;: <b><span style="color:${COLR.g}">vert ≥3</span></b> · <b><span style="color:${COLR.y}">jaune 2</span></b> · <b><span style="color:${COLR.o}">orange 1</span></b> · <b><span style="color:${COLR.r}">rouge 0</span></b> (bilan ${tally.g}/${tally.y}/${tally.o}/${tally.r}). Nœud <b>plein</b> = mesuré, <b>creux</b> = inféré. Épaisseur d'arête ∝ #sources.`;
  document.getElementById("legendG").innerHTML=
    `<span class="lg"><span class="sw" style="border:2.4px solid ${COLR.g};border-radius:50%;background:transparent"></span>≥3 sources</span>`
    +`<span class="lg"><span class="sw" style="border:2.4px solid ${COLR.y};border-radius:50%;background:transparent"></span>2</span>`
    +`<span class="lg"><span class="sw" style="border:2.4px solid ${COLR.o};border-radius:50%;background:transparent"></span>1</span>`
    +`<span class="lg"><span class="sw" style="border:2.4px solid ${COLR.r};border-radius:50%;background:transparent"></span>0</span>`
    +`<span class="lg"><span class="sw" style="background:${cvar('--muted')}"></span>lien mesuré</span>`;
}
// ===== RATIO-BY-PAIR assignment charts (cost & tokens); colour = effort, grey = @default =====
const RD=__RATIO_DATA__;
const CONS=__CONS_DATA__;
const EC={low:"#5B8FF0",medium:"#2E9C5A",high:"#D9B23A",xhigh:"#E08A2E",max:"#E0342A",grey:"#9a9a9a"};
const RVIEW={};   // per-axis semantic-zoom window: key `${pair}|${metric}` -> [loLog10, hiLog10]
// One block per model pair: two stacked own-scale log axes (cost on top, tokens below),
// points coloured by effort (grey=@default), IDs above; dashed connector when the same source has both.
function drawRatios(svgId){
  const s=document.getElementById(svgId); if(!s) return; s.innerHTML=""; s.__axes=[];
  const cb={}, tb={};
  RD.cost.forEach(p=>{(cb[p[0]]=cb[p[0]]||[]).push(p);});
  RD.tok.forEach(p=>{(tb[p[0]]=tb[p[0]]||[]).push(p);});
  const grey1=a=>a&&a.some(p=>p[5]===0&&p[2]==="grey");   // show axis only if it has a MEASURED @default to assign
  const pairs=[...new Set([...Object.keys(cb),...Object.keys(tb)])]
    .filter(p=>grey1(cb[p])||grey1(tb[p]))
    .sort((a,b)=>((cb[b]||[]).length-(cb[a]||[]).length)||((tb[b]||[]).length-(tb[a]||[]).length)||a.localeCompare(b));
  const W=780, mT=8, aX0=150, aX1=W-24, axGap=52, L=Math.log10;
  const TC=[0.1,0.15,0.2,0.25,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1,1.2,1.5,2,2.5,3,4,5,6,7,8,10,12,15,20,25,30,40,50];
  // key `${pair}|${metric}` : RVIEW override (semantic zoom) → [loLog,hiLog], else data-derived
  function axis(pts,yA,cons,key){
    if(!grey1(pts)) return null;
    let loL,hiL;
    if(RVIEW[key]){ [loL,hiL]=RVIEW[key]; }
    else { const vals=pts.map(p=>p[1]).concat(cons.map(c=>c[1]));
      let lo=Math.min(...vals), hi=Math.max(...vals);
      if(lo===hi){lo*=0.7;hi*=1.4;} else {const f=hi/lo; lo/=Math.pow(f,0.07); hi*=Math.pow(f,0.07);}
      loL=L(lo); hiL=L(hi); }
    s.__axes.push({key,yA,x0:aX0,x1:aX1,loL,hiL});         // hitbox for zoom/pan
    const X=v=>aX0+(L(v)-loL)/(hiL-loL)*(aX1-aX0);
    const inR=x=>x>=aX0-4&&x<=aX1+4;
    s.appendChild(el("line",{x1:aX0,y1:yA,x2:aX1,y2:yA,stroke:cvar('--muted'),"stroke-width":1,"stroke-opacity":.5}));
    let ticks=TC.filter(t=>L(t)>=loL&&L(t)<=hiL);
    if(ticks.length>6){ const step=Math.ceil(ticks.length/6); ticks=ticks.filter((_,k)=>k%step===0); }
    if(ticks.length<2) ticks=[+Math.pow(10,loL).toPrecision(2),+Math.pow(10,hiL).toPrecision(2)];
    ticks.forEach(t=>{ s.appendChild(el("line",{x1:X(t),y1:yA-3,x2:X(t),y2:yA+3,stroke:cvar('--faint'),"stroke-width":1}));
      const tx=el("text",{x:X(t),y:yA+14,fill:cvar('--faint'),"font-size":9,"text-anchor":"middle"});tx.textContent=t+"×";s.appendChild(tx);});
    cons.forEach(c=>{ const x=X(c[1]); if(!inR(x))return;
      const sq=el("rect",{x:x-6,y:yA-6,width:12,height:12,rx:1.5,fill:EC[c[0]],"fill-opacity":.32,stroke:EC[c[0]],"stroke-width":1.4});
      const ti=document.createElementNS(NS,"title");ti.textContent=`médiane mesurée ${c[0]} = ${c[1]}×`;sq.appendChild(ti);s.appendChild(sq); });
    const pos={};
    pts.slice().sort((a,b)=>a[1]-b[1]).forEach(p=>{ const x=X(p[1]); if(!inR(x))return; const derived=p[5]===1, grey=p[2]==="grey";
      const c=el("circle",{cx:x,cy:yA,r:4.4,fill:derived?"none":EC[p[2]],stroke:derived?EC[p[2]]:cvar('--panel'),"stroke-width":derived?1.6:1,"stroke-dasharray":derived?"2 1.5":"none"});
      const ti=document.createElementNS(NS,"title");ti.textContent=`${p[4]}${derived?" (dérivé via prix)":""} · ${p[0]} · ${p[1]}× · ${p[2]} · ${p[3]}`;c.appendChild(ti);s.appendChild(c);
      if(grey){ const it=el("text",{x:x,y:yA-8,fill:cvar('--ink'),"font-size":7.5,"text-anchor":"middle","font-weight":700});it.textContent=p[4];s.appendChild(it); }
      pos[p[4]]=x; });
    return pos;
  }
  let y=mT;
  pairs.forEach((pair,ri)=>{ const top=y;
    const cons=CONS[pair]||[];
    const consC=cons.filter(r=>r[1]!=null).map(r=>[r[0],r[1]]), consT=cons.filter(r=>r[2]!=null).map(r=>[r[0],r[2]]);
    if(ri) s.appendChild(el("line",{x1:0,y1:top,x2:W,y2:top,stroke:cvar('--line'),"stroke-width":1,"stroke-opacity":.35}));
    const lb=el("text",{x:8,y:top+18,fill:cvar('--ink'),"font-size":11,"font-weight":700});lb.textContent=pair;s.appendChild(lb);
    let ay=top+36, yC=null,yT=null,cp=null,tp=null;
    if(grey1(cb[pair])){ yC=ay; const t=el("text",{x:aX0-8,y:yC+3.5,fill:cvar('--faint'),"font-size":9,"text-anchor":"end"});t.textContent="coût";s.appendChild(t); cp=axis(cb[pair],yC,consC,pair+"|cost"); ay+=axGap; }
    if(grey1(tb[pair])){ yT=ay; const t=el("text",{x:aX0-8,y:yT+3.5,fill:cvar('--faint'),"font-size":9,"text-anchor":"end"});t.textContent="tok";s.appendChild(t); tp=axis(tb[pair],yT,consT,pair+"|tok"); ay+=axGap; }
    if(cp&&tp){ for(const k in cp){ if(k in tp){
      s.appendChild(el("line",{x1:cp[k],y1:yC+7,x2:tp[k],y2:yT-7,stroke:cvar('--faint'),"stroke-width":1.2,"stroke-opacity":.7,"stroke-dasharray":"2 2"})); } } }
    y=ay+8;
  });
  s.setAttribute("viewBox",`0 0 ${W} ${y+2}`);
}
// §4 semantic zoom, per axis: Shift+wheel zooms the ratio domain around the cursor, drag pans, dbl-click resets.
function enableRatioZoom(svg){
  if(svg.__rz) return; svg.__rz=true; svg.style.touchAction="none"; svg.style.userSelect="none"; svg.style.webkitUserSelect="none";
  const pt=e=>{ const r=svg.getBoundingClientRect(), v=svg.getAttribute("viewBox").split(/[ ,]+/).map(Number);
    return [v[0]+(e.clientX-r.left)/r.width*v[2], v[1]+(e.clientY-r.top)/r.height*v[3]]; };
  const near=(cx,cy)=>{ let b=null,bd=24; (svg.__axes||[]).forEach(a=>{ const d=Math.abs(cy-a.yA);
    if(d<bd && cx>=a.x0-48 && cx<=a.x1+8){bd=d;b=a;} }); return b; };
  svg.addEventListener("wheel",e=>{ if(!e.shiftKey) return; e.preventDefault();
    const [cx,cy]=pt(e), a=near(cx,cy); if(!a) return;
    const fr=Math.max(0,Math.min(1,(cx-a.x0)/(a.x1-a.x0))), curL=a.loL+fr*(a.hiL-a.loL);
    const span=(a.hiL-a.loL)*(e.deltaY<0?0.8:1.25);
    RVIEW[a.key]=[curL-fr*span, curL+(1-fr)*span]; drawRatios(svg.id); },{passive:false});
  let d=null;
  svg.addEventListener("pointerdown",e=>{ const [cx,cy]=pt(e), a=near(cx,cy); if(!a) return; e.preventDefault(); d={a,x:cx}; svg.style.cursor="grabbing"; svg.setPointerCapture(e.pointerId); });
  svg.addEventListener("pointermove",e=>{ if(!d) return; const [cx]=pt(e), a=d.a, span=a.hiL-a.loL;
    const dL=-(cx-d.x)/(a.x1-a.x0)*span; RVIEW[a.key]=[a.loL+dL,a.hiL+dL]; drawRatios(svg.id); const na=(svg.__axes||[]).find(z=>z.key===a.key); if(na){d.a=na; d.x=cx;} });
  const up=()=>{ d=null; svg.style.cursor=""; }; svg.addEventListener("pointerup",up); svg.addEventListener("pointercancel",up);
  svg.addEventListener("dblclick",e=>{ const [cx,cy]=pt(e), a=near(cx,cy); if(a){ delete RVIEW[a.key]; drawRatios(svg.id); } });
}
function drawRatiosLegend(){ const L=document.getElementById("legendR"); if(!L) return;
  L.innerHTML=["low","medium","high","xhigh","max","grey"].map(k=>`<span class="lg"><span class="sw" style="background:${EC[k]}"></span>${k==="grey"?"@default (à assigner, avec ID)":k}</span>`).join("")
    +`<span class="lg"><span class="sw" style="background:var(--muted);opacity:.35;border-radius:2px"></span>carré = médiane des mesures / effort</span>`
    +`<span class="lg"><span class="sw" style="border:1.6px dashed var(--muted);background:transparent;border-radius:50%"></span>creux = dérivé via prix/token</span>`
    +`<span class="lg"><span class="sw" style="border-top:1.4px dashed var(--faint);background:transparent;height:0"></span>même source (coût↔tok)</span>`; }

function drawEdgeTable(){
  const tb=document.querySelector("#edge-tbl tbody"); tb.innerHTML="";
  const short=x=>{const[m,e]=x.split("@");return (GMODEL[m]?GMODEL[m].l:m)+"·"+e;};
  const cur=x=>{const m=x.split("@")[0];return GMODEL[m]&&GMODEL[m].cur;};
  GROUPS.slice().filter(g=>g.n.some(cur))   // drop legacy-only sources (HAL, PostTrain, whitekumalabo)
    .sort((a,b)=>a.t.localeCompare(b.t)||a.g.localeCompare(b.g)).forEach(g=>{
    const cn=g.n.filter(cur);
    const tr=document.createElement("tr");
    tr.innerHTML=`<td><b>${g.g}</b><br><span class="faint" style="font-size:10px">${g.s}</span></td>`
      +`<td style="font-size:11px">${g.h||"—"}</td>`
      +`<td><span class="etag" style="background:${GCOL[g.t]}">${g.t}</span></td>`
      +`<td>${cn.map(short).join(" · ")}</td>`;
    tb.appendChild(tr);});
}
// ---- pan/zoom (viewBox-based, no external lib) : Ctrl/⌘+wheel zoom · drag pan · +/−/⟳ buttons ----
function zoomable(svg){
  const box=svg.parentNode; box.style.position="relative";
  const vb=()=>svg.getAttribute("viewBox").split(/[ ,]+/).map(Number);
  const set=(x,y,w,h)=>svg.setAttribute("viewBox",`${x} ${y} ${w} ${h}`);
  if(!box.querySelector(".zoomctl")){
    const tb=document.createElement("div"); tb.className="zoomctl";
    tb.innerHTML='<button data-z="in" title="Zoom +">+</button><button data-z="out" title="Zoom −">−</button><button data-z="reset" title="Réinitialiser">⟳</button>';
    tb.addEventListener("click",e=>{ const z=e.target.getAttribute("data-z"); if(!z)return;
      if(z==="reset"){ svg.setAttribute("viewBox",svg.__base); return; }
      const [x,y,w,h]=vb(), f=z==="in"?0.8:1.25; set(x+(w-w*f)/2, y+(h-h*f)/2, w*f, h*f); });
    box.appendChild(tb);
  }
  if(svg.__zoom) return; svg.__zoom=true; svg.style.cursor="grab"; svg.style.userSelect="none"; svg.style.webkitUserSelect="none";
  svg.addEventListener("wheel",e=>{ if(!e.shiftKey) return; e.preventDefault();   // Shift+wheel (Ctrl/⌘ = browser zoom, avoided)
    const [x,y,w,h]=vb(), r=svg.getBoundingClientRect();
    const mx=x+(e.clientX-r.left)/r.width*w, my=y+(e.clientY-r.top)/r.height*h, f=e.deltaY<0?0.9:1.11;
    set(mx-(mx-x)*f, my-(my-y)*f, w*f, h*f); },{passive:false});
  let d=null;
  svg.addEventListener("pointerdown",e=>{ e.preventDefault(); d={x:e.clientX,y:e.clientY,vb:vb()}; svg.style.cursor="grabbing"; svg.setPointerCapture(e.pointerId); });
  svg.addEventListener("pointermove",e=>{ if(!d)return; const [x,y,w,h]=d.vb, r=svg.getBoundingClientRect();
    set(x-(e.clientX-d.x)/r.width*w, y-(e.clientY-d.y)/r.height*h, w, h); });
  const up=()=>{ d=null; svg.style.cursor="grab"; };
  svg.addEventListener("pointerup",up); svg.addEventListener("pointercancel",up); svg.addEventListener("pointerleave",up);
}
function renderAll(){drawB();drawMatrix();drawGraph();drawEdgeTable();drawRatiosLegend();drawRatios('chartR');
  ['chartB','chartG'].forEach(id=>{ const sv=document.getElementById(id); if(sv){ sv.__base=sv.getAttribute("viewBox"); zoomable(sv); } });
  const rr=document.getElementById('chartR'); if(rr) enableRatioZoom(rr);}
renderAll();
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',renderAll);
new MutationObserver(renderAll).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
