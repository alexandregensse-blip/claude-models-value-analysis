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
// round-value axis ticks (regular VALUES, not regular screen spacing)
const logTicks=(vmin,vmax)=>{const o=[];for(let e=Math.floor(Math.log10(vmin));Math.pow(10,e)<=vmax*1.0001;e++)for(let b=1;b<=9;b++){const v=b*Math.pow(10,e);if(v>=vmin*0.999&&v<=vmax*1.001)o.push(v);}return o;};
const tickLbl=v=>{const m=Math.round(v/Math.pow(10,Math.floor(Math.log10(v)+1e-9)));return m===1||m===2||m===5;};
const linTicks=(lo,hi,target)=>{const raw=(hi-lo)/target,mag=Math.pow(10,Math.floor(Math.log10(raw))),n=raw/mag,step=(n<1.5?1:n<3?2:n<7?5:10)*mag,o=[];for(let t=Math.ceil(lo/step)*step;t<=hi+1e-9;t+=step)o.push(Math.round(t*1e4)/1e4);return o;};
// least-squares log fit q = A + B·log10(c) — monotone, diminishing-returns envelope for the Pareto frontier
// (a power law overshoots the quality plateau; a quadratic turns back down at high cost — the log does neither).
function logFit(xs,ys){ const n=xs.length, mx=xs.reduce((a,b)=>a+b,0)/n, my=ys.reduce((a,b)=>a+b,0)/n;
  let sxy=0,sxx=0; for(let i=0;i<n;i++){ sxy+=(xs[i]-mx)*(ys[i]-my); sxx+=(xs[i]-mx)*(xs[i]-mx); }
  const B=sxy/sxx; return [my-B*mx, B]; }

// ---- COST is now DATA-DRIVEN: relative cost per (model,effort) [rel, ci_lo, ci_hi], anchored opus-4.8@medium,
// computed in build.py::cost_grid() from measured same-task ratios (couple-atomic). Only intel (Vals capability
// index) + halo height (ey) + the tag flag stay hand-set here — they are capability priors, not cost.
const COSTGRID=__COSTGRID__;
const QUALGRID=__QUALGRID__;   // data-driven quality axis: {model:{effort:[central, lo, hi]}} — median + robust Huber ±1.5·MAD band (asymmetric, centred on median)
const META={
  "fable-5":{intel:75.1,ey:2.2}, "opus-4.8":{intel:70.4,ey:1.4}, "sonnet-5":{intel:68.6,ey:2.6,tag:true},
  "opus-4.7":{intel:66.1,ey:2.2}, "sonnet-4.6":{intel:60.1,ey:1.6}, "haiku-4.5":{intel:40.9,ey:1.9},
};
const B={};
for(const m in META){ const cg=COSTGRID[m]||{};
  B[m]={intel:META[m].intel, ey:META[m].ey, tag:META[m].tag, order:Object.keys(cg), e:cg}; }
// quality offset below the TOP available effort (concave plateau SHAPE, corroborated by effort-sweep sources:
// small gains + plateau on code/agentic). Shared across models as a prior; Haiku is single-effort → flat.
const OFF5={low:-5.0,medium:-3.2,high:-1.6,xhigh:-0.6,max:0};      // 5-level models (top=max)
const OFF4={low:-5.0,medium:-3.2,high:-1.6,max:0};                  // sonnet-4.6 (top=max, no xhigh)
const OFFH={solo:0};                                               // haiku 4.5: one operating point, no ladder
function offs(m){return m==="haiku-4.5"?OFFH:(m==="sonnet-4.6"?OFF4:OFF5);}

// ============ shared chart helpers (used by both the landscape §1 and the Pareto) ============
// Quality axis as a symlog around parity (1.0): dilates the crowded near-parity band, compresses the sparse tails.
function symY(ymn,ymx,mT,ih,yp){ const SQ=0.045, T=v=>Math.sign(v-1)*Math.log(1+Math.abs(v-1)/SQ), tb=T(ymn)-0.12, tt=T(ymx)+0.12;
  return v=>mT+yp+(1-(T(v)-tb)/(tt-tb))*(ih-2*yp); }
// Quality gridlines at round quality values (non-uniform spacing under symlog); the 1.0 anchor is dashed.
function qGrid(s,Y,mL,iw,mT,ih){ [0.7,0.8,0.9,0.95,1.0,1.05,1.1,1.15,1.2,1.3].forEach(val=>{ const y=Y(val); if(y<mT-0.5||y>mT+ih+0.5) return;
  s.appendChild(el("line",{x1:mL,y1:y,x2:mL+iw,y2:y,stroke:cvar(val===1?'--opus48':'--line'),"stroke-width":1,"stroke-dasharray":val===1?"3 4":"","stroke-opacity":val===1?0.5:1}));
  const t=el("text",{x:mL-9,y:y+4,fill:cvar('--faint'),"font-size":10.5,"text-anchor":"end"});t.textContent=val.toFixed(2);s.appendChild(t); }); }
