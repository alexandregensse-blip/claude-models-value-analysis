const MODELS = __MODELS__;   // data/catalog/models.json: label, colour variable, task-size flag, in legend order
const LEGACY=["opus-4.7","sonnet-4.6"];                         // older models: hidden unless the reader turns them on
const cvar = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const NS="http://www.w3.org/2000/svg";
const el=(n,a={})=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);return e;};
// round-value axis ticks (regular VALUES, not regular screen spacing)
const logTicks=(vmin,vmax)=>{const o=[];for(let e=Math.floor(Math.log10(vmin));Math.pow(10,e)<=vmax*1.0001;e++)for(let b=1;b<=9;b++){const v=b*Math.pow(10,e);if(v>=vmin*0.999&&v<=vmax*1.001)o.push(v);}return o;};
const tickLbl=v=>{const m=Math.round(v/Math.pow(10,Math.floor(Math.log10(v)+1e-9)));return m===1||m===2||m===5;};
const linTicks=(lo,hi,target)=>{const raw=(hi-lo)/target,mag=Math.pow(10,Math.floor(Math.log10(raw))),n=raw/mag,step=(n<1.5?1:n<3?2:n<7?5:10)*mag,o=[];for(let t=Math.ceil(lo/step)*step;t<=hi+1e-9;t+=step)o.push(Math.round(t*1e4)/1e4);return o;};
// Normal CDF (Abramowitz & Stegun 7.1.26, error below 1.5e-7): the probability that one couple beats another.
const Phi=z=>{ const x=Math.abs(z)/Math.SQRT2, k=1/(1+0.3275911*x),
  e=1-((((1.061405429*k-1.453152027)*k+1.421413741)*k-0.284496736)*k+0.254829592)*k*Math.exp(-x*x); return z>=0?(1+e)/2:(1-e)/2; };

// The fitted values, reference-free (model/fit-cache.json through site/grids.py), published couples only:
//   COSTGRID {model:{effort:[ln cost, quasi-standard error]}}: cost on a task of typical size;
//   QUALGRID {model:{effort:[θ, quasi-standard error]}}: θ the latent quality, on the model's logit scale.
// The quasi-standard error is the half-width of the couple's own 16–84 % interval: two couples compare through their two
// intervals. No couple is a reference: the page counts cost from the cheapest couple shown and reads θ as an expected
// panel score (PANEL). Every decision (frontier, trend, tiers, crown) is taken on ln cost and θ.
const COSTGRID=__COSTGRID__;
const QUALGRID=__QUALGRID__;
// PANEL = [[θ, expected score]]: the expected score, averaged over the benchmark panel, of a couple of latent quality θ
// (posterior median, no couple-specific effect). It only LABELS θ; read linearly in logit between its nodes.
const PANEL=__PANEL__;
const lgt=s=>Math.log(s/(1-s)), expit=x=>1/(1+Math.exp(-x));
function score(t){ let i=1; while(i<PANEL.length-1&&PANEL[i][0]<t) i++;
  const [t0,s0]=PANEL[i-1], [t1,s1]=PANEL[i]; return expit(lgt(s0)+(lgt(s1)-lgt(s0))*(t-t0)/(t1-t0)); }
function scoreInv(s){ let lo=PANEL[0][0]-100, hi=PANEL[PANEL.length-1][0]+100;   // the score rises with θ
  for(let k=0;k<60;k++){ const m=(lo+hi)/2; if(score(m)<s) lo=m; else hi=m; } return (lo+hi)/2; }
const pct=s=>(100*s).toFixed(1)+" %";
const fmtX=v=>(v<10?v.toFixed(1):v.toFixed(0))+"×";
// Every shown couple: x = ln cost, t = θ (hx, ht their quasi-standard errors); c = cost as a multiple of the cheapest
// couple shown, [clo, chi] its interval; [tlo, thi] the interval of θ; s = the expected panel score of θ.
function couples(){ const rows=[];
  for(const m in COSTGRID){ const cg=COSTGRID[m], qg=QUALGRID[m]||{};
    for(const e in cg){ const q=qg[e]; if(q) rows.push({m,e,x:cg[e][0],hx:cg[e][1],t:q[0],ht:q[1]}); } }
  const x0=Math.min(...rows.map(p=>p.x));
  rows.forEach(p=>{ p.c=Math.exp(p.x-x0); p.clo=p.c*Math.exp(-p.hx); p.chi=p.c*Math.exp(p.hx); p.tlo=p.t-p.ht; p.thi=p.t+p.ht; p.s=score(p.t); });
  return rows; }
// PARETO FRONTIER. By centres, a couple is dominated when another costs no more and scores no less (strictly better on
// one). With the intervals, a couple is WITHIN REACH of the frontier unless another couple beats it on both axes with
// probability REACH or more: P(θ higher) × P(cost lower), each a normal law on the difference of the two centres with
// the two quasi-standard errors (the two axes are fitted separately). REACH = 0.84, the level of the intervals shown
// everywhere: a couple beaten by a hair stays a candidate. The frontier by centres is always within reach.
const REACH=0.84;
function frontier(rows){ const E=1e-9, dom=(o,p)=>o.x<=p.x+E&&o.t>=p.t-E&&(o.x<p.x-E||o.t>p.t+E);
  const pDom=(o,p)=>Phi((o.t-p.t)/Math.hypot(o.ht,p.ht))*Phi((p.x-o.x)/Math.hypot(o.hx,p.hx));
  rows.forEach(p=>{ p.front=!rows.some(o=>dom(o,p)); p.reach=!rows.some(o=>o!==p&&pDom(o,p)>=REACH); });
  return {front:rows.filter(p=>p.front).sort((a,b)=>a.x-b.x), reach:rows.filter(p=>p.reach).sort((a,b)=>a.x-b.x)}; }
// PRICE TREND: what a given quality typically costs, fitted on EVERY shown couple (the trend of the models, not the
// frontier): ln cost = a + λ·θ, least squares weighted by each couple's uncertainty across the line, 1/(hx² + λ²·ht²)
// (both axes are uncertain: effective variance), iterated to its fixed point. λ is the market's price of quality: one
// more unit of θ costs e^λ times more. Kept ≥ 0: quality never gets cheaper as it rises.
function fitTrend(rows){ let a=0, l=0;
  for(let it=0; it<100; it++){ let S=0,St=0,Sx=0,Stt=0,Stx=0;
    rows.forEach(p=>{ const w=1/(p.hx*p.hx+l*l*p.ht*p.ht); S+=w; St+=w*p.t; Sx+=w*p.x; Stt+=w*p.t*p.t; Stx+=w*p.t*p.x; });
    const l2=Math.max(0,(S*Stx-St*Sx)/(S*Stt-St*St)); a=(Sx-l2*St)/S; const done=Math.abs(l2-l)<1e-12; l=l2; if(done) break; }
  const w=rows.map(p=>1/(p.hx*p.hx+l*l*p.ht*p.ht)), sw=w.reduce((u,v)=>u+v,0), xm=rows.reduce((u,p,i)=>u+w[i]*p.x,0)/sw;
  const R2=1-rows.reduce((u,p,i)=>u+w[i]*(p.x-a-l*p.t)**2,0)/rows.reduce((u,p,i)=>u+w[i]*(p.x-xm)**2,0);
  return {a,l,R2,at:t=>a+l*t}; }
// VALUE: how much cheaper a couple is than the trend charges for its quality, r = trend(θ) − ln cost, shown as e^r
// times cheaper (or e^−r times dearer). The same gap read on the quality axis is r/λ: the couple's θ above what the
// trend gives for its cost, shown in points of expected score.
const valueOf=(tr,p)=>tr.at(p.t)-p.x;
const vWord=r=>`${fmtX(Math.exp(Math.abs(r)))} ${r>=0?"cheaper":"dearer"}`;
// VALUE INDEX: 100·e^r — 100 is the trend, 500 five times cheaper than the trend at that quality, 50 twice as dear.
const vIndex=r=>Math.round(100*Math.exp(r));
const qGain=(tr,p)=>tr.l>0?100*(p.s-score(p.t-valueOf(tr,p)/tr.l)):0;   // points of expected score above the trend