// Asymmetric Huber uncertainty ovals (per-side radii from [clo,chi]×[qlo,qhi]), centred on the median dot, clipped
// to the plot, faint by default. Returns the array used by hoverTip() to reveal them.
function drawOvals(s,pts,X,Y,mL,iw,mT,ih,cid){ const defs=el("defs"), cp=el("clipPath",{id:cid});
  cp.appendChild(el("rect",{x:mL,y:mT,width:iw,height:ih})); defs.appendChild(cp); s.appendChild(defs);
  const gEll=el("g",{"clip-path":`url(#${cid})`}); s.appendChild(gEll); const ells=[], byM={};
  pts.forEach(p=>(byM[p.m]=byM[p.m]||[]).push(p));
  for(const m in byM){ const col=cvar(MODELS[m].c); byM[m].forEach(p=>{ if(p.clo==null) return; const cx=X(p.c), cy=Y(p.q),
      rxR=Math.max(X(p.chi)-cx,0.6), rxL=Math.max(cx-X(p.clo),0.6), ryU=Math.max(cy-Y(p.qhi),0.6), ryD=Math.max(Y(p.qlo)-cy,0.6);
    const d=`M ${cx} ${cy-ryU} A ${rxR} ${ryU} 0 0 1 ${cx+rxR} ${cy} A ${rxR} ${ryD} 0 0 1 ${cx} ${cy+ryD} A ${rxL} ${ryD} 0 0 1 ${cx-rxL} ${cy} A ${rxL} ${ryU} 0 0 1 ${cx} ${cy-ryU} Z`;
    const elp=el("path",{d,fill:col,"fill-opacity":0.4,stroke:col,"stroke-opacity":0.85,"stroke-width":1,opacity:0.15});
    gEll.appendChild(elp); ells.push({el:elp,cx,cy,rxR,rxL,ryU,ryD}); }); }
  return ells; }