// Older-model toggle: the grids keep a full copy; hiding a model removes it from every view and every fit
// (frontier, price curve, tiers, matrix), exactly as if it had not been measured.
const GRID_ALL={cost:{...COSTGRID},qual:{...QUALGRID}};
let showLegacy=false; try{ showLegacy=localStorage.getItem("showLegacy")==="1"; }catch(e){}
function applyLegacy(){ LEGACY.forEach(m=>{ if(showLegacy){ if(GRID_ALL.cost[m]) COSTGRID[m]=GRID_ALL.cost[m]; if(GRID_ALL.qual[m]) QUALGRID[m]=GRID_ALL.qual[m]; }
  else { delete COSTGRID[m]; delete QUALGRID[m]; } }); }
const visibleModels=()=>Object.keys(MODELS).filter(m=>showLegacy||!LEGACY.includes(m));
let showBands=false; try{ showBands=localStorage.getItem("showTierBands")==="1"; }catch(e){}
let showOvals=false; try{ showOvals=localStorage.getItem("showOvals")==="1"; }catch(e){}
// On/off switch (role=switch): a track + knob and an explicit ON/OFF word, so the state reads without colour.
const tgl=(id,on,label,hint,fn)=>`<button type="button" role="switch" class="tgl" id="${id}" aria-checked="${on}" onclick="${fn}()">`
  +`<span class="tgl-track" aria-hidden="true"><span class="tgl-knob"></span></span><span class="tgl-state">${on?"ON":"OFF"}</span>`
  +`<span class="tgl-label">${label}</span>${hint?`<span class="tgl-hint">${hint}</span>`:""}</button>`;
function renderControls(){
  const legacy=id=>tgl(id,showLegacy,"Older models","Opus 4.7 · Sonnet 4.6","toggleLegacy");
  const b=document.getElementById("ctrlB"), p=document.getElementById("ctrlP");
  const ovals=id=>tgl(id,showOvals,"Uncertainty ovals","","toggleOvals");
  const bands=id=>tgl(id,showBands,"Tier bands","","toggleBands");
  if(b) b.innerHTML=`<span class="cc-k">Display</span>`+legacy("tgl-legacy-b")+ovals("tgl-ovals-b")+bands("tgl-bands-b");
  if(p) p.innerHTML=`<span class="cc-k">Display</span>`+legacy("tgl-legacy-p")+ovals("tgl-ovals-p")+bands("tgl-bands-p");
}
function toggleOvals(){ const fid=document.activeElement?.id; showOvals=!showOvals; try{ localStorage.setItem("showOvals",showOvals?"1":"0"); }catch(e){}
  renderControls(); drawB(); drawPareto(); ['chartB','chartP'].forEach(id=>{ const sv=document.getElementById(id); if(sv) zoomable(sv); });
  if(fid) document.getElementById(fid)?.focus(); }
function toggleBands(){ const fid=document.activeElement?.id; showBands=!showBands; try{ localStorage.setItem("showTierBands",showBands?"1":"0"); }catch(e){}
  renderControls(); drawB(); drawPareto(); ['chartB','chartP'].forEach(id=>{ const sv=document.getElementById(id); if(sv) zoomable(sv); });
  if(fid) document.getElementById(fid)?.focus(); }
function toggleLegacy(){ const fid=document.activeElement?.id; showLegacy=!showLegacy; try{ localStorage.setItem("showLegacy",showLegacy?"1":"0"); }catch(e){} applyLegacy(); tierDefaults(); renderAll(); if(fid) document.getElementById(fid)?.focus(); }
applyLegacy();

// ============ shared chart helpers (used by both the landscape §1 and the Pareto) ============
// Quality axis: θ itself (the scale every decision uses), labelled in expected panel score. Below the weakest tier target
// (couples short of today's level) θ is compressed LOW_SQUEEZE times, so older and weaker models sit together at the
// bottom instead of stretching the axis; above it the scale is left as it is.
const LOW_SQUEEZE=3;
const yOf=t=>{ const t0=TIERQ.lo; return t>=t0?t:t0+(t-t0)/LOW_SQUEEZE; };
// Zoom/pan work in the axes' SCREEN-LINEAR coordinates: X is linear in log10(cost), Y in yOf(θ).
// A chart's "view" = [xlo,xhi (log-cost), ylo,yhi (yOf θ)]. Default = data bounds; a stored s.__view overrides it,
// so zoom re-renders the chart (ticks + labels recompute at fixed size) instead of scaling the whole SVG.
const defView=(xmn,xmx,tmn,tmx)=>{ const a=yOf(tmn), b=yOf(tmx), p=0.03*(b-a); return [Math.log10(xmn)-0.06,Math.log10(xmx)+0.06,a-p,b+p]; };
const viewAxes=(v,mL,iw,mT,ih,yp)=>({
  X:val=>mL+(Math.log10(val)-v[0])/(v[1]-v[0])*iw,
  Y:t=>mT+yp+(1-(yOf(t)-v[2])/(v[3]-v[2]))*(ih-2*yp) });
// Two-line axis title: big main label + small precision on the next line (a second tspan; under rotation it sits
// alongside, toward the plot). rot = optional transform string.
function axisTitle(s,x,y,main,sub,rot){
  const t=el("text",{x,y,fill:cvar('--muted'),"text-anchor":"middle"}); if(rot) t.setAttribute("transform",rot);
  const a=el("tspan",{x,"font-size":15,"font-weight":700}); a.textContent=main; t.appendChild(a);
  const b=el("tspan",{x,dy:15,"font-size":10.5,fill:cvar('--faint'),"font-weight":400}); b.textContent=sub; t.appendChild(b);
  s.appendChild(t);
}
// Quality gridlines at round expected scores: every 5 points, or 10 when they fall too close.
function qGrid(s,Y,mL,iw,mT,ih){
  const at=st=>{ const o=[]; for(let k=1;k*st<0.9999;k++){ const v=Math.round(k*st*1000)/1000, y=Y(scoreInv(v)); if(y>=mT-0.5&&y<=mT+ih+0.5) o.push([v,y]); } return o; };
  let st=0.05, g=at(st); const gaps=g.slice(1).map((u,i)=>Math.abs(u[1]-g[i][1])).sort((a,b)=>a-b), med=gaps.length?gaps[gaps.length>>1]:99;
  if(med<16){ st=0.10; g=at(st); }
  let last=-1e9; g=g.filter(([v,y])=>Math.abs(y-last)>=16?(last=y,true):false);   // the compressed low end: skip lines closer than 16 px
  g.forEach(([v,y])=>{ s.appendChild(el("line",{x1:mL,y1:y,x2:mL+iw,y2:y,stroke:cvar('--line'),"stroke-width":1}));
    const t=el("text",{x:mL-9,y:y+4,fill:cvar('--faint'),"font-size":10.5,"text-anchor":"end"}); t.textContent=Math.round(100*v)+"%"; s.appendChild(t); }); }
// Asymmetric interval ovals (per-side radii from [clo,chi]×[qlo,qhi]), centred on the point, clipped
// to the plot, faint by default. Returns the array used by hoverTip() to reveal them.
function drawOvals(s,pts,X,Y,mL,iw,mT,ih,cid){ const defs=el("defs"), cp=el("clipPath",{id:cid});
  cp.appendChild(el("rect",{x:mL,y:mT,width:iw,height:ih})); defs.appendChild(cp); s.appendChild(defs);
  const gEll=el("g",{"clip-path":`url(#${cid})`}); s.appendChild(gEll); const ells=[], byM={};
  pts.forEach(p=>(byM[p.m]=byM[p.m]||[]).push(p));
  for(const m in byM){ const col=cvar(MODELS[m].c); byM[m].forEach(p=>{ if(p.clo==null) return; const cx=X(p.c), cy=Y(p.t),
      rxR=Math.max(X(p.chi)-cx,0.6), rxL=Math.max(cx-X(p.clo),0.6), ryU=Math.max(cy-Y(p.thi),0.6), ryD=Math.max(Y(p.tlo)-cy,0.6);
    const d=`M ${cx} ${cy-ryU} A ${rxR} ${ryU} 0 0 1 ${cx+rxR} ${cy} A ${rxR} ${ryD} 0 0 1 ${cx} ${cy+ryD} A ${rxL} ${ryD} 0 0 1 ${cx-rxL} ${cy} A ${rxL} ${ryU} 0 0 1 ${cx} ${cy-ryU} Z`;
    const elp=el("path",{d,fill:col,"fill-opacity":0.4,stroke:col,"stroke-opacity":0.85,"stroke-width":1,opacity:0.15});
    gEll.appendChild(elp); ells.push({el:elp,cx,cy,rxR,rxL,ryU,ryD}); }); }
  return ells; }