// Hover: reveal ovals under the cursor + a compact tooltip when the cursor is right on a point.
function hoverTip(s,ells,pts,X,Y,mL,iw){ const DEF=0.15,HOV=0.78;
  const tip=el("g",{"pointer-events":"none",opacity:0}), trect=el("rect",{rx:3,fill:cvar('--panel'),stroke:cvar('--line'),"stroke-width":1,"fill-opacity":0.97});
  const ttxt=el("text",{"font-size":9.5,"font-weight":600,"text-anchor":"middle"}); tip.appendChild(trect); tip.appendChild(ttxt); s.appendChild(tip);
  const capE=e=>e==="solo"?"solo":e.charAt(0).toUpperCase()+e.slice(1);
  s.onmousemove=ev=>{ const P=new DOMPoint(ev.clientX,ev.clientY).matrixTransform(s.getScreenCTM().inverse());
    ells.forEach(o=>{ const dx=P.x-o.cx, dy=P.y-o.cy, rx=dx>0?o.rxR:o.rxL, ry=dy>0?o.ryD:o.ryU; o.el.setAttribute("opacity",((dx/rx)**2+(dy/ry)**2<=1)?HOV:DEF); });
    let best=null,bd=49; pts.forEach(p=>{ const d2=(P.x-X(p.c))**2+(P.y-Y(p.q))**2; if(d2<bd){bd=d2;best=p;} });
    if(best){ ttxt.setAttribute("fill",cvar(MODELS[best.m].c)); ttxt.setAttribute("x",Math.min(Math.max(X(best.c),mL+52),mL+iw-52)); ttxt.setAttribute("y",Y(best.q)-11);
      ttxt.textContent=`${MODELS[best.m].label} · ${capE(best.e)} — ${best.c}× · ${best.q}×`;
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

function drawB(){
  const s=document.getElementById("chartB"); s.innerHTML="";
  const W=1100,H=619,mL=58,mR=100,mT=22,mB=56, iw=W-mL-mR, ih=H-mT-mB;   // 16:9, fills body; extra width → cost axis + labels breathe
  // X = cost [central,lo,hi] from COSTGRID · Y = quality [central,lo,hi] from QUALGRID (median + Huber ±1.5·MAD band). Haiku excluded here. Bounds DYNAMIC.
  const pts=[]; let xmn=Infinity,xmx=-Infinity,ymn=Infinity,ymx=-Infinity;
  for(const m in COSTGRID){ if(m==="haiku-4.5") continue; const cg=COSTGRID[m], qg=QUALGRID[m]||{};
    for(const e in cg){ const d=cg[e], q=qg[e]; if(!q) continue;
      xmn=Math.min(xmn,d[1]); xmx=Math.max(xmx,d[2]); ymn=Math.min(ymn,q[1]); ymx=Math.max(ymx,q[2]);   // bounds include the uncertainty ovals (extents) so they stay fully inside
      pts.push({m,e,c:d[0],clo:d[1],chi:d[2],q:q[0],qlo:q[1],qhi:q[2]}); } }
  const xlo=Math.log10(xmn)-0.06, xhi=Math.log10(xmx)+0.06, yp=8;
  const X=v=>mL+(Math.log10(v)-xlo)/(xhi-xlo)*iw;
  const Y=symY(ymn,ymx,mT,ih,yp);   // symlog quality axis (dilated near parity 1.0)
  const fmtC=v=>(v<1?v.toFixed(2):v<10?v.toFixed(1):v.toFixed(0));
  logTicks(Math.pow(10,xlo),Math.pow(10,xhi)).forEach(val=>{ const x=X(val);
    s.appendChild(el("line",{x1:x,y1:mT,x2:x,y2:mT+ih,stroke:cvar('--line'),"stroke-width":1}));
    if(tickLbl(val)){const t=el("text",{x,y:mT+ih+20,fill:cvar('--faint'),"font-size":10.5,"text-anchor":"middle"});t.textContent=fmtC(val)+"×";s.appendChild(t);}});
  qGrid(s,Y,mL,iw,mT,ih);
  let a=el("text",{x:mL+iw/2,y:H-12,fill:cvar('--muted'),"font-size":12.5,"text-anchor":"middle"});a.textContent="Relative cost  (Opus 4.8 @medium = 1.0 · log scale)";s.appendChild(a);
  a=el("text",{x:16,y:mT+ih/2,fill:cvar('--muted'),"font-size":12.5,"text-anchor":"middle",transform:`rotate(-90 16 ${mT+ih/2})`});a.textContent="Relative quality  (Opus 4.8 @medium = 1.0 · dilated near parity)";s.appendChild(a);
  const EO=["low","medium","high","xhigh","max"], byM={};
  pts.forEach(p=>{(byM[p.m]=byM[p.m]||[]).push(p);});
  const ells=drawOvals(s,pts,X,Y,mL,iw,mT,ih,"clipB");                     // faint asymmetric uncertainty ovals, behind
  const segs=[];                                                          // curves + points on top, collect line segments for label repulsion
  for(const m in byM){ const col=cvar(MODELS[m].c), mp=byM[m].slice().sort((a,b)=>EO.indexOf(a.e)-EO.indexOf(b.e));
    s.appendChild(el("path",{d:mp.map((p,i)=>(i?"L":"M")+X(p.c)+" "+Y(p.q)).join(" "),fill:"none",stroke:col,"stroke-width":2.2,"stroke-linejoin":"round"}));
    mp.forEach(p=>s.appendChild(el("circle",{cx:X(p.c),cy:Y(p.q),r:3.6,fill:col,stroke:cvar('--panel'),"stroke-width":1.4})));
    for(let i=0;i<mp.length-1;i++) segs.push([X(mp[i].c),Y(mp[i].q),X(mp[i+1].c),Y(mp[i+1].q)]); }
  const ppix=pts.map(p=>({x:X(p.c),y:Y(p.q)})), labs=[];                  // effort labels + model-name labels, force-directed together
  pts.forEach(p=>labs.push({ax:X(p.c),ay:Y(p.q),lx:X(p.c),ly:Y(p.q)-9,t:p.e,col:cvar(MODELS[p.m].c),lead:cvar(MODELS[p.m].c),w:p.e.length*5.4+4,h:11,fs:8.5,mdl:false}));
  for(const m in byM){ const mp=byM[m].slice().sort((a,b)=>EO.indexOf(a.e)-EO.indexOf(b.e)), last=mp[mp.length-1], w=MODELS[m].label.length*7+6;
    labs.push({ax:X(last.c),ay:Y(last.q),lx:X(last.c)+16+w/2,ly:Y(last.q)+4,t:MODELS[m].label,col:cvar(MODELS[m].c),lead:cvar(MODELS[m].c),w,h:15,fs:12.5,mdl:true}); }
  placeLabels(s,labs,ppix,segs,W,mL,mT,ih);
  hoverTip(s,ells,pts,X,Y,mL,iw);
  const lg=document.getElementById("legendB"); lg.innerHTML=
    Object.keys(MODELS).filter(m=>m!=="haiku-4.5").map(m=>`<span class="lg"><span class="sw" style="background:${cvar(MODELS[m].c)}"></span>${MODELS[m].label}</span>`).join("")
    +`<span class="lg"><span class="sw" style="opacity:.5;background:transparent;border:1px solid var(--ink);border-radius:50%"></span>oval = robust uncertainty (Huber ±1.5·MAD), asymmetric · <b>hover a point</b> for its identity</span>`;
}

// ---- Dedicated Pareto chart: cost × quality scatter, dominated points faded, frontier joined ----
// Same shared machinery as the §1 landscape: symlog quality axis, faint Huber ovals (hover to reveal),
// point tooltip, force-directed frontier labels. Full body width.
function drawPareto(){
  const s=document.getElementById("chartP"); if(!s) return; s.innerHTML="";
  const W=1100,H=619,mL=54,mR=100,mT=20,mB=52, iw=W-mL-mR, ih=H-mT-mB;
  // X = cost · Y = quality (central + lo/hi for the ovals). All current nodes incl. Haiku (solo).
  const pts=[]; let xmn=Infinity,xmx=-Infinity,ymn=Infinity,ymx=-Infinity;
  for(const m in COSTGRID){ const cg=COSTGRID[m], qg=QUALGRID[m]||{};
    for(const e in cg){ const d=cg[e], q=qg[e]; if(!q) continue;
      xmn=Math.min(xmn,d[1]); xmx=Math.max(xmx,d[2]); ymn=Math.min(ymn,q[1]); ymx=Math.max(ymx,q[2]);
      pts.push({m,e,c:d[0],clo:d[1],chi:d[2],q:q[0],qlo:q[1],qhi:q[2]}); } }
  const xlo=Math.log10(xmn)-0.06, xhi=Math.log10(xmx)+0.06, yp=10;
  const X=v=>mL+(Math.log10(v)-xlo)/(xhi-xlo)*iw;
  const Y=symY(ymn,ymx,mT,ih,yp);
  const fmtC=v=>(v<1?v.toFixed(2):v<10?v.toFixed(1):v.toFixed(0));
  logTicks(Math.pow(10,xlo),Math.pow(10,xhi)).forEach(val=>{ const x=X(val);
    s.appendChild(el("line",{x1:x,y1:mT,x2:x,y2:mT+ih,stroke:cvar('--line'),"stroke-width":1}));
    if(tickLbl(val)){const t=el("text",{x,y:mT+ih+18,fill:cvar('--faint'),"font-size":10.5,"text-anchor":"middle"});t.textContent=fmtC(val)+"×";s.appendChild(t);}});
  qGrid(s,Y,mL,iw,mT,ih);
  let a=el("text",{x:mL+iw/2,y:H-10,fill:cvar('--muted'),"font-size":12,"text-anchor":"middle"});a.textContent="Relative cost  (Opus 4.8 @medium = 1.0 · log scale)";s.appendChild(a);
  a=el("text",{x:13,y:mT+ih/2,fill:cvar('--muted'),"font-size":12,"text-anchor":"middle",transform:`rotate(-90 13 ${mT+ih/2})`});a.textContent="Relative quality  (Opus 4.8 @medium = 1.0 · dilated near parity)";s.appendChild(a);
  const E=1e-9, dom=(o,p)=>o.c<=p.c+E&&o.q>=p.q-E&&(o.c<p.c-E||o.q>p.q+E);
  const par=pts.filter(p=>!pts.some(o=>dom(o,p))).sort((a,b)=>a.c-b.c);
  const pset=new Set(par.map(p=>p.m+"@"+p.e));
  // Fit a smooth logarithmic ENVELOPE to the frontier (quality vs log-cost); draw it faint, BEHIND everything else.
  const fit=logFit(par.map(p=>Math.log10(p.c)),par.map(p=>p.q)), fev=x=>fit[0]+fit[1]*x;
  { const cmn=Math.min(...par.map(p=>p.c)), cmx=Math.max(...par.map(p=>p.c)), lmn=Math.log10(cmn), lmx=Math.log10(cmx); let d="";
    for(let i=0;i<=56;i++){ const lx=lmn+(lmx-lmn)*i/56; d+=(i?"L":"M")+X(Math.pow(10,lx))+" "+Y(fev(lx))+" "; }
    s.appendChild(el("path",{d,fill:"none",stroke:cvar('--ink'),"stroke-width":1,"stroke-opacity":0.5})); }
  // score = signed distance to the envelope, squashed: tanh(residual / RMS-over-all-points). +1 above · 0 on · −1 below.
  const resAll=pts.map(p=>p.q-fev(Math.log10(p.c))), rms=Math.sqrt(resAll.reduce((a,r)=>a+r*r,0)/resAll.length);
  const scored=pts.map((p,i)=>({...p,score:Math.tanh(resAll[i]/rms),front:pset.has(p.m+"@"+p.e)}));
  fillScoreTable(scored);
  const ells=drawOvals(s,par,X,Y,mL,iw,mT,ih,"clipP");   // ovals only on the frontier points
  s.appendChild(el("path",{d:par.map((p,i)=>(i?"L":"M")+X(p.c)+" "+Y(p.q)).join(" "),fill:"none",stroke:cvar('--ink'),"stroke-width":2.2,"stroke-opacity":.7,"stroke-linejoin":"round"}));
  pts.forEach(p=>{ const on=pset.has(p.m+"@"+p.e), col=cvar(MODELS[p.m].c);
    s.appendChild(el("circle",{cx:X(p.c),cy:Y(p.q),r:on?5.6:3.4,fill:col,"fill-opacity":on?1:.25,stroke:on?cvar('--panel'):"none","stroke-width":1.3})); });
  // frontier labels (model · effort), force-directed to dodge overlaps and the frontier line
  const cap=e=>e==="solo"?"solo":e.charAt(0).toUpperCase()+e.slice(1);
  const ppix=par.map(p=>({x:X(p.c),y:Y(p.q)})), segs=[];   // anti-collision considers ONLY frontier points (faded/dominated ignored)
  for(let i=0;i<par.length-1;i++) segs.push([X(par[i].c),Y(par[i].q),X(par[i+1].c),Y(par[i+1].q)]);
  const labs=par.map(p=>{ const t=`${MODELS[p.m].label}${p.e==="solo"?"":" · "+cap(p.e)}`, w=t.length*7.2+8;
    return {ax:X(p.c),ay:Y(p.q),lx:X(p.c)+18+w/2,ly:Y(p.q),t,col:cvar(MODELS[p.m].c),lead:cvar(MODELS[p.m].c),w,h:17,fs:13,mdl:true}; });
  placeLabels(s,labs,ppix,segs,W,mL,mT,ih);
  hoverTip(s,ells,pts,X,Y,mL,iw);
  const lg=document.getElementById("legendP");
  if(lg) lg.innerHTML=Object.keys(MODELS).map(m=>`<span class="lg"><span class="sw" style="background:${cvar(MODELS[m].c)}"></span>${MODELS[m].label}</span>`).join("")
    +`<span class="lg"><span class="sw" style="opacity:.25;background:var(--ink);border-radius:50%"></span>dominated</span>`
    +`<span class="lg"><span class="sw" style="border-top:2.4px solid var(--ink);background:transparent;height:0"></span>Pareto frontier</span>`
    +`<span class="lg"><span class="sw" style="border-top:1.5px solid var(--ink);opacity:.5;background:transparent;height:0"></span>frontier fit (envelope)</span>`;
  const pn=document.getElementById("pareto-note");
  if(pn) pn.innerHTML=par.map(p=>`<b style="color:${cvar(MODELS[p.m].c)}">${MODELS[p.m].label}${p.e==="solo"?"":" @"+p.e}</b> <span class="faint">${fmtC(p.c)}× · q=${p.q.toFixed(2)}</span>`).join(" &nbsp;→&nbsp; ");
}
// ---- Value-score table : distance of each couple to the fitted Pareto-frontier envelope (from drawPareto) ----
function fillScoreTable(scored){
  const tb=document.querySelector("#score-tbl tbody"); if(!tb) return; tb.innerHTML="";
  const capE=e=>e==="solo"?"solo":e.charAt(0).toUpperCase()+e.slice(1);
  scored.filter(p=>p.front).slice().sort((a,b)=>b.score-a.score).forEach(p=>{ const col=cvar(MODELS[p.m].c),   // frontier couples only
    sc=p.score>=0?cvar('--good'):cvar('--crit'), al=Math.round((0.14+Math.abs(p.score)*0.52)*100),
    pill=`<span class="scorepill" style="background:color-mix(in srgb, ${sc} ${al}%, transparent); color:${sc}">${p.score>=0?'+':''}${p.score.toFixed(2)}</span>`;
    const tr=document.createElement("tr");
    tr.innerHTML=`<td class="mdl"><span class="dot" style="background:${col}"></span>${MODELS[p.m].label} · ${capE(p.e)}</td>`
      +`<td class="num">${p.c.toFixed(2)}×</td><td class="num">${p.q.toFixed(2)}×</td>`
      +`<td style="min-width:96px">${pill}</td>`
      +`<td style="text-align:left;color:${sc};font-size:12px">${p.score>=0?'above envelope':'below envelope'}</td>`;
    tb.appendChild(tr); }); }
// ---- BEST-YIELD-BY-TASK-TIER + best-of-both-worlds crown (data-driven from COSTGRID × QUALGRID) ----
// Four task-complexity tiers, defined by the QUALITY window a task demands (relative quality, anchor
// Opus 4.8 @medium = 1.0). Per tier we pick, ON THE PARETO FRONTIER and within that quality band, the
// couple with the best score/cost YIELD (q/c) — the cheapest way to clear the bar. The crown ranks
// MODELS by a "best of both worlds" score V = q³/c (capability weighted 3× cost, in log terms): it
// rewards being both capable and efficient, so neither the cheapest-but-weak nor the strongest-but-costly wins.
const QFLOOR=1.0;   // crown complexity bar: only couples with quality ≥ this (relative to Opus 4.8 @medium) qualify — tuned for complex/production tasks
const TIERS=[
  {key:"triage",  name:"Triage &amp; volume", lo:0,    hi:0.65, ex:"Classification, tagging, extraction, routing, log/PR triage — run at scale, where throughput and unit cost dominate."},
  {key:"everyday",name:"Everyday build",      lo:0.65, hi:0.90, ex:"Routine coding, refactors, unit tests, summaries, first-draft agent steps — solid work that doesn't need the frontier."},
  {key:"pro",     name:"Professional",        lo:0.90, hi:1.03, ex:"Production code review, architecture, hard debugging, customer-facing reasoning — you need essentially flagship quality."},
  {key:"frontier",name:"Frontier",            lo:1.03, hi:99,   ex:"Research-grade reasoning, novel or ambiguous problems, the hardest agentic runs — a few extra points of capability are worth a premium."},
];
function tierPicks(){
  const rows=[];
  for(const m in COSTGRID){ const cg=COSTGRID[m], qg=QUALGRID[m]||{};
    for(const e in cg){ const q=qg[e]; if(!q) continue; rows.push({m,e,c:cg[e][0],q:q[0],y:q[0]/cg[e][0]}); } }
  const E=1e-9, dom=(o,p)=>o.c<=p.c+E&&o.q>=p.q-E&&(o.c<p.c-E||o.q>p.q+E);
  const front=rows.filter(p=>!rows.some(o=>dom(o,p)));
  const picks=TIERS.map(t=>{ const cand=front.filter(p=>p.q>=t.lo&&p.q<t.hi);
    return cand.length?{...t,win:cand.reduce((a,b)=>b.y>a.y?b:a)}:{...t,win:null}; });
  // Crown: V = q³/c, but only over couples that CLEAR the complexity bar q ≥ QFLOOR. Rationale (research-backed):
  // benchmark score is a task-averaged proxy that dilutes the hard tail; satisfaction is threshold/reliability-driven,
  // and the value of effort rises with difficulty. The floor isolates the tail where capability actually pays — so
  // the winning EFFORT lifts off 'low' (which only wins on flat average quality). q₀=1.0 = "must match the flagship".
  const crown=[]; for(const m in COSTGRID){ const cg=COSTGRID[m], qg=QUALGRID[m]||{}; let best=null;
    for(const e in cg){ const q=qg[e]; if(!q||q[0]<QFLOOR) continue; const V=Math.pow(q[0],3)/cg[e][0];
      if(!best||V>best.V) best={m,e,c:cg[e][0],q:q[0],V}; } if(best) crown.push(best); }
  crown.sort((a,b)=>b.V-a.V);
  const extValue=rows.reduce((a,b)=>b.y>a.y?b:a);      // global pure-value extreme (max yield q/c)
  const extCap=rows.reduce((a,b)=>b.q>a.q?b:a);        // global pure-capability extreme (max quality)
  return {picks,crown,extValue,extCap};
}
function drawTiers(){
  const host=document.getElementById("tier-cards"); if(!host) return;
  const capE=e=>e==="solo"?"solo":e.charAt(0).toUpperCase()+e.slice(1);
  const {picks,crown,extValue,extCap}=tierPicks();
  host.innerHTML=picks.map(t=>{ const w=t.win, col=w?cvar(MODELS[w.m].c):cvar('--muted');
    const pick=w?`<span class="tier-pick" style="color:${col}"><span class="dot" style="background:${col}"></span>${MODELS[w.m].label}${w.e==="solo"?"":" · "+capE(w.e)}</span>
        <span class="tier-nums">cost <b>${w.c.toFixed(2)}×</b> · quality <b>${w.q.toFixed(2)}×</b> · yield <b>${w.y.toFixed(2)}</b></span>`:`<span class="faint">no couple in band</span>`;
    return `<div class="card pad crit tier">
      <div class="tier-band">quality ${t.lo===0?"≤ ":t.lo+"–"}${t.hi>=99?"and up":t.hi}</div>
      <h3>${t.name}</h3>
      <div class="tier-win">${pick}</div>
      <span class="ex">${t.ex}</span>
    </div>`; }).join("");
  const c=crown[0], col=cvar(MODELS[c.m].c);
  const cr=document.getElementById("tier-crown");
  if(cr) cr.innerHTML=`
    <div class="crown-badge">👑 Best of both worlds</div>
    <div class="crown-model" style="color:${col}"><span class="dot" style="background:${col}"></span>${MODELS[c.m].label} · ${capE(c.e)}</div>
    <div class="crown-score">V = q³ ⁄ c = <b>${c.V.toFixed(2)}</b> &nbsp;<span class="faint">(quality ${c.q.toFixed(2)}× at cost ${c.c.toFixed(2)}×, over couples clearing q ≥ ${QFLOOR.toFixed(2)})</span></div>
    <p class="crown-note">Ranks models by a capability-weighted value score <b>V = q³/c</b>, evaluated <b>only over couples that clear a complexity bar q ≥ ${QFLOOR.toFixed(2)}</b> (≈ must match the flagship). Two reasons, both backed by the benchmark-vs-satisfaction literature&nbsp;: a task-averaged score dilutes the <b>hard tail</b> where effort actually pays, and satisfaction is <b>threshold/reliability-driven</b>, not mean-driven — so the floor lifts the winning effort off "low" (which only wins on flat average quality). For reference, the pure extremes&nbsp;: max value (yield) → <b style="color:${cvar(MODELS[extValue.m].c)}">${MODELS[extValue.m].label} · ${capE(extValue.e)}</b> · max capability (quality) → <b style="color:${cvar(MODELS[extCap.m].c)}">${MODELS[extCap.m].label} · ${capE(extCap.e)}</b>. <b>${MODELS[c.m].label} · ${capE(c.e)}</b> wins the balance.</p>`;
}
// ---------- MATRIX (sorted by intelligence desc) — cost cells DATA-DRIVEN from COSTGRID ----------
const fr=x=>x.toFixed(2);
const ciStr=(m,e,v)=> (m==="opus-4.8"&&e==="medium") ? "anchor" : (v[1]===v[2] ? "single source" : `${fr(v[1])}–${fr(v[2])}`);
const M={};
for(const m in META){ const cg=COSTGRID[m]||{}; M[m]={intel:META[m].intel, tag:META[m].tag};
  ["low","medium","high","xhigh","max","solo"].forEach(e=>{ M[m][e]= cg[e]? [cg[e][0], ciStr(m,e,cg[e])] : null; }); }
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
    let row=`<td class="mdl"><span class="dot" style="background:${cvar(md.c)}"></span>${md.label}${M[m].tag?' <span class="pill" title="Cost is strongly task-size dependent: Sonnet 5 is verbose (~2.5x the tokens of Opus 4.8), so its relative cost is ~0.7x on short tasks but up to ~1.6x on long agentic ones — hence the wide CI.">size-sensitive</span>':''}</td>`;
    if(M[m].solo){ const c=M[m].solo;   // Haiku 4.5 = single operating point → one merged cell across the 5 effort columns
      row+=`<td colspan="5"><div class="cell num" style="${heat(c[0])}">${c[0].toFixed(2)}<small>merged · ${c[1]}</small></div></td>`;
    } else {
      ["low","medium","high","xhigh","max"].forEach(e=>{ const c=M[m][e];
        row+= c? `<td><div class="cell num" style="${heat(c[0])}">${c[0].toFixed(2)}<small>${c[1]}</small></div></td>`
               : `<td class="na">—</td>`; });
    }
    row+=`<td class="mdl num">${M[m].intel.toFixed(1)}</td>`;
    tr.innerHTML=row; tb.appendChild(tr);
  }
}
// ---------- LINKING GRAPH ----------
// nodes = (model,effort) couples ; edges = a source that measured them on the SAME task.
// DATA-DRIVEN: generated by build.py::groups_data() from raw-data.csv (nodes) + an editorial metadata sidecar
// (label / type / verified config note). No more hand-maintained mirror that could silently drift from the CSV.
const GROUPS = __GROUPS_DATA__;
const GMODEL = {
 "fable-5":{l:"Fable 5",c:"--fable5",cur:1},"opus-4.8":{l:"Opus 4.8",c:"--opus48",cur:1},
 "opus-4.7":{l:"Opus 4.7",c:"--opus47",cur:1},"sonnet-5":{l:"Sonnet 5",c:"--sonnet5",cur:1},
 "sonnet-4.6":{l:"Sonnet 4.6",c:"--sonnet46",cur:1},"haiku-4.5":{l:"Haiku 4.5",c:"--haiku45",cur:1},
 "opus-4.6":{l:"Opus 4.6",leg:1},"sonnet-3.7":{l:"Sonnet 3.7",leg:1},"opus-4.5":{l:"Opus 4.5",leg:1},
 "sonnet-4.5":{l:"Sonnet 4.5",leg:1},"opus-4.1":{l:"Opus 4.1",leg:1},
};
const GCOL={sweep:"#2E9C8E",xmodel:"#7C6BB2",xgen:"#B98A3E"};
const GTLAB={sweep:"effort sweep (same model)",xmodel:"cross-model (same generation)",xgen:"cross-generation bridge"};
const MEFF={"fable-5":["low","medium","high","xhigh","max"],"opus-4.8":["low","medium","high","xhigh","max"],"sonnet-5":["low","medium","high","xhigh","max"],"opus-4.7":["low","medium","high","xhigh","max"],"sonnet-4.6":["low","medium","high","max"],"haiku-4.5":["solo"]};   // Haiku 4.5 = SINGLE-OPERATING-POINT model (no discrete effort parameter) → one node merging all its sources, placed off the effort gridlines; cost also in §6 (no-think regime, anchor)
const MX={"fable-5":0,"opus-4.8":1,"opus-4.7":2,"sonnet-5":3,"sonnet-4.6":4,"haiku-4.5":5,"opus-4.6":6.4,"sonnet-3.7":6.9,"opus-4.5":7.3,"sonnet-4.5":7.8,"opus-4.1":8.3};
const EORD=["max","xhigh","high","medium","low"];   // corroboration graph: 5 explicit efforts, no default row
const EORD2=["max","xhigh","high","medium","low","default"];   // line-cloud assignment view: adds the 'default' row
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
  const nodeSrc={}; GROUPS.forEach(g=>{ g.n.forEach(id=>{ (nodeSrc[id]=nodeSrc[id]||new Set()).add(g.s); }); });   // dedup by SOURCE: one source's sub-benchmarks count once
  const srcCount={}; for(const id in nodeSrc) srcCount[id]=nodeSrc[id].size;
  const hks=new Set(); GROUPS.forEach(g=>{ if(g.n.some(id=>id.startsWith("haiku-4.5@"))) g.n.forEach(id=>{if(id.startsWith("haiku-4.5@"))hks.add(g.s);}); }); srcCount["haiku-4.5@solo"]=hks.size;   // Haiku merged node = distinct sources measuring it in any config
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
    });}
  s.appendChild(el("circle",{cx:px("opus-4.8"),cy:py("medium"),r:11.5,fill:"none",stroke:cvar('--opus48'),"stroke-width":1.6,"stroke-dasharray":"1 2"}));
  document.getElementById("graphcap").innerHTML=`<b>5 discrete-effort models × 5 efforts</b> + <b>Haiku&nbsp;4.5 as a single point</b> (no <code>effort</code> parameter → all its sources merged into one node, see §6&nbsp;; "default" row removed&nbsp;; @default runs feed the §2 matrix CIs). Ring = <b>#independent sources</b>&nbsp;: <b><span style="color:${COLR.g}">green ≥3</span></b> · <b><span style="color:${COLR.y}">yellow 2</span></b> · <b><span style="color:${COLR.o}">orange 1</span></b> · <b><span style="color:${COLR.r}">red 0</span></b> (tally ${tally.g}/${tally.y}/${tally.o}/${tally.r}). <b>Filled</b> node = measured, <b>hollow</b> = inferred. Edge width ∝ #sources.`;
  document.getElementById("legendG").innerHTML=
    `<span class="lg"><span class="sw" style="border:2.4px solid ${COLR.g};border-radius:50%;background:transparent"></span>≥3 sources</span>`
    +`<span class="lg"><span class="sw" style="border:2.4px solid ${COLR.y};border-radius:50%;background:transparent"></span>2</span>`
    +`<span class="lg"><span class="sw" style="border:2.4px solid ${COLR.o};border-radius:50%;background:transparent"></span>1</span>`
    +`<span class="lg"><span class="sw" style="border:2.4px solid ${COLR.r};border-radius:50%;background:transparent"></span>0</span>`
    +`<span class="lg"><span class="sw" style="background:${cvar('--muted')}"></span>measured link</span>`;
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
      const ti=document.createElementNS(NS,"title");ti.textContent=`measured median ${c[0]} = ${c[1]}×`;sq.appendChild(ti);s.appendChild(sq); });
    const pos={};
    pts.slice().sort((a,b)=>a[1]-b[1]).forEach(p=>{ const x=X(p[1]); if(!inR(x))return; const derived=p[5]===1, grey=p[2]==="grey";
      const c=el("circle",{cx:x,cy:yA,r:4.4,fill:derived?"none":EC[p[2]],stroke:derived?EC[p[2]]:cvar('--panel'),"stroke-width":derived?1.6:1,"stroke-dasharray":derived?"2 1.5":"none"});
      const ti=document.createElementNS(NS,"title");ti.textContent=`${p[4]}${derived?" (derived via price)":""} · ${p[0]} · ${p[1]}× · ${p[2]} · ${p[3]}`;c.appendChild(ti);s.appendChild(c);
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
    if(grey1(cb[pair])){ yC=ay; const t=el("text",{x:aX0-8,y:yC+3.5,fill:cvar('--faint'),"font-size":9,"text-anchor":"end"});t.textContent="cost";s.appendChild(t); cp=axis(cb[pair],yC,consC,pair+"|cost"); ay+=axGap; }
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
  L.innerHTML=["low","medium","high","xhigh","max","grey"].map(k=>`<span class="lg"><span class="sw" style="background:${EC[k]}"></span>${k==="grey"?"@default (to assign, with ID)":k}</span>`).join("")
    +`<span class="lg"><span class="sw" style="background:var(--muted);opacity:.35;border-radius:2px"></span>square = median of measurements / effort</span>`
    +`<span class="lg"><span class="sw" style="border:1.6px dashed var(--muted);background:transparent;border-radius:50%"></span>hollow = derived via price/token</span>`
    +`<span class="lg"><span class="sw" style="border-top:1.4px dashed var(--faint);background:transparent;height:0"></span>same source (cost↔tok)</span>`; }

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
    tb.innerHTML='<button data-z="in" title="Zoom +">+</button><button data-z="out" title="Zoom −">−</button><button data-z="reset" title="Reset">⟳</button>';
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
function fillMeta(){   // all source counts + the footer source list derive from the (generated) GROUPS — nothing hand-typed
  const curNode=x=>{const m=x.split("@")[0];return GMODEL[m]&&GMODEL[m].cur;};
  const curGroups=GROUPS.filter(g=>g.n.some(curNode));
  const nSrc=curGroups.length;   // count == what is actually listed (benchmarks touching current models)
  document.querySelectorAll(".nsrc").forEach(e=>e.textContent=nSrc);
  const et=document.getElementById("edge-title"); if(et) et.textContent=`The ${curGroups.length} sources that weave the links`;
  const sl=document.getElementById("src-list");
  if(sl) sl.textContent=curGroups.slice().sort((a,b)=>a.g.localeCompare(b.g,'en')).map(g=>g.g).join(" · ");
}
function renderAll(){drawB();drawPareto();drawTiers();drawMatrix();drawGraph();drawEdgeTable();drawRatiosLegend();drawRatios('chartR');fillMeta();
  ['chartB','chartP','chartG'].forEach(id=>{ const sv=document.getElementById(id); if(sv){ sv.__base=sv.getAttribute("viewBox"); zoomable(sv); } });
  const rr=document.getElementById('chartR'); if(rr) enableRatioZoom(rr);}
renderAll();
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',renderAll);
new MutationObserver(renderAll).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