// Hover: reveal ovals under the cursor + a compact tooltip when the cursor is right on a point.
function hoverTip(s,ells,pts,X,Y,mL,iw){ const DEF=0.15,HOV=0.78;
  const tip=el("g",{"pointer-events":"none",opacity:0}), trect=el("rect",{rx:3,fill:cvar('--panel'),stroke:cvar('--line'),"stroke-width":1,"fill-opacity":0.97});
  const ttxt=el("text",{"font-size":9.5,"font-weight":600,"text-anchor":"middle"}); tip.appendChild(trect); tip.appendChild(ttxt); s.appendChild(tip);
  const capE=e=>e==="solo"?"solo":e==="xhigh"?"xHigh":e.charAt(0).toUpperCase()+e.slice(1);
  s.onmousemove=ev=>{ const P=new DOMPoint(ev.clientX,ev.clientY).matrixTransform(s.getScreenCTM().inverse());
    ells.forEach(o=>{ const dx=P.x-o.cx, dy=P.y-o.cy, rx=dx>0?o.rxR:o.rxL, ry=dy>0?o.ryD:o.ryU; o.el.setAttribute("opacity",((dx/rx)**2+(dy/ry)**2<=1)?HOV:DEF); });
    let best=null,bd=49; pts.forEach(p=>{ const d2=(P.x-X(p.c))**2+(P.y-Y(p.t))**2; if(d2<bd){bd=d2;best=p;} });
    if(best){ ttxt.setAttribute("fill",cvar(MODELS[best.m].c)); ttxt.setAttribute("x",Math.min(Math.max(X(best.c),mL+52),mL+iw-52)); ttxt.setAttribute("y",Y(best.t)-11);
      ttxt.textContent=`${MODELS[best.m].label} · ${capE(best.e)} — cost ${fmtC(best.c)}× · score ${pct(best.s)}`;
      const bb=ttxt.getBBox(); trect.setAttribute("x",bb.x-4); trect.setAttribute("y",bb.y-2); trect.setAttribute("width",bb.width+8); trect.setAttribute("height",bb.height+4); tip.setAttribute("opacity",1); }
    else tip.setAttribute("opacity",0); };
  s.onmouseleave=()=>{ ells.forEach(o=>o.el.setAttribute("opacity",DEF)); tip.setAttribute("opacity",0); }; }
// Force-directed label layout: labels drift away from the local point barycentre, from other points, from line
// segments (so they never sit on a curve) and from each other (bias = vector between anchor points); soft spring
// to their own anchor. labs = [{ax,ay,lx,ly,t,col,lead,w,h,fs,mdl}]. Draws leader lines + text.
function placeLabels(s,labs,ppix,segs,W,mL,mT,ih){
  const segVec=(px,py,ax,ay,bx,by)=>{ const dx=bx-ax,dy=by-ay,L2=dx*dx+dy*dy; let t=L2?((px-ax)*dx+(py-ay)*dy)/L2:0; t=t<0?0:t>1?1:t; return [px-(ax+t*dx),py-(ay+t*dy)]; };
  const own=(Q,L)=>Q.x===L.ax&&Q.y===L.ay;
  for(let it=0; it<300; it++){
    labs.forEach(L=>{ let fx=0,fy=0, bx=0,by=0,n=0;
      ppix.forEach(Q=>{ if(Math.hypot(Q.x-L.ax,Q.y-L.ay)<72){ bx+=Q.x; by+=Q.y; n++; }                       // barycentre over a wider radius
        if(!own(Q,L)){ const dx=L.lx-Q.x, dy=L.ly-Q.y, d=Math.hypot(dx,dy);
          if(d>0&&d<32){ fx+=dx/d*(32-d)/32*1.6; fy+=dy/d*(32-d)/32*1.6; }                                    // strong close repulsion
          else if(d>0&&d<170){ fx+=dx/d*(170-d)/170*0.35; fy+=dy/d*(170-d)/170*0.35; } } });                  // minor repulsion from ALL points
      if(n>1){ bx/=n; by/=n; const dx=L.ax-bx, dy=L.ay-by, d=Math.hypot(dx,dy)||1; fx+=dx/d*0.7; fy+=dy/d*0.7; }
      segs.forEach(g=>{ const v=segVec(L.lx,L.ly,g[0],g[1],g[2],g[3]), d=Math.hypot(v[0],v[1]); if(d<19&&d>0){ fx+=v[0]/d*(19-d)/19*1.5; fy+=v[1]/d*(19-d)/19*1.5; } });
      labs.forEach(P=>{ if(P===L) return;
        if(Math.abs(P.lx-L.lx)<(P.w+L.w)/2 && Math.abs(P.ly-L.ly)<(P.h+L.h)/2){
          let dx=L.ax-P.ax, dy=L.ay-P.ay; if(Math.hypot(dx,dy)<1){ dx=L.lx-P.lx||0.1; dy=L.ly-P.ly; }
          const d=Math.hypot(dx,dy)||1; fx+=dx/d*2.6; fy+=dy/d*2.6; } });
      const tX=L.mdl?L.ax+16+L.w/2:L.ax, tY=L.mdl?L.ay+4:L.ay-9; fx+=(tX-L.lx)*0.03; fy+=(tY-L.ly)*0.03;
      L.nx=L.lx+Math.max(-3,Math.min(3,fx)); L.ny=L.ly+Math.max(-3,Math.min(3,fy)); });
    labs.forEach(L=>{ L.lx=Math.min(Math.max(L.nx,mL+8),W-6-L.w/2); L.ly=Math.min(Math.max(L.ny,mT+8),mT+ih-4); });
  }
  labs.forEach(L=>{ const cyL=L.ly-(L.mdl?4:3), hw=L.w/2+1, hh=L.mdl?8:6;
    if(Math.hypot(L.lx-L.ax,cyL-L.ay)>(L.mdl?18:12)){ const dx=L.ax-L.lx, dy=L.ay-cyL, sc=Math.min(hw/(Math.abs(dx)||1e9),hh/(Math.abs(dy)||1e9));
      s.appendChild(el("line",{x1:L.ax,y1:L.ay,x2:L.lx+dx*sc,y2:cyL+dy*sc,stroke:L.lead,"stroke-width":L.mdl?0.9:0.7,"stroke-opacity":0.4})); }
    const t=el("text",{x:L.lx,y:L.ly,fill:L.col,"font-size":L.fs,"font-weight":600,"text-anchor":"middle"});t.textContent=L.t;s.appendChild(t); }); }

// Tier bands: the four usage tiers of the picker as translucent horizontal bands. A tier owns [its target θ*, the next
// target): the qualities that clear its bar but not the next one's; the outer bands extend half a gap beyond the first
// and last targets. They follow the sliders (TIERS is live).
function tierBandEdges(){ const Tc=TIERS.map(t=>t.t), n=Tc.length, e=[Tc[0]-(Tc[1]-Tc[0])/2];
  for(let i=1;i<n;i++) e.push(Tc[i]); e.push(Tc[n-1]+(Tc[n-1]-Tc[n-2])/2); return e; }
function drawTierBands(s,Y,mL,iw,mT,ih){                                  // translucent fills, drawn UNDER the grid
  const e=tierBandEdges(), n=TIERS.length, g=el("g",{"pointer-events":"none"});
  TIERS.forEach((t,i)=>{ const yA=Math.max(mT,Math.min(mT+ih,Y(e[i+1]))), yB=Math.max(mT,Math.min(mT+ih,Y(e[i])));
    if(yB-yA<1) return;
    g.appendChild(el("rect",{x:mL,y:yA,width:iw,height:yB-yA,fill:TWCOL[i],"fill-opacity":0.10}));
    if(i<n-1) g.appendChild(el("line",{x1:mL,y1:yA,x2:mL+iw,y2:yA,stroke:TWCOL[i],"stroke-opacity":0.35,"stroke-width":1,"stroke-dasharray":"2 5"})); });
  s.appendChild(g);
}
// Same hue, equal PERCEIVED lightness (OKLab L): the four tier colours differ in lightness (0.48–0.68), which made two
// labels look heavier than the others. Labels are re-lit to one L per theme; chroma shrinks if the result leaves sRGB.
function atLightness(hex,L){
  const toLin=c=>{c/=255;return c<=0.04045?c/12.92:((c+0.055)/1.055)**2.4}, toS=c=>{c=Math.max(0,Math.min(1,c));return Math.round(255*(c<=0.0031308?12.92*c:1.055*c**(1/2.4)-0.055))};
  const [R,G,B]=[1,3,5].map(i=>toLin(parseInt(hex.slice(i,i+2),16)));
  const l=Math.cbrt(0.4122214708*R+0.5363137081*G+0.0514459929*B), m=Math.cbrt(0.2119034982*R+0.6806995451*G+0.1073969566*B), q=Math.cbrt(0.0883024619*R+0.2817188376*G+0.6299787005*B);
  const a=1.9779984951*l-2.4285922050*m+0.4505937099*q, b=0.0259040371*l+0.7827717662*m-0.8086757660*q;
  for(let k=1;k>=0;k-=0.05){ const A=a*k, Bb=b*k, l2=(L+0.3963377774*A+0.2158037573*Bb)**3, m2=(L-0.1055613458*A-0.0638541728*Bb)**3, s2=(L-0.0894841775*A-1.2914855480*Bb)**3;
    const rgb=[4.0767416621*l2-3.3077115913*m2+0.2309699292*s2, -1.2684380046*l2+2.6097574011*m2-0.3413193965*s2, -0.0041960863*l2-0.7034186147*m2+1.7076147010*s2];
    if(rgb.every(c=>c>=-1e-4&&c<=1+1e-4)) return "#"+rgb.map(c=>toS(c).toString(16).padStart(2,"0")).join(""); }
  return hex; }
const isDark=()=>{ const h=cvar('--paper'); return /^#/.test(h) && parseInt(h.slice(1,3),16)<100; };
function drawTierBandLabels(s,Y,mL,iw,mT,ih){                             // names: left, opaque, ABOVE the grid (paper halo)
  const e=tierBandEdges(), g=el("g",{"pointer-events":"none"});
  TIERS.forEach((t,i)=>{ const yA=Math.max(mT,Math.min(mT+ih,Y(e[i+1]))), yB=Math.max(mT,Math.min(mT+ih,Y(e[i])));
    if(yB-yA<16) return;
    const tx=el("text",{x:mL+10,y:yB-7,fill:atLightness(TWCOL[i],isDark()?0.80:0.50),"font-size":11.5,"font-weight":700,"text-anchor":"start","letter-spacing":"0.04em",
      stroke:cvar('--panel'),"stroke-width":3,"stroke-linejoin":"round","paint-order":"stroke"});
    tx.textContent=t.name; g.appendChild(tx); });
  s.appendChild(g);
}
// Cost multiples: two significant digits (one decimal below 10, none above), as fine as the Monte Carlo error allows
// (about 0.3 % relative, the cheapest couple's included) and well inside the intervals (about ±10 %).
const fmtC=v=>(v<1?v.toFixed(2):v<10?v.toFixed(1):v.toFixed(0));
function costTicks(s,X,xlo,xhi,mT,ih,dy){ logTicks(Math.pow(10,xlo),Math.pow(10,xhi)).forEach(val=>{ const x=X(val);
  s.appendChild(el("line",{x1:x,y1:mT,x2:x,y2:mT+ih,stroke:cvar('--line'),"stroke-width":1}));
  if(tickLbl(val)){const t=el("text",{x,y:mT+ih+dy,fill:cvar('--faint'),"font-size":10.5,"text-anchor":"middle"});t.textContent=fmtC(val)+"×";s.appendChild(t);}}); }
const AXIS_C=["Cost","multiple of the cheapest couple · log scale"], AXIS_Q=["Quality","expected score on the benchmark panel · latent scale"];
function drawB(){
  const s=document.getElementById("chartB"); s.innerHTML="";
  const W=1100,H=619,mL=66,mR=64,mT=22,mB=72, iw=W-mL-mR, ih=H-mT-mB;   // 16:9, fills body; extra bottom margin so the axis title clears the ticks
  // X = cost multiple, Y = θ, each with its interval. Haiku excluded here. Bounds include the ovals so they stay inside.
  const pts=couples().filter(p=>p.m!=="haiku-4.5");
  const xmn=Math.min(...pts.map(p=>p.clo)), xmx=Math.max(...pts.map(p=>p.chi)), tmn=Math.min(...pts.map(p=>p.tlo)), tmx=Math.max(...pts.map(p=>p.thi));
  const yp=8, view=s.__view||defView(xmn,xmx,tmn,tmx);   // stored view (zoom/pan) overrides the data bounds
  s.__view=view; s.__geo={mL,iw,mT,ih,yp};
  const {X,Y}=viewAxes(view,mL,iw,mT,ih,yp), xlo=view[0], xhi=view[1];
  if(showBands) drawTierBands(s,Y,mL,iw,mT,ih);                          // optional usage-tier fills, under the grid
  costTicks(s,X,xlo,xhi,mT,ih,20);
  qGrid(s,Y,mL,iw,mT,ih);
  if(showBands) drawTierBandLabels(s,Y,mL,iw,mT,ih);                     // tier names over the grid
  axisTitle(s,mL+iw/2,H-30,...AXIS_C);
  axisTitle(s,13,mT+ih/2,...AXIS_Q,`rotate(-90 13 ${mT+ih/2})`);
  const EO=["low","medium","high","xhigh","max"], byM={};
  pts.forEach(p=>{(byM[p.m]=byM[p.m]||[]).push(p);});
  const ells=showOvals?drawOvals(s,pts,X,Y,mL,iw,mT,ih,"clipB"):[];      // optional asymmetric uncertainty ovals, behind
  const segs=[];                                                          // curves + points on top, collect line segments for label repulsion
  for(const m in byM){ const col=cvar(MODELS[m].c), mp=byM[m].slice().sort((a,b)=>EO.indexOf(a.e)-EO.indexOf(b.e));
    s.appendChild(el("path",{d:mp.map((p,i)=>(i?"L":"M")+X(p.c)+" "+Y(p.t)).join(" "),fill:"none",stroke:col,"stroke-width":2.2,"stroke-linejoin":"round"}));
    mp.forEach(p=>s.appendChild(el("circle",{cx:X(p.c),cy:Y(p.t),r:3.6,fill:col,stroke:cvar('--panel'),"stroke-width":1.4})));
    for(let i=0;i<mp.length-1;i++) segs.push([X(mp[i].c),Y(mp[i].t),X(mp[i+1].c),Y(mp[i+1].t)]); }
  const ppix=pts.map(p=>({x:X(p.c),y:Y(p.t)})), labs=[];                  // effort labels + model-name labels, force-directed together
  pts.forEach(p=>labs.push({ax:X(p.c),ay:Y(p.t),lx:X(p.c),ly:Y(p.t)-9,t:p.e,col:cvar(MODELS[p.m].c),lead:cvar(MODELS[p.m].c),w:p.e.length*5.4+4,h:11,fs:8.5,mdl:false}));
  for(const m in byM){ const mp=byM[m].slice().sort((a,b)=>EO.indexOf(a.e)-EO.indexOf(b.e)), last=mp[mp.length-1], w=MODELS[m].label.length*7+6;
    labs.push({ax:X(last.c),ay:Y(last.t),lx:X(last.c)+16+w/2,ly:Y(last.t)+4,t:MODELS[m].label,col:cvar(MODELS[m].c),lead:cvar(MODELS[m].c),w,h:15,fs:12.5,mdl:true}); }
  placeLabels(s,labs,ppix,segs,W,mL,mT,ih);
  hoverTip(s,ells,pts,X,Y,mL,iw);
  const lg=document.getElementById("legendB"); lg.innerHTML=
    visibleModels().filter(m=>m!=="haiku-4.5").map(m=>`<span class="lg"><span class="sw" style="background:${cvar(MODELS[m].c)}"></span>${MODELS[m].label}</span>`).join("")
    +(showOvals?`<span class="lg"><span class="sw" style="opacity:.5;background:transparent;border:1px solid var(--ink);border-radius:50%"></span>oval = the couple's 16–84 % interval · <b>hover a point</b> for its identity</span>`
               :`<span class="lg"><b>hover a point</b> for its identity</span>`);
}

// ---- Dedicated Pareto chart: cost × quality scatter, the frontier joined, the couples within reach marked ----
// Same shared machinery as the §1 landscape: θ axis, faint interval ovals (hover to reveal), point tooltip,
// force-directed labels. Full body width.
const capE=e=>e==="solo"?"solo":e==="xhigh"?"xHigh":e.charAt(0).toUpperCase()+e.slice(1);
function drawPareto(){
  const s=document.getElementById("chartP"); if(!s) return; s.innerHTML="";
  const W=1100,H=619,mL=66,mR=64,mT=20,mB=68, iw=W-mL-mR, ih=H-mT-mB;   // extra bottom margin so the axis title clears the ticks
  const pts=couples(), {front,reach}=frontier(pts), tr=fitTrend(pts);    // all current couples incl. Haiku (solo)
  const xmn=Math.min(...pts.map(p=>p.clo)), xmx=Math.max(...pts.map(p=>p.chi)), tmn=Math.min(...pts.map(p=>p.tlo)), tmx=Math.max(...pts.map(p=>p.thi));
  const yp=10, view=s.__view||defView(xmn,xmx,tmn,tmx);   // stored view (zoom/pan) overrides the data bounds
  s.__view=view; s.__geo={mL,iw,mT,ih,yp};
  const {X,Y}=viewAxes(view,mL,iw,mT,ih,yp), xlo=view[0], xhi=view[1];
  if(showBands) drawTierBands(s,Y,mL,iw,mT,ih);                          // optional usage-tier fills, under the grid
  costTicks(s,X,xlo,xhi,mT,ih,18);
  qGrid(s,Y,mL,iw,mT,ih);
  if(showBands) drawTierBandLabels(s,Y,mL,iw,mT,ih);                     // tier names over the grid
  axisTitle(s,mL+iw/2,H-28,...AXIS_C);
  axisTitle(s,13,mT+ih/2,...AXIS_Q,`rotate(-90 13 ${mT+ih/2})`);
  { const r2el=document.getElementById("pareto-r2"); if(r2el) r2el.textContent=tr.R2.toFixed(2); }
  { const x0=Math.min(...pts.map(p=>p.x)), cLo=Math.pow(10,xlo), cHi=Math.pow(10,xhi); let d="", on=false;   // the trend, edge to edge
    for(let k=0;k<=200;k++){ const t=tmn-20+(tmx-tmn+40)*k/200, cost=Math.exp(tr.at(t)-x0), yy=Y(t);
      if(cost>=cLo&&cost<=cHi&&yy>=mT&&yy<=mT+ih){ d+=(on?"L":"M")+X(cost)+" "+yy+" "; on=true; } else on=false; }
    s.appendChild(el("path",{d,fill:"none",stroke:cvar('--ink'),"stroke-width":1,"stroke-opacity":0.3})); }
  fillScoreTable(reach,tr);
  const ells=showOvals?drawOvals(s,reach,X,Y,mL,iw,mT,ih,"clipP"):[];   // optional; ovals only on the couples within reach
  s.appendChild(el("path",{d:front.map((p,i)=>(i?"L":"M")+X(p.c)+" "+Y(p.t)).join(" "),fill:"none",stroke:cvar('--ink'),"stroke-width":2.2,"stroke-opacity":.7,"stroke-linejoin":"round"}));
  pts.forEach(p=>{ const col=cvar(MODELS[p.m].c);
    s.appendChild(el("circle",p.front?{cx:X(p.c),cy:Y(p.t),r:5.6,fill:col,stroke:cvar('--panel'),"stroke-width":1.3}
      :p.reach?{cx:X(p.c),cy:Y(p.t),r:5.2,fill:col,"fill-opacity":.35,stroke:col,"stroke-width":1.6,"stroke-dasharray":"2 1.6"}
      :{cx:X(p.c),cy:Y(p.t),r:3.4,fill:col,"fill-opacity":.25})); });
  // labels (model · effort) on the couples within reach, force-directed to dodge overlaps and the frontier line
  const ppix=reach.map(p=>({x:X(p.c),y:Y(p.t)})), segs=[];
  for(let i=0;i<front.length-1;i++) segs.push([X(front[i].c),Y(front[i].t),X(front[i+1].c),Y(front[i+1].t)]);
  const labs=reach.map(p=>{ const t=`${MODELS[p.m].label}${p.e==="solo"?"":" · "+capE(p.e)}`, w=t.length*7.2+8;
    return {ax:X(p.c),ay:Y(p.t),lx:X(p.c)+18+w/2,ly:Y(p.t),t,col:cvar(MODELS[p.m].c),lead:cvar(MODELS[p.m].c),w,h:17,fs:13,mdl:true}; });
  placeLabels(s,labs,ppix,segs,W,mL,mT,ih);
  hoverTip(s,ells,pts,X,Y,mL,iw);
  const lg=document.getElementById("legendP");
  if(lg) lg.innerHTML=visibleModels().map(m=>`<span class="lg"><span class="sw" style="background:${cvar(MODELS[m].c)}"></span>${MODELS[m].label}</span>`).join("")
    +`<span class="lg"><span class="sw" style="opacity:.25;background:var(--ink);border-radius:50%"></span>dominated</span>`
    +`<span class="lg"><span class="sw" style="border:1.5px dashed var(--ink);background:transparent;border-radius:50%"></span>within reach of the frontier (not beaten at 84 %)</span>`
    +`<span class="lg"><span class="sw" style="border-top:2.4px solid var(--ink);background:transparent;height:0"></span>Pareto frontier</span>`
    +`<span class="lg"><span class="sw" style="border-top:1.5px solid var(--ink);opacity:.5;background:transparent;height:0"></span>Price trend — what a quality typically costs, over every couple · R² = ${tr.R2.toFixed(2)}</span>`;
  const pb=document.getElementById("pareto-blocks");   // chained mini-blocks (cost order), same style as the tier cards but small
  if(pb) pb.innerHTML=reach.map((p,i)=>`${i?'<span class="pconn">→</span>':''}<span class="pblock" style="border-color:${cvar(MODELS[p.m].c)}${p.front?'':';border-style:dashed'}"><b>${MODELS[p.m].label}</b><span class="pblock-e">${capE(p.e)}</span><span class="pblock-n">${pct(p.s)} · ${fmtC(p.c)}×</span></span>`).join("");
}
// ---- Value table: each couple within reach against the price trend ----
function fillScoreTable(rows,tr){
  const tb=document.querySelector("#score-tbl tbody"); if(!tb) return; tb.innerHTML="";
  rows.map(p=>({...p,r:valueOf(tr,p)})).sort((a,b)=>b.r-a.r).forEach(p=>{ const col=cvar(MODELS[p.m].c),
    // Intensity from the distance to the trend in decades, so 2× cheaper and 2× dearer read equally strong; capped at one decade.
    sc=p.r>=0?cvar('--good'):cvar('--crit'), al=Math.round((0.14+Math.min(Math.abs(p.r)/Math.LN10,1)*0.52)*100),
    pill=`<span class="scorepill" style="background:color-mix(in srgb, ${sc} ${al}%, transparent); color:var(--ink)">${vIndex(p.r)}</span>`;
    const row=document.createElement("tr");
    row.innerHTML=`<td class="mdl"><span class="dot" style="background:${col}"></span>${MODELS[p.m].label} · ${capE(p.e)}${p.front?"":" <span class=\"faint\">(within reach)</span>"}</td>`
      +`<td class="num">${fmtC(p.c)}×</td><td class="num">${pct(p.s)}</td>`
      +`<td style="min-width:96px">${pill}</td>`;
    tb.appendChild(row); }); }
// ---- Tiers: the best value by task complexity; the crown ----
// Four tiers, each with a TARGET quality θ*. Among the couples within reach of the frontier, each tier picks the one
// that maximises
//     window(θ) × e^(λ·θ) ⁄ cost
// λ the slope of the price trend. e^(λθ) ⁄ cost is the couple's value against the trend (the same all along the trend
// line): above its target, a couple wins by bringing more quality than the trend charges for its extra cost, a smooth
// reward with no constant to set. Below the target the Gaussian window e^(−δ²), δ = (θ − θ*) ⁄ σ, penalises the
// shortfall; at or above it the window is 1. Cost is weighed in ratios (log cost), as people perceive prices
// (Weber–Fechner): twice as dear weighs the same at every price.
function logWindow(t,T){ const d=(t-T.t)/T.sig; return d<0?-d*d:0; }
const TWCOL=["#3F8A78","#5B8FF0","#C98A2E","#7C4A6A"];
// t (θ*) and sig below are PLACEHOLDERS: tierDefaults() sets both from the data on load.
const TIERS=[
  {key:"triage",  name:"Grunt work",             t:0, sig:1, ex:"Classification, tagging, extraction, routing, log/PR triage — run at scale, where throughput and unit cost dominate."},
  {key:"everyday",name:"Everyday tasks",         t:0, sig:1, ex:"Routine coding, refactors, unit tests, summaries, first-draft agent steps — solid work that doesn't need the frontier."},
  {key:"pro",     name:"Advanced reasoning",     t:0, sig:1, ex:"Production code review, architecture, hard debugging, customer-facing reasoning — you need essentially flagship quality."},
  {key:"frontier",name:"Cutting-Edge thinking",  t:0, sig:1, ex:"Research-grade reasoning, novel or ambiguous problems, the hardest agentic runs — a few extra points of capability are worth a premium."},
];
// DATA-DERIVED targets. Models improve release after release, so fixed targets would go stale. The four θ* spread
// evenly from (1 − e)·min + e·max to (1 − e)·max + e·min of the frontier's quality (frontier by centres), e = TIER_E:
// the bottom tier follows the weakest frontier couple as it rises, the top one the best, each drawn 5 % of the span
// inward so that no target sits on a single couple. They depend on the couples only through these two bounds.
// σ follows the spacing: adjacent windows cross at half weight midway between their targets, σ = gap ⁄ (2·√ln 2).
const TIER_E=0.05;
let TIERQ={lo:0,hi:1,gap:1,sig:1};
function tierDefaults(){
  const {front}=frontier(couples()); if(!front.length) return;
  const a=Math.min(...front.map(p=>p.t)), b=Math.max(...front.map(p=>p.t)), lo=(1-TIER_E)*a+TIER_E*b, hi=(1-TIER_E)*b+TIER_E*a;
  const gap=(hi-lo)/Math.max(TIERS.length-1,1), sig=gap/(2*Math.sqrt(Math.LN2));
  TIERS.forEach((T,i)=>{ T.t=lo+i*gap; T.sig=sig; });
  TIERQ={lo,hi,gap,sig};
}
tierDefaults();
function tierPicks(){
  const rows=couples(), {reach}=frontier(rows), tr=fitTrend(rows);
  reach.forEach(p=>{ p.r=valueOf(tr,p); p.qg=qGain(tr,p); });
  const tscore=(p,T)=>logWindow(p.t,T)+tr.l*p.t-p.x;                                   // ln(window × e^(λθ) ⁄ cost)
  const picks=TIERS.map(T=>({...T, win:reach.reduce((a,b)=> tscore(b,T) > tscore(a,T) ? b : a)}));
  // CROWN: the couple within reach furthest below the price trend: the most quality for its cost against the going
  // rate. Read on the cost axis, e^r times cheaper than the trend at its quality; on the quality axis, r ⁄ λ above what
  // the trend gives for its cost: the same gap, since the trend is a straight line.
  const crown=reach.reduce((a,b)=> b.r > a.r ? b : a);
  return {picks,crown,tr};
}
function drawTiers(){
  const host=document.getElementById("tier-cards"); if(!host) return;
  const {picks,crown}=tierPicks();
  // noQ → header-mirror cards & the top crown: drop the target prefix, keep the full card layout
  const cardHTML=(T,name,col,w,ex,noQ)=>`<div class="card pad crit tier">
      <div class="tier-head"><span class="tier-name">${noQ?'':`Target ${pct(score(T.t))} – `}${name}</span></div>
      <div class="tier-top">
        <div class="tier-left">
          <span class="tier-pick"><span class="dot" style="background:${col}"></span>${MODELS[w.m].label}${w.e==="solo"?"":" · "+capE(w.e)}</span>
          <span class="tier-nums">Cost <b>${fmtC(w.c)}×</b> · Score <b>${pct(w.s)}</b></span>
        </div>
        <div class="tier-yield">${vIndex(w.r)}</div>
      </div>
      ${ex?`<span class="ex">${ex}</span>`:''}
    </div>`;
  host.innerHTML=picks.map(t=>cardHTML(t,t.name,cvar(MODELS[t.win.m].c),t.win,t.ex,false)).join("");        // detailed cards: keep the target
  const top=document.getElementById("tier-cards-top");
  if(top) top.innerHTML=picks.map(t=>cardHTML(t,t.name,cvar(MODELS[t.win.m].c),t.win,t.ex,true)).join("");   // near-header cards: labels only
  const c=crown, col=cvar(MODELS[c.m].c);
  const crT=document.getElementById("tier-crown-top");   // best overall above the header cards: SAME tier-card layout
  if(crT) crT.innerHTML=cardHTML(null,"👑 Best overall",col,c,"",true);
  const cr=document.getElementById("tier-crown");   // the detailed section keeps the explained crown
  if(cr) cr.innerHTML=`<div class="card pad crown">
      <div class="tier-q">👑 Best overall</div>
      <div class="crown-model"><span class="dot" style="background:${col}"></span>${MODELS[c.m].label}${c.e==="solo"?"":" · "+capE(c.e)}</div>
      <div class="crown-line">Cost <b>${fmtC(c.c)}×</b> · Score <b>${pct(c.s)}</b> · Value index <b>${vIndex(c.r)}</b></div>
      <p class="crown-note"><b>Picked</b> as the couple within reach of the frontier that sits <b>furthest below the price trend</b>&nbsp;: it costs <b>${fmtX(Math.exp(c.r))} less</b> than the trend charges for its quality — or, read on the other axis, it scores <b>${c.qg.toFixed(1)} points</b> of expected score above what the trend gives for its cost. Its <b>value index</b> is that ratio times 100: <b>100 = the trend</b>, fitted on <b>every</b> couple shown, so the going rate of the models, not the frontier; no couple serves as a reference.</p>
    </div>`;
}
// Interactive tuner: draws the four tier windows over the θ axis (labelled in expected score) plus the couples within
// reach as ticks, and a θ*/σ slider pair per tier that live-updates TIERS and re-renders.
// Redraw ONLY the window SVG (called on every slider move) — leaves the slider DOM untouched so dragging keeps working.
function drawTierWindows(){
  const host=document.getElementById("tier-windows"); if(!host) return;
  const {reach}=frontier(couples());
  // Axis spans the targets' range (from tierDefaults) plus half a gap of padding, so the end windows are not clipped.
  const padT=0.5*TIERQ.gap, Tmn=TIERQ.lo-padT, Tmx=TIERQ.hi+padT;
  const W=1100,H=140,mL=8,mR=8,mT=8,mB=24, iw=W-mL-mR, ih=H-mT-mB;
  const X=t=>mL+(t-Tmn)/(Tmx-Tmn)*iw;
  let svg=`<svg viewBox="0 0 ${W} ${H}" class="tuner-svg" role="img" aria-label="Tier windows over the quality axis">`;
  for(let v=0.05; v<0.999; v+=0.05){ const t=scoreInv(Math.round(v*100)/100); if(t<Tmn||t>Tmx) continue; const x=X(t);
    svg+=`<line x1="${x}" y1="${mT}" x2="${x}" y2="${mT+ih}" stroke="${cvar('--line')}" stroke-width="1"/><text x="${x}" y="${mT+ih+15}" fill="${cvar('--faint')}" font-size="10" text-anchor="middle">${Math.round(v*100)}%</text>`; }
  TIERS.forEach((T,i)=>{ const col=TWCOL[i]; let d=`M ${mL} ${mT+ih}`;
    for(let k=0;k<=140;k++){ const t=Tmn+(Tmx-Tmn)*k/140, g=Math.exp(logWindow(t,T)); d+=` L ${X(t).toFixed(1)} ${(mT+ih-g*(ih-8)).toFixed(1)}`; }
    d+=` L ${mL+iw} ${mT+ih} Z`;
    svg+=`<path d="${d}" fill="${col}" fill-opacity="0.06" stroke="${col}" stroke-opacity="0.7" stroke-width="1.3"/>`
       +`<line x1="${X(T.t)}" y1="${mT}" x2="${X(T.t)}" y2="${mT+ih}" stroke="${col}" stroke-width="1" stroke-dasharray="3 3"/>`; });
  reach.forEach(p=>{ if(p.t<Tmn||p.t>Tmx) return; svg+=`<circle cx="${X(p.t)}" cy="${mT+ih}" r="3.2" fill="${cvar(MODELS[p.m].c)}" stroke="${cvar('--panel')}" stroke-width="1"/>`; });
  host.innerHTML=svg+`</svg>`;
}
// Build the tuner ONCE (window container + persistent sliders). Slider input updates state + redraws windows/cards only.
function drawTierTuner(){
  const host=document.getElementById("tier-tuner"); if(!host) return;
  // Slider travel follows the data: θ* spans the padded range the windows are drawn over, σ runs from a quarter to
  // triple its default, so the useful settings sit mid-travel whatever the current spread of models is.
  const padT=0.5*TIERQ.gap, s0=TIERQ.sig;
  const sQ={lo:(TIERQ.lo-padT).toFixed(2), hi:(TIERQ.hi+padT).toFixed(2)}, sS={lo:(0.25*s0).toFixed(2), hi:(3*s0).toFixed(2)};
  let ctl='';
  TIERS.forEach((t,i)=>{ ctl+=`<div class="tuner-row" style="--tw:${TWCOL[i]}"><span class="tuner-name">${t.name}</span>`
    +`<label><span class="lbl">Target</span><input type="range" min="${sQ.lo}" max="${sQ.hi}" step="0.05" value="${t.t}" data-i="${i}" data-k="t"><b id="tv-q-${i}">${pct(score(t.t))}</b></label>`
    +`<label><span class="lbl">σ</span><input type="range" min="${sS.lo}" max="${sS.hi}" step="0.05" value="${t.sig}" data-i="${i}" data-k="sig"><b id="tv-s-${i}">${t.sig.toFixed(2)}</b></label></div>`; });
  host.innerHTML=`<div id="tier-windows"></div><div class="tuner-ctl">${ctl}</div>`;
  drawTierWindows();
  host.querySelectorAll('input[type=range]').forEach(inp=>inp.addEventListener('input',e=>{
    const i=+e.target.dataset.i, k=e.target.dataset.k, v=+e.target.value; TIERS[i][k]=v;
    document.getElementById((k==='t'?'tv-q-':'tv-s-')+i).textContent=k==='t'?pct(score(v)):v.toFixed(2);
    drawTierWindows(); drawTiers(); if(showBands&&k==='t'){ drawB(); drawPareto(); } }));   // only the SVG + cards redraw; the sliders stay in the DOM → drag continues
}
// ---------- MATRIX (sorted by expected score at top effort) — every cell DATA-DRIVEN from COSTGRID / QUALGRID ----------
function drawMatrix(){
  const tb=document.querySelector("#matrix-tbl tbody"); tb.innerHTML="";
  const xs=Object.values(COSTGRID).flatMap(es=>Object.values(es).map(v=>v[0])), x0=Math.min(...xs), cmax=Math.exp(Math.max(...xs)-x0);
  const cell=v=>{ const c=Math.exp(v[0]-x0); return [c, `${fmtC(c*Math.exp(-v[1]))}–${fmtC(c*Math.exp(v[1]))}`]; };
  const topS=m=>{ const qg=QUALGRID[m]||{}, e=["max","xhigh","high","medium","low","solo"].find(k=>qg[k]); return e?score(qg[e][0]):0; };
  const dark=document.documentElement.getAttribute('data-theme')==='dark'||(window.matchMedia('(prefers-color-scheme:dark)').matches&&document.documentElement.getAttribute('data-theme')!=='light');
  const heat=c=>{ const t=cmax>1?Math.log(c)/Math.log(cmax):0, al=dark?(0.10+t*0.42):(0.07+t*0.40);
    return `background:color-mix(in srgb, var(--opus48) ${Math.round(al*100)}%, transparent)`; };
  for(const m of Object.keys(COSTGRID).sort((a,b)=>topS(b)-topS(a))){ const md=MODELS[m], cg=COSTGRID[m], tr=document.createElement("tr");
    let row=`<td class="mdl"><span class="dot" style="background:${cvar(md.c)}"></span>${md.label}${md.tag?' <span class="pill" title="Cost is strongly task-size dependent — a verbose model swings widely between short and long agentic tasks, hence the wide CI.">size-sensitive</span>':''}</td>`;
    if(cg.solo){ const c=cell(cg.solo);   // Haiku 4.5 = single operating point → one merged cell across the 5 effort columns
      row+=`<td colspan="5"><div class="cell num" style="${heat(c[0])}">${fmtC(c[0])}<small>merged · ${c[1]}</small></div></td>`;
    } else {
      ["low","medium","high","xhigh","max"].forEach(e=>{ const c=cg[e]?cell(cg[e]):null;
        row+= c? `<td><div class="cell num" style="${heat(c[0])}">${fmtC(c[0])}<small>${c[1]}</small></div></td>`
               : `<td class="na">—</td>`; });
    }
    row+=`<td class="mdl num">${pct(topS(m))}</td>`;
    tr.innerHTML=row; tb.appendChild(tr);
  }
}
// ---------- VALUE-INDEX MATRIX: every couple shown, model × effort, against the price trend ----------
// Each cell is the couple's value index 100·e^r (100 = the trend) with its 16–84 % range: r's spread is the couple's
// two quasi-standard errors across the trend line, √(hx² + λ²·ht²). Rows in the same order as the cost matrix.
function drawValueMatrix(){
  const tb=document.querySelector("#value-tbl tbody"); if(!tb) return; tb.innerHTML="";
  const rows=couples(), tr=fitTrend(rows), by={};
  rows.forEach(p=>{ (by[p.m]=by[p.m]||{})[p.e]=p; });
  const topS=m=>{ const qg=QUALGRID[m]||{}, e=["max","xhigh","high","medium","low","solo"].find(k=>qg[k]); return e?score(qg[e][0]):0; };
  // Colour range from the data: the most favourable couple shown is the deepest green, the least favourable the deepest
  // red, each side scaled on its own (log scale), 100 neutral.
  const rs=rows.map(p=>valueOf(tr,p)), rHi=Math.max(...rs,1e-9), rLo=Math.min(...rs,-1e-9);
  const cell=p=>{ const r=valueOf(tr,p), sd=Math.hypot(p.hx,tr.l*p.ht), al=Math.round((0.08+(r>=0?r/rHi:r/rLo)*0.50)*100),
      sc=r>=0?cvar('--good'):cvar('--crit');
    return `<div class="cell num" style="background:color-mix(in srgb, ${sc} ${al}%, transparent)">${vIndex(r)}<small>${vIndex(r-sd)}–${vIndex(r+sd)}</small></div>`; };
  for(const m of Object.keys(by).sort((a,b)=>topS(b)-topS(a))){ const md=MODELS[m], row=document.createElement("tr");
    let h=`<td class="mdl"><span class="dot" style="background:${cvar(md.c)}"></span>${md.label}</td>`;
    if(by[m].solo) h+=`<td colspan="5">${cell(by[m].solo)}</td>`;
    else ["low","medium","high","xhigh","max"].forEach(e=>{ h+= by[m][e]? `<td>${cell(by[m][e])}</td>` : `<td class="na">—</td>`; });
    row.innerHTML=h; tb.appendChild(row); } }
// ---------- LINKING GRAPH ----------
// nodes = (model,effort) couples ; edges = a source that measured them on the SAME task.
// DATA-DRIVEN: generated by build.py::groups_data() from raw-data.csv (nodes) + an editorial metadata sidecar
// (label / type / verified config note).
const GROUPS = __GROUPS_DATA__;
const GMODEL = {
 "fable-5.1":{l:"Fable 5.1",c:"--fable51",cur:1},"fable-5":{l:"Fable 5",c:"--fable5",cur:1},
 "opus-5.5":{l:"Opus 5.5",c:"--opus55",cur:1},"opus-5":{l:"Opus 5",c:"--opus5",cur:1},"opus-4.8":{l:"Opus 4.8",c:"--opus48",cur:1},
 "opus-4.7":{l:"Opus 4.7",c:"--opus47",cur:1},"sonnet-5.5":{l:"Sonnet 5.5",c:"--sonnet55",cur:1},"sonnet-5":{l:"Sonnet 5",c:"--sonnet5",cur:1},
 "sonnet-4.6":{l:"Sonnet 4.6",c:"--sonnet46",cur:1},"haiku-4.5":{l:"Haiku 4.5",c:"--haiku45",cur:1},
 "opus-4.6":{l:"Opus 4.6",leg:1},"sonnet-3.7":{l:"Sonnet 3.7",leg:1},"opus-4.5":{l:"Opus 4.5",leg:1},
 "sonnet-4.5":{l:"Sonnet 4.5",leg:1},"opus-4.1":{l:"Opus 4.1",leg:1},
};
const GCOL={sweep:"#2E9C8E",xmodel:"#7C6BB2",xgen:"#B98A3E"};
function drawEdgeTable(){
  const tb=document.querySelector("#edge-tbl tbody"); tb.innerHTML="";
  const short=x=>{const[m,e]=x.split("@");return (GMODEL[m]?GMODEL[m].l:m)+"·"+e;};
  const cur=x=>{const m=x.split("@")[0];return GMODEL[m]&&GMODEL[m].cur;};
  GROUPS.slice().filter(g=>g.n.some(cur))   // keep only sources that touch a current model
    .sort((a,b)=>a.t.localeCompare(b.t)||a.g.localeCompare(b.g)).forEach(g=>{
    const cn=g.n.filter(cur);
    const tr=document.createElement("tr");
    tr.innerHTML=`<td><b>${g.u?`<a href="${g.u}" target="_blank" rel="noopener">${g.g}</a>`:g.g}</b><br><span class="faint" style="font-size:10px">${g.s}</span></td>`
      +`<td style="font-size:11px">${g.h||"—"}</td>`
      +`<td><span class="etag" style="background:${GCOL[g.t]}">${g.t}</span></td>`
      +`<td>${cn.map(short).join(" · ")}</td>`;
    tb.appendChild(tr);});
}
// ---- pan/zoom in DATA space : Shift+wheel zoom · drag pan · +/−/⟳ buttons ----
// Instead of scaling the viewBox (which drags the axes along), we mutate the chart's view [xlo,xhi,tLo,tHi] and
// re-render, so ticks/labels recompute at fixed size for the zoomed window. Registry maps id → its draw function.
const CHART_RENDER={chartB:drawB, chartP:drawPareto};
const svgPt=(s,cx,cy)=>{ const P=new DOMPoint(cx,cy).matrixTransform(s.getScreenCTM().inverse()); return {x:P.x,y:P.y}; };
const dataAt=(s,px,py)=>{ const g=s.__geo, v=s.__view;   // pixel → view coords (log-cost, yOf θ)
  return [ v[0]+(px-g.mL)/g.iw*(v[1]-v[0]), v[2]+(1-(py-g.mT-g.yp)/(g.ih-2*g.yp))*(v[3]-v[2]) ]; };
function zoomView(s,px,py,f){ const [ux,uy]=dataAt(s,px,py), v=s.__view.slice();
  v[0]=ux-(ux-v[0])*f; v[1]=ux+(v[1]-ux)*f; v[2]=uy-(uy-v[2])*f; v[3]=uy+(v[3]-uy)*f; s.__view=v; }
function zoomable(svg){
  const box=svg.closest(".card")||svg.parentNode; box.style.position="relative";   // buttons attach to the CARD (chartbox clips overflow)
  let raf=false; const render=()=>{ if(raf) return; raf=true; requestAnimationFrame(()=>{ raf=false; CHART_RENDER[svg.id](); }); };
  if(!box.querySelector(".zoomctl")){
    const tb=document.createElement("div"); tb.className="zoomctl";
    tb.innerHTML='<span class="zoomhint">⇧+scroll: zoom · drag: pan</span><button data-z="in" title="Zoom +">+</button><button data-z="out" title="Zoom −">−</button><button data-z="reset" title="Reset">⟳</button>';
    tb.addEventListener("click",e=>{ const z=e.target.getAttribute("data-z"); if(!z)return;
      if(z==="reset"){ svg.__view=null; } else { const g=svg.__geo; zoomView(svg,g.mL+g.iw/2,g.mT+g.ih/2, z==="in"?0.8:1.25); }
      render(); });
    box.appendChild(tb);
  }
  if(svg.__zoom) return; svg.__zoom=true; svg.style.cursor="grab"; svg.style.userSelect="none"; svg.style.webkitUserSelect="none";
  svg.addEventListener("wheel",e=>{ if(!e.shiftKey) return; e.preventDefault();   // Shift+wheel (Ctrl/⌘ = browser zoom, avoided)
    const p=svgPt(svg,e.clientX,e.clientY); zoomView(svg,p.x,p.y, e.deltaY<0?0.9:1.11); render(); },{passive:false});
  let d=null;
  svg.addEventListener("pointerdown",e=>{ e.preventDefault(); d={x:e.clientX,y:e.clientY}; svg.style.cursor="grabbing"; svg.setPointerCapture(e.pointerId); });
  svg.addEventListener("pointermove",e=>{ if(!d)return;
    const p0=svgPt(svg,d.x,d.y), p1=svgPt(svg,e.clientX,e.clientY), a=dataAt(svg,p0.x,p0.y), b=dataAt(svg,p1.x,p1.y);
    const v=svg.__view, dx=b[0]-a[0], dy=b[1]-a[1]; v[0]-=dx; v[1]-=dx; v[2]-=dy; v[3]-=dy;   // keep the grabbed point under the cursor
    d={x:e.clientX,y:e.clientY}; render(); });
  const up=()=>{ d=null; svg.style.cursor="grab"; };
  svg.addEventListener("pointerup",up); svg.addEventListener("pointercancel",up); svg.addEventListener("pointerleave",up);
}
function fillMeta(){   // all source counts + the footer source list derive from the (generated) GROUPS — nothing hand-typed
  const curNode=x=>{const m=x.split("@")[0];return GMODEL[m]&&GMODEL[m].cur;};
  const curGroups=GROUPS.filter(g=>g.n.some(curNode));
  const pub=s=>s==="anthropic-chart"?"anthropic-syscard":s;        // one publisher = one source (mirrors PUBLISHER in build.py)
  const nSrc=new Set(curGroups.map(g=>pub(g.s))).size;              // independent sources
  const nMeas=curGroups.reduce((a,g)=>a+g.n.filter(curNode).length,0);   // measured (model, effort) points
  document.querySelectorAll(".nsrc").forEach(e=>e.textContent=`${nSrc} sources · ${curGroups.length} benchmarks · ${nMeas} measurements`);
  const et=document.getElementById("edge-title"); if(et) et.textContent=`The ${curGroups.length} benchmarks (${nSrc} sources, ${nMeas} measurements) that weave the links`;
  const sl=document.getElementById("src-list");
  if(sl) sl.textContent=curGroups.slice().sort((a,b)=>a.g.localeCompare(b.g,'en')).map(g=>g.g).join(" · ");
}
// Answer first: the headline pick in one sentence in the header (visible), and the full statement — crown, pick per
// tier, top-quality couple — as plain text for llms.txt. Both pre-rendered at build time (site/prerender.js).
function answerData(){
  const {picks,crown}=tierPicks();
  const top=couples().reduce((a,b)=>b.t>a.t?b:a);
  const nm=p=>`${MODELS[p.m].label}${p.e==="solo"?"":` at ${p.e==="xhigh"?"xHigh":p.e} effort`}`;
  return {picks,crown,top,nm};
}
function fillAnswer(){
  const host=document.getElementById("answer"); if(!host) return;
  const {crown,nm}=answerData();
  host.innerHTML=`The best value today is <b>${nm(crown)}</b> — ${vWord(crown.r)} than the price trend for its quality (expected score ${pct(crown.s)} on the benchmark panel).`;
}
function answerFull(){
  const {picks,crown,top,nm}=answerData();
  return `Best value overall: ${nm(crown)}, ${vWord(crown.r)} than the price trend for its quality (expected score ${pct(crown.s)} on the benchmark panel, cost ${fmtC(crown.c)}× the cheapest couple). `
    +`Best pick by task tier: ${picks.map(t=>`${t.name.toLowerCase()} → ${nm(t.win)}`).join("; ")}. `
    +`Highest measured quality: ${nm(top)} (expected score ${pct(top.s)}, cost ${fmtC(top.c)}× the cheapest couple).`;
}
function renderAll(){renderControls();drawB();drawPareto();drawTierTuner();drawTiers();drawMatrix();drawValueMatrix();drawEdgeTable();fillMeta();fillAnswer();
  ['chartB','chartP'].forEach(id=>{ const sv=document.getElementById(id); if(sv) zoomable(sv); });}
renderAll();
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',renderAll);
new MutationObserver(renderAll).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
