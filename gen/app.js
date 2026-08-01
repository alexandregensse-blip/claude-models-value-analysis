const MODELS = {
  "fable-5":   {label:"Fable 5",   c:"--fable5"},
  "opus-5":    {label:"Opus 5",    c:"--opus5"},
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
// Solve a small n×n linear system by Gaussian elimination (n ≤ 3) — used for the price-envelope fit.
// Returns null on a singular system so the caller can fall back to a lower-order fit.
function solveN(A,b){ const n=b.length, M=A.map((r,i)=>[...r,b[i]]);
  for(let c=0;c<n;c++){ let piv=c; for(let r=c+1;r<n;r++) if(Math.abs(M[r][c])>Math.abs(M[piv][c])) piv=r; [M[c],M[piv]]=[M[piv],M[c]];
    if(Math.abs(M[c][c])<1e-12) return null;
    for(let r=0;r<n;r++){ if(r===c) continue; const f=M[r][c]/M[c][c]; for(let k=c;k<=n;k++) M[r][k]-=f*M[c][k]; } }
  return M.map((r,i)=>r[n]/M[i][i]); }

// COST & QUALITY grids: relative [central, ci_lo, ci_hi] per (model, effort), anchored Opus 4.8 @medium = 1.0,
// computed in build.py (cost_grid / ratio_grid) from measured same-task ratios.
const COSTGRID=__COSTGRID__;
const QUALGRID=__QUALGRID__;   // {model:{effort:[central, lo, hi]}} — median + robust Huber ±1.5·MAD band (asymmetric, centred on median)

// ============ shared chart helpers (used by both the landscape §1 and the Pareto) ============
// Quality axis as a symlog around parity (1.0): dilates the crowded near-parity band, compresses the sparse tails.
const SQ=0.045, symT=v=>Math.sign(v-1)*Math.log(1+Math.abs(v-1)/SQ), symTinv=u=>1+Math.sign(u)*SQ*(Math.exp(Math.abs(u))-1);
// Zoom/pan work in the axes' SCREEN-LINEAR coordinates: X is linear in log10(cost), Y in symT(quality).
// A chart's "view" = [xlo,xhi (log-cost), tLo,tHi (symT-quality)]. Default = data bounds; a stored s.__view overrides it,
// so zoom re-renders the chart (ticks + labels recompute at fixed size) instead of scaling the whole SVG.
const defView=(xmn,xmx,ymn,ymx)=>[Math.log10(xmn)-0.06,Math.log10(xmx)+0.06,symT(ymn)-0.12,symT(ymx)+0.12];
const viewAxes=(v,mL,iw,mT,ih,yp)=>({
  X:val=>mL+(Math.log10(val)-v[0])/(v[1]-v[0])*iw,
  Y:val=>mT+yp+(1-(symT(val)-v[2])/(v[3]-v[2]))*(ih-2*yp) });
// Two-line axis title: big main label + small precision on the next line (a second tspan; under rotation it sits
// alongside, toward the plot). rot = optional transform string.
function axisTitle(s,x,y,main,sub,rot){
  const t=el("text",{x,y,fill:cvar('--muted'),"text-anchor":"middle"}); if(rot) t.setAttribute("transform",rot);
  const a=el("tspan",{x,"font-size":15,"font-weight":700}); a.textContent=main; t.appendChild(a);
  const b=el("tspan",{x,dy:15,"font-size":10.5,fill:cvar('--faint'),"font-weight":400}); b.textContent=sub; t.appendChild(b);
  s.appendChild(t);
}
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

// UNCERTAINTY-AWARE price envelope: each frontier couple contributes 5 weighted samples to the fit — its centre (w=0.5)
// and the four IC extremities (cost lo/hi, quality lo/hi; w=0.125 each). A wide IC thus smears the point over its box
// instead of pinning the curve to an over-precise centre.  Fit: log10(cost) = g(T(quality)).
//
// SHAPE: log10(cost) = a + b·u + c·(e^{k·u} − 1)/k, with u = T(q) − T(min) and b, c ≥ 0. Then g'(u) = b + c·e^{k·u}
// ≥ 0 for EVERY u, positive or negative — monotone by construction, everywhere, extrapolation included. The price of
// quality cannot fall as quality rises; a decreasing stretch is a fitting artefact, not a shape, and since every value
// index is a distance to this curve the artefact would propagate to all of them.
// Fitted on ALL measured couples, not only the Pareto frontier. The frontier is by definition the CHEAPEST couple at
// each quality: a regression through it is neither the frontier itself nor a market rate, and with one model
// dominating a long stretch it collapses to 7 points, 5 of them a single effort ladder, with 64% of the quality axis
// empty. The dominated couples are real measurements of what that quality costs — they are what populates the gap.
// So the curve reads as "what a given quality typically costs", and a couple's distance to it as how far it beats or
// trails the going rate.
// The exponential term matters because the cloud is not parabolic: cost climbs gently across most of the quality
// range then steepens sharply near the ceiling — curvature that GROWS. k is profiled over a small grid by weighted
// SSE; as k → 0 the basis degenerates to a plain quadratic, so this is a strict generalisation.
// INFLUENCE GRADED BY DISTANCE TO THE PARETO FRONTIER. Fitting every couple equally lets strictly-dominated models —
// worse on both axes than something else — pull the curve; fitting the frontier alone throws away the measurements
// that populate the middle. So each couple's weight is graded by how far it sits from the frontier, measured the same
// way everything else in this report is, in log-cost:
//     d = log10(cost) − log10(cheapest couple offering AT LEAST this quality)
// d is exactly 0 on the frontier (the couple qualifies against itself), needs no interpolation, and grows with how
// much you overpay for what you get. Weight = 1 − d/dmax: an efficient couple counts fully, the single worst one not
// at all, everything in between on a straight line. dmax comes from the data, so the grading rescales by itself.
function paretoWeights(pts){
  const d=pts.map(p=>{ let best=Infinity;
    pts.forEach(o=>{ if(o.q>=p.q-1e-9 && o.c<best) best=o.c; });
    return Math.log10(p.c)-Math.log10(best); });
  const dmax=Math.max(...d)||1;
  return d.map(v=>1-v/dmax); }
function fitPriceEnvelope(pts){
  const PW=paretoWeights(pts), samp=[];
  pts.forEach((p,i)=>{ const Tq=symT(p.q), lc=Math.log10(p.c), w=PW[i];
    if(w<=0) return;                                                   // the single worst couple carries no influence
    samp.push([Tq,lc,0.5*w],[Tq,Math.log10(p.clo),0.125*w],[Tq,Math.log10(p.chi),0.125*w],
              [symT(p.qlo),lc,0.125*w],[symT(p.qhi),lc,0.125*w]); });
  const T0=Math.min(...samp.map(s=>s[0])), L=Math.max(...samp.map(s=>s[0]))-T0;
  const fitK=k=>{
    const M=[[0,0,0],[0,0,0],[0,0,0]], V=[0,0,0];                    // weighted normal equations on {1, u, (e^{ku}−1)/k}
    samp.forEach(([Tq,lc,w])=>{ const u=Tq-T0, B=[1,u,(Math.exp(k*u)-1)/k];
      for(let i=0;i<3;i++){ V[i]+=w*B[i]*lc; for(let j=0;j<3;j++) M[i][j]+=w*B[i]*B[j]; } });
    const sse=co=>{ let s=0; for(let i=0;i<3;i++){ s-=2*co[i]*V[i]; for(let j=0;j<3;j++) s+=co[i]*co[j]*M[i][j]; } return s; };
    // Candidate subspaces co = R·y for the b ≥ 0, c ≥ 0 active set: free · b pinned · c pinned · both pinned.
    const RS=[ [[1,0,0],[0,1,0],[0,0,1]], [[1,0],[0,0],[0,1]], [[1,0],[0,1],[0,0]], [[1],[0],[0]] ];
    let best=null;
    RS.forEach(R=>{ const n=R[0].length, A=[], v=[];
      for(let a=0;a<n;a++){ const row=[];
        for(let b=0;b<n;b++){ let s=0; for(let i=0;i<3;i++) for(let j=0;j<3;j++) s+=R[i][a]*M[i][j]*R[j][b]; row.push(s); }
        let s2=0; for(let i=0;i<3;i++) s2+=R[i][a]*V[i]; A.push(row); v.push(s2); }
      const y=solveN(A,v); if(!y) return;
      const co=[0,0,0]; for(let i=0;i<3;i++) for(let a=0;a<n;a++) co[i]+=R[i][a]*y[a];
      if(co[1]<-1e-9 || co[2]<-1e-9) return;                          // infeasible: a negative slope term
      const e=sse(co); if(!best||e<best.e-1e-12) best={co,e}; });
    return best; };
  let best=null, bk=1;
  [0.1,0.25,0.5,0.75,1,1.25,1.5,1.75,2,2.5,3].forEach(k=>{ const r=fitK(k);
    if(r && (!best||r.e<best.e-1e-12)){ best=r; bk=k; } });
  const co=best?best.co:[0,0,0];
  // NOT clamped: the curve extrapolates freely outside the sampled range. Safe here precisely because b, c ≥ 0 makes
  // g' ≥ 0 for every u, positive or negative — extrapolation can never fold back on itself, only flatten out below
  // the data (g → a − c/k + b·u) and steepen above it.
  return t=>{ const u=t-T0; return co[0]+co[1]*u+co[2]*(Math.exp(bk*u)-1)/bk; }; }
// Distance of a couple to the price envelope, in LOG-COST: r = log10(price the frontier charges for that quality)
// − log10(what the couple actually costs). Positive = cheaper than the frontier price, i.e. good value. The interval
// is propagated by the SAME 5-point weighting used to fit the envelope — the couple's centre (½) and its four CI
// extremities (⅛ each) — so a wide interval carries the couple toward what the envelope charges across its whole box.
// Averaging in LOG space is what makes the exponential below a clean ratio (it is a weighted geometric mean).
function valueResidual(gevT,p){ const r=(c,q)=>gevT(symT(q))-Math.log10(c);
  return 0.5*r(p.c,p.q)+0.125*(r(p.clo,p.q)+r(p.chi,p.q)+r(p.c,p.qlo)+r(p.c,p.qhi)); }
// VALUE INDEX, anchored so Opus 4.8 @medium = 100. Being an exponentiated difference of log-distances it is a genuine
// RATIO: 384 reads "3.8× the value-for-money of the anchor", 45 reads "0.45×" — every value above 100 means something,
// which a linear stretch of a bounded score could not offer. Unbounded above by construction: that is the cost of an
// interpretable multiple, and it is why the anchor can sit anywhere in the ranking without breaking the scale.
// The previous tanh squash is deliberately gone — a ratio cannot be squashed without destroying the reading. A wide
// interval therefore now SHIFTS the index (through the weighting above) rather than damping it toward neutral.
const valueIndex=(r,rAnc)=>100*Math.pow(10,r-rAnc);
const anchorResidual=(gevT,pts)=>{ const a=pts.find(p=>p.m==="opus-4.8"&&p.e==="medium"); return a?valueResidual(gevT,a):0; };
function drawB(){
  const s=document.getElementById("chartB"); s.innerHTML="";
  const W=1100,H=619,mL=58,mR=64,mT=22,mB=72, iw=W-mL-mR, ih=H-mT-mB;   // 16:9, fills body; extra bottom margin so the axis title clears the ticks
  // X = cost [central,lo,hi] from COSTGRID · Y = quality [central,lo,hi] from QUALGRID (median + Huber ±1.5·MAD band). Haiku excluded here. Bounds DYNAMIC.
  const pts=[]; let xmn=Infinity,xmx=-Infinity,ymn=Infinity,ymx=-Infinity;
  for(const m in COSTGRID){ if(m==="haiku-4.5") continue; const cg=COSTGRID[m], qg=QUALGRID[m]||{};
    for(const e in cg){ const d=cg[e], q=qg[e]; if(!q) continue;
      xmn=Math.min(xmn,d[1]); xmx=Math.max(xmx,d[2]); ymn=Math.min(ymn,q[1]); ymx=Math.max(ymx,q[2]);   // bounds include the uncertainty ovals (extents) so they stay fully inside
      pts.push({m,e,c:d[0],clo:d[1],chi:d[2],q:q[0],qlo:q[1],qhi:q[2]}); } }
  const yp=8, view=s.__view||defView(xmn,xmx,ymn,ymx);   // stored view (zoom/pan) overrides the data bounds
  s.__view=view; s.__geo={mL,iw,mT,ih,yp};
  const {X,Y}=viewAxes(view,mL,iw,mT,ih,yp), xlo=view[0], xhi=view[1];   // symlog quality axis (dilated near parity 1.0)
  const fmtC=v=>(v<1?v.toFixed(2):v<10?v.toFixed(1):v.toFixed(0));
  logTicks(Math.pow(10,xlo),Math.pow(10,xhi)).forEach(val=>{ const x=X(val);
    s.appendChild(el("line",{x1:x,y1:mT,x2:x,y2:mT+ih,stroke:cvar('--line'),"stroke-width":1}));
    if(tickLbl(val)){const t=el("text",{x,y:mT+ih+20,fill:cvar('--faint'),"font-size":10.5,"text-anchor":"middle"});t.textContent=fmtC(val)+"×";s.appendChild(t);}});
  qGrid(s,Y,mL,iw,mT,ih);
  axisTitle(s,mL+iw/2,H-30,"Relative cost","Opus 4.8 @medium = 1.0 · log scale");
  axisTitle(s,13,mT+ih/2,"Relative quality","Opus 4.8 @medium = 1.0 · dilated near parity",`rotate(-90 13 ${mT+ih/2})`);
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
  const W=1100,H=619,mL=54,mR=64,mT=20,mB=68, iw=W-mL-mR, ih=H-mT-mB;   // extra bottom margin so the axis title clears the ticks
  // X = cost · Y = quality (central + lo/hi for the ovals). All current nodes incl. Haiku (solo).
  const pts=[]; let xmn=Infinity,xmx=-Infinity,ymn=Infinity,ymx=-Infinity;
  for(const m in COSTGRID){ const cg=COSTGRID[m], qg=QUALGRID[m]||{};
    for(const e in cg){ const d=cg[e], q=qg[e]; if(!q) continue;
      xmn=Math.min(xmn,d[1]); xmx=Math.max(xmx,d[2]); ymn=Math.min(ymn,q[1]); ymx=Math.max(ymx,q[2]);
      pts.push({m,e,c:d[0],clo:d[1],chi:d[2],q:q[0],qlo:q[1],qhi:q[2]}); } }
  const yp=10, view=s.__view||defView(xmn,xmx,ymn,ymx);   // stored view (zoom/pan) overrides the data bounds
  s.__view=view; s.__geo={mL,iw,mT,ih,yp};
  const {X,Y}=viewAxes(view,mL,iw,mT,ih,yp), xlo=view[0], xhi=view[1];
  const fmtC=v=>(v<1?v.toFixed(2):v<10?v.toFixed(1):v.toFixed(0));
  logTicks(Math.pow(10,xlo),Math.pow(10,xhi)).forEach(val=>{ const x=X(val);
    s.appendChild(el("line",{x1:x,y1:mT,x2:x,y2:mT+ih,stroke:cvar('--line'),"stroke-width":1}));
    if(tickLbl(val)){const t=el("text",{x,y:mT+ih+18,fill:cvar('--faint'),"font-size":10.5,"text-anchor":"middle"});t.textContent=fmtC(val)+"×";s.appendChild(t);}});
  qGrid(s,Y,mL,iw,mT,ih);
  axisTitle(s,mL+iw/2,H-28,"Relative cost","Opus 4.8 @medium = 1.0 · log scale");
  axisTitle(s,13,mT+ih/2,"Relative quality","Opus 4.8 @medium = 1.0 · dilated near parity",`rotate(-90 13 ${mT+ih/2})`);
  const E=1e-9, dom=(o,p)=>o.c<=p.c+E&&o.q>=p.q-E&&(o.c<p.c-E||o.q>p.q+E);
  const par=pts.filter(p=>!pts.some(o=>dom(o,p))).sort((a,b)=>a.c-b.c);
  const pset=new Set(par.map(p=>p.m+"@"+p.e));
  // HORIZONTAL price envelope log10(cost) = g(T(quality)), fit UNCERTAINTY-AWARE (5 weighted points per couple). Distance
  // is measured in log-COST (cheaper/dearer than the frontier price for your quality) so cost is weighted linearly.
  const gevT=fitPriceEnvelope(pts);                                                                      // all couples, graded by Pareto distance
  const PW=paretoWeights(pts), sw=PW.reduce((a,b)=>a+b,0);                                              // R² uses the SAME grading as the fit
  const xm=pts.reduce((a,p,i)=>a+PW[i]*Math.log10(p.c),0)/sw,
    ssX=pts.reduce((a,p,i)=>a+PW[i]*Math.pow(Math.log10(p.c)-xm,2),0),
    rssX=pts.reduce((a,p,i)=>a+PW[i]*Math.pow(gevT(symT(p.q))-Math.log10(p.c),2),0), R2=1-rssX/ssX;
  { const r2el=document.getElementById("pareto-r2"); if(r2el) r2el.textContent=R2.toFixed(2); }
  { let d="", on=false; const cLo=Math.pow(10,xlo), cHi=Math.pow(10,xhi), Ta=symT(0.45), Tb=symT(1.35);   // draw envelope EDGE TO EDGE (clip to the visible plot rect)
    for(let k=0;k<=160;k++){ const Tt=Ta+(Tb-Ta)*k/160, q=symTinv(Tt), cost=Math.pow(10,gevT(Tt)), yy=Y(q);
      if(cost>=cLo&&cost<=cHi&&yy>=mT&&yy<=mT+ih){ d+=(on?"L":"M")+X(cost)+" "+Y(q)+" "; on=true; } else on=false; }
    s.appendChild(el("path",{d,fill:"none",stroke:cvar('--ink'),"stroke-width":1,"stroke-opacity":0.3})); }   // envelope: faint grey, behind
  const rAnc=anchorResidual(gevT,pts);                                                            // 100 = Opus 4.8 @medium
  const scored=pts.map(p=>({...p,score:valueIndex(valueResidual(gevT,p),rAnc),front:pset.has(p.m+"@"+p.e)}));
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
    +`<span class="lg"><span class="sw" style="border-top:1.5px solid var(--ink);opacity:.5;background:transparent;height:0"></span>Price curve — what a quality typically costs, graded by Pareto distance · R² = ${R2.toFixed(2)}</span>`;
  const pb=document.getElementById("pareto-blocks");   // chained mini-blocks (frontier order), same style as the tier cards but small
  if(pb) pb.innerHTML=par.map((p,i)=>`${i?'<span class="pconn">→</span>':''}<span class="pblock" style="border-color:${cvar(MODELS[p.m].c)}"><b style="color:${cvar(MODELS[p.m].c)}">${MODELS[p.m].label}</b><span class="pblock-e">${cap(p.e)}</span><span class="pblock-n">${p.q.toFixed(2)}× · ${fmtC(p.c)}×</span></span>`).join("");
}
// ---- Value-score table : distance of each couple to the fitted Pareto-frontier envelope (from drawPareto) ----
function fillScoreTable(scored){
  const tb=document.querySelector("#score-tbl tbody"); if(!tb) return; tb.innerHTML="";
  const capE=e=>e==="solo"?"solo":e.charAt(0).toUpperCase()+e.slice(1);
  scored.filter(p=>p.front).slice().sort((a,b)=>b.score-a.score).forEach(p=>{ const col=cvar(MODELS[p.m].c),   // frontier couples only
    // Intensity from the DECADE distance to the anchor, so 2× and 0.5× read equally strong; capped at one decade.
    sc=p.score>=100?cvar('--good'):cvar('--crit'), al=Math.round((0.14+Math.min(Math.abs(Math.log10(p.score/100)),1)*0.52)*100),
    pill=`<span class="scorepill" style="background:color-mix(in srgb, ${sc} ${al}%, transparent); color:${sc}">${Math.round(p.score)}</span>`;
    const tr=document.createElement("tr");
    tr.innerHTML=`<td class="mdl"><span class="dot" style="background:${col}"></span>${MODELS[p.m].label} · ${capE(p.e)}</td>`
      +`<td class="num">${p.c.toFixed(2)}×</td><td class="num">${p.q.toFixed(2)}×</td>`
      +`<td style="min-width:96px">${pill}</td>`;
    tb.appendChild(tr); }); }
// ---- Central-complexity tiers + hidden-prominence crown (data-driven from COSTGRID × QUALGRID) ----
// Each tier targets a CENTRAL complexity q* (relative quality). Among the Pareto-frontier couples we pick the one
// maximising a proximity-weighted yield:  score(p) = exp(−((q−q*)/σ)²) · yield, with yield = quality/cost. The Gaussian
// focuses on couples near the target complexity; yield (which falls with cost) tilts the choice toward value.
// The CROWN uses the HIDDEN PROMINENCE: hid(n) = 2·Sₙ − S_prev − S_next along the frontier (S = signed distance to the
// envelope, as in the value-score table; endpoints get 0). It marks the sharpest knee — the standout couple overall.
// q = target complexity, sig = Gaussian width — BOTH live-adjustable via the tuner (drawTierTuner); the proximity
// is measured in the DILATED metric T(q) (same transform as the fit & the value score), so the windows are consistent
// with the chart. TWCOL = one colour per tier window.
const TWCOL=["#3F8A78","#5B8FF0","#C98A2E","#7C4A6A"];
// q and sig below are PLACEHOLDERS — tierDefaults() overwrites both from the data on load (see there).
const TIERS=[
  {key:"triage",  name:"Grunt work",             q:0.75, sig:0.80, ex:"Classification, tagging, extraction, routing, log/PR triage — run at scale, where throughput and unit cost dominate."},
  {key:"everyday",name:"Everyday tasks",         q:0.95, sig:0.80, ex:"Routine coding, refactors, unit tests, summaries, first-draft agent steps — solid work that doesn't need the frontier."},
  {key:"pro",     name:"Advanced reasoning",     q:1.05, sig:0.80, ex:"Production code review, architecture, hard debugging, customer-facing reasoning — you need essentially flagship quality."},
  {key:"frontier",name:"Cutting-Edge thinking",  q:1.25, sig:0.80, ex:"Research-grade reasoning, novel or ambiguous problems, the hardest agentic runs — a few extra points of capability are worth a premium."},
];
// DATA-DERIVED tier windows. Model quality drifts upward release after release: the weakest couple slowly improves
// and the best one sets a new ceiling, so hardcoded q* go stale — the shipped 1.25 for the top tier had drifted ABOVE
// the best couple actually available (1.19), leaving that tier aiming at a quality nothing reaches. Centres are spread
// evenly across the FRONTIER's quality span in the dilated metric T (the one the Gaussian and the chart already use),
// from the weakest selectable couple to the strongest — so the bottom tracks the floor as it rises, and the top always
// sits exactly on the best model available rather than on a number fixed at some past release.
// sigma follows the spacing on a single rule: adjacent windows cross at HALF weight exactly midway between their
// centres — exp(−((gap/2)/sig)²) = ½ ⟹ sig = gap ⁄ (2·√ln2). The four windows partition the axis instead of
// overlapping arbitrarily, and sigma rescales automatically when the span widens or narrows.
// Sanity check: replaying the pre-Opus-5 grids through this rule returns q* = 0.59 / 0.93 / 1.02 / 1.23, reproducing
// the 0.59 / 0.93 / 1.01 / 1.20 that had been hand-tuned for exactly that data.
let TIERQ={qmn:0.55,qmx:1.30};
function tierDefaults(){
  const rows=[]; for(const m in COSTGRID){ const cg=COSTGRID[m], qg=QUALGRID[m]||{};
    for(const e in cg){ const q=qg[e]; if(q) rows.push({c:cg[e][0],q:q[0]}); } }
  const E=1e-9, dom=(o,p)=>o.c<=p.c+E&&o.q>=p.q-E&&(o.c<p.c-E||o.q>p.q+E);
  const Ts=rows.filter(p=>!rows.some(o=>dom(o,p))).map(p=>symT(p.q));
  if(!Ts.length) return;
  const Tmin=Math.min(...Ts), Tmax=Math.max(...Ts), gap=(Tmax-Tmin)/Math.max(TIERS.length-1,1);
  const sig=gap/(2*Math.sqrt(Math.LN2));
  TIERS.forEach((t,i)=>{ t.q=symTinv(Tmin+i*gap); t.sig=sig; });
  TIERQ={qmn:symTinv(Tmin), qmx:symTinv(Tmax), gap, sig};
}
tierDefaults();
function tierPicks(){
  const rows=[];
  for(const m in COSTGRID){ const cg=COSTGRID[m], qg=QUALGRID[m]||{};
    for(const e in cg){ const q=qg[e]; if(!q) continue; rows.push({m,e,c:cg[e][0],clo:cg[e][1],chi:cg[e][2],q:q[0],qlo:q[1],qhi:q[2]}); } }
  const E=1e-9, dom=(o,p)=>o.c<=p.c+E&&o.q>=p.q-E&&(o.c<p.c-E||o.q>p.q+E);
  const front=rows.filter(p=>!rows.some(o=>dom(o,p))).sort((a,b)=>a.c-b.c);
  // uncertainty-aware price envelope + log-distance r + hidden prominence (crown) — same machinery as the value table
  const gevT=fitPriceEnvelope(rows);                     // ALL couples, not just the frontier
  rows.forEach(p=>p.S=valueResidual(gevT,p));           // r is defined for EVERY couple — frontier and dominated alike
  // Prominence stays a 2nd difference of r, i.e. computed in LOG space where these distances are additive, so it keeps
  // meaning "this couple stands out from its two frontier neighbours". Crown SELECTION only.
  front.forEach((p,i)=>p.hid=(i===0||i===front.length-1)?0:2*p.S-front[i-1].S-front[i+1].S);
  // DISPLAYED SCORE = the value index, anchored so Opus 4.8 @medium = 100 (see valueIndex). The anchor is read from
  // the FULL set of couples, not the frontier: a new model can push it OFF the Pareto frontier — Opus 5 does — but
  // never out of the full set, so the reference always exists. And because the index is a ratio rather than a stretch
  // between two extremes, the anchor sitting low in the ranking no longer distorts anything above it.
  const rAnc=anchorResidual(gevT,rows);
  rows.forEach(p=>p.norm=valueIndex(p.S,rAnc));
  const K=(q,q0,sig)=>Math.exp(-Math.pow((symT(q)-symT(q0))/sig,2));   // proximity in the DILATED metric (consistent with the chart)
  // Tier winner = the frontier couple maximising PROXIMITY × VALUE INDEX. It used to be proximity × (quality ÷ cost),
  // the one raw ratio in the whole report: everything else — the price curve, the residual, the Pareto distance —
  // works in log-cost. That mattered, it did not just offend symmetry. Across the cloud quality spans a factor 2.0
  // while cost spans 14.4, so a linear q/c is driven almost entirely by cost and tilts every tier toward the cheapest
  // couple: it collapsed the top tier onto the same pick as the one below it (3 distinct picks instead of 4).
  // Using the index also makes the number a card SHOWS the criterion that chose it.
  const picks=TIERS.map(t=>({...t, win:front.reduce((a,b)=> K(b.q,t.q,t.sig)*b.norm > K(a.q,t.q,t.sig)*a.norm ? b : a)}));
  const CROWN_Q=1.0, CROWN_SIG=10;                                                                          // best-overall window: Gaussian centred on parity, very wide
  const crown=front.reduce((a,b)=> b.hid*K(b.q,CROWN_Q,CROWN_SIG) > a.hid*K(a.q,CROWN_Q,CROWN_SIG) ? b : a);
  return {picks,crown};
}
function drawTiers(){
  const host=document.getElementById("tier-cards"); if(!host) return;
  const capE=e=>e==="solo"?"solo":e.charAt(0).toUpperCase()+e.slice(1);
  const {picks,crown}=tierPicks();
  // noQ → header-mirror cards & the top crown: drop the "Q* …" prefix, keep the full card layout
  const cardHTML=(q,name,col,w,ex,noQ)=>`<div class="card pad crit tier">
      <div class="tier-head"><span class="tier-name">${noQ?'':`Q* ${q.toFixed(2)} – `}${name}</span></div>
      <div class="tier-top">
        <div class="tier-left">
          <span class="tier-pick" style="color:${col}"><span class="dot" style="background:${col}"></span>${MODELS[w.m].label}${w.e==="solo"?"":" · "+capE(w.e)}</span>
          <span class="tier-nums">Cost <b>${w.c.toFixed(2)}×</b> · Quality <b>${w.q.toFixed(2)}×</b></span>
        </div>
        <div class="tier-yield">${Math.round(w.norm)}</div>
      </div>
      ${ex?`<span class="ex">${ex}</span>`:''}
    </div>`;
  host.innerHTML=picks.map(t=>cardHTML(t.q,t.name,cvar(MODELS[t.win.m].c),t.win,t.ex,false)).join("");        // detailed cards: keep Q*
  const top=document.getElementById("tier-cards-top");
  if(top) top.innerHTML=picks.map(t=>cardHTML(t.q,t.name,cvar(MODELS[t.win.m].c),t.win,t.ex,true)).join("");   // near-header cards: labels only, no Q*
  const c=crown, col=cvar(MODELS[c.m].c);
  const crT=document.getElementById("tier-crown-top");   // best-overall above the header cards: SAME tier-card layout (title · model+cost/quality · big score)
  if(crT) crT.innerHTML=cardHTML(0,"👑 Best overall",col,c,"",true);
  const cr=document.getElementById("tier-crown");   // the detailed section keeps the explained crown
  if(cr) cr.innerHTML=`<div class="card pad crown">
      <div class="tier-q">👑 Best overall</div>
      <div class="crown-model" style="color:${col}"><span class="dot" style="background:${col}"></span>${MODELS[c.m].label}${c.e==="solo"?"":" · "+capE(c.e)}</div>
      <div class="crown-line">Cost <b>${c.c.toFixed(2)}×</b> · Quality <b>${c.q.toFixed(2)}×</b> · Score <b>${Math.round(c.norm)}</b></div>
      <p class="crown-note"><b>Picked</b> by highest <b>local prominence</b> across the frontier (softly centred on parity) — a 2nd difference of the cost-value score S along the frontier, which rewards a clear step up from the cheaper option while the pricier one adds little: the genuine knee. The <b>index</b> shown is the couple's own <b>value index</b> — its IC-weighted distance to the price curve, exponentiated against the anchor&nbsp;: <b>100 = Opus&nbsp;4.8&nbsp;@medium</b>, and the number reads as a multiple of it. The anchor is taken from <b>every</b> couple, dominated ones included, so the reference survives a release that pushes it off the frontier.</p>
    </div>`;
}
// Interactive tuner: draws the four tier windows as Gaussians over the DILATED quality axis (so overlaps are visible)
// plus the frontier couples as ticks, and a q*/σ slider pair per tier that live-updates TIERS and re-renders.
// Redraw ONLY the window SVG (called on every slider move) — leaves the slider DOM untouched so dragging keeps working.
function drawTierWindows(){
  const host=document.getElementById("tier-windows"); if(!host) return;
  const rows=[]; for(const m in COSTGRID){ const cg=COSTGRID[m], qg=QUALGRID[m]||{}; for(const e in cg){ const q=qg[e]; if(q) rows.push({m,e,c:cg[e][0],q:q[0]}); } }
  const E=1e-9, dom=(o,p)=>o.c<=p.c+E&&o.q>=p.q-E&&(o.c<p.c-E||o.q>p.q+E);
  const front=rows.filter(p=>!rows.some(o=>dom(o,p)));
  // Axis spans the DATA range (from tierDefaults) plus half a tier-spacing of padding, so the end windows are not
  // clipped; ticks are generated over whatever that range turns out to be rather than assuming a fixed 0.6–1.2.
  const padT=0.5*(TIERQ.gap||1), Tmn=symT(TIERQ.qmn)-padT, Tmx=symT(TIERQ.qmx)+padT;
  const qmn=symTinv(Tmn), qmx=symTinv(Tmx);
  const W=1100,H=140,mL=8,mR=8,mT=8,mB=24, iw=W-mL-mR, ih=H-mT-mB;
  const X=q=>mL+(symT(q)-Tmn)/(Tmx-Tmn)*iw;
  let svg=`<svg viewBox="0 0 ${W} ${H}" class="tuner-svg" role="img" aria-label="Tier windows over the dilated quality axis">`;
  const ticks=[]; for(let v=Math.ceil(qmn*10)/10; v<=qmx+1e-9; v=Math.round((v+0.1)*10)/10) ticks.push(v);
  ticks.forEach(v=>{ const x=X(v); svg+=`<line x1="${x}" y1="${mT}" x2="${x}" y2="${mT+ih}" stroke="${cvar('--line')}" stroke-width="1"/><text x="${x}" y="${mT+ih+15}" fill="${cvar('--faint')}" font-size="10" text-anchor="middle">${v.toFixed(1)}</text>`; });
  TIERS.forEach((t,i)=>{ const col=TWCOL[i]; let d=`M ${mL} ${mT+ih}`;
    for(let k=0;k<=140;k++){ const q=qmn+(qmx-qmn)*k/140, g=Math.exp(-Math.pow((symT(q)-symT(t.q))/t.sig,2)); d+=` L ${X(q).toFixed(1)} ${(mT+ih-g*(ih-8)).toFixed(1)}`; }
    d+=` L ${mL+iw} ${mT+ih} Z`;
    svg+=`<path d="${d}" fill="${col}" fill-opacity="0.13" stroke="${col}" stroke-opacity="0.7" stroke-width="1.3"/>`
       +`<line x1="${X(t.q)}" y1="${mT}" x2="${X(t.q)}" y2="${mT+ih}" stroke="${col}" stroke-width="1" stroke-dasharray="3 3"/>`; });
  front.forEach(p=>svg+=`<circle cx="${X(p.q)}" cy="${mT+ih}" r="3.2" fill="${cvar(MODELS[p.m].c)}" stroke="${cvar('--panel')}" stroke-width="1"/>`);
  host.innerHTML=svg+`</svg>`;
}
// Build the tuner ONCE (window container + persistent sliders). Slider input updates state + redraws windows/cards only.
function drawTierTuner(){
  const host=document.getElementById("tier-tuner"); if(!host) return;
  // Slider travel follows the data too: Q* spans the padded quality range the windows are drawn over, and sigma runs
  // from a quarter to triple its derived default — so the useful settings sit in the middle of the travel whatever
  // the current spread of models is, instead of against a stop.
  const padT=0.5*(TIERQ.gap||1), s0=TIERQ.sig||0.8;
  const sQ={lo:symTinv(symT(TIERQ.qmn)-padT).toFixed(2), hi:symTinv(symT(TIERQ.qmx)+padT).toFixed(2)};
  const sS={lo:(0.25*s0).toFixed(2), hi:(3*s0).toFixed(2)};
  let ctl='';
  TIERS.forEach((t,i)=>{ ctl+=`<div class="tuner-row" style="--tw:${TWCOL[i]}"><span class="tuner-name">${t.name}</span>`
    +`<label><span class="lbl">Q*</span><input type="range" min="${sQ.lo}" max="${sQ.hi}" step="0.01" value="${t.q}" data-i="${i}" data-k="q"><b id="tv-q-${i}">${t.q.toFixed(2)}</b></label>`
    +`<label><span class="lbl">σ</span><input type="range" min="${sS.lo}" max="${sS.hi}" step="0.05" value="${t.sig}" data-i="${i}" data-k="sig"><b id="tv-s-${i}">${t.sig.toFixed(2)}</b></label></div>`; });
  host.innerHTML=`<div id="tier-windows"></div><div class="tuner-ctl">${ctl}</div>`;
  drawTierWindows();
  host.querySelectorAll('input[type=range]').forEach(inp=>inp.addEventListener('input',e=>{
    const i=+e.target.dataset.i, k=e.target.dataset.k, v=+e.target.value; TIERS[i][k]=v;
    document.getElementById((k==='q'?'tv-q-':'tv-s-')+i).textContent=v.toFixed(2);
    drawTierWindows(); drawTiers(); }));   // only the SVG + cards redraw; the sliders stay in the DOM → drag continues
}
// ---------- MATRIX (sorted by relative quality desc) — every cell DATA-DRIVEN from COSTGRID / QUALGRID ----------
const fr=x=>x.toFixed(2);
const ciStr=(m,e,v)=> (m==="opus-4.8"&&e==="medium") ? "anchor" : (v[1]===v[2] ? "single source" : `${fr(v[1])}–${fr(v[2])}`);
const relQ=m=>{ const qg=QUALGRID[m]||{}, e=["max","xhigh","high","medium","low","solo"].find(k=>qg[k]); return e?qg[e][0]:0; };   // quality at the model's top effort
const M={};
for(const m in COSTGRID){ const cg=COSTGRID[m]||{}; M[m]={q:relQ(m), tag:MODELS[m].tag};
  ["low","medium","high","xhigh","max","solo"].forEach(e=>{ M[m][e]= cg[e]? [cg[e][0], ciStr(m,e,cg[e])] : null; }); }
function heat(v){
  const t=Math.max(0,Math.min(1,(Math.log10(v)-Math.log10(0.12))/(Math.log10(4.5)-Math.log10(0.12))));
  const dark=document.documentElement.getAttribute('data-theme')==='dark'||(window.matchMedia('(prefers-color-scheme:dark)').matches&&document.documentElement.getAttribute('data-theme')!=='light');
  const al=dark?(0.10+t*0.42):(0.07+t*0.40);
  return `background:color-mix(in srgb, var(--opus48) ${Math.round(al*100)}%, transparent)`;
}
function drawMatrix(){
  const tb=document.querySelector("#matrix-tbl tbody"); tb.innerHTML="";
  const rows=Object.keys(M).sort((a,b)=>M[b].q-M[a].q);
  for(const m of rows){ const md=MODELS[m], tr=document.createElement("tr");
    let row=`<td class="mdl"><span class="dot" style="background:${cvar(md.c)}"></span>${md.label}${M[m].tag?' <span class="pill" title="Cost is strongly task-size dependent — a verbose model swings widely between short and long agentic tasks, hence the wide CI.">size-sensitive</span>':''}</td>`;
    if(M[m].solo){ const c=M[m].solo;   // Haiku 4.5 = single operating point → one merged cell across the 5 effort columns
      row+=`<td colspan="5"><div class="cell num" style="${heat(c[0])}">${c[0].toFixed(2)}<small>merged · ${c[1]}</small></div></td>`;
    } else {
      ["low","medium","high","xhigh","max"].forEach(e=>{ const c=M[m][e];
        row+= c? `<td><div class="cell num" style="${heat(c[0])}">${c[0].toFixed(2)}<small>${c[1]}</small></div></td>`
               : `<td class="na">—</td>`; });
    }
    row+=`<td class="mdl num">${M[m].q.toFixed(2)}×</td>`;
    tr.innerHTML=row; tb.appendChild(tr);
  }
}
// ---------- LINKING GRAPH ----------
// nodes = (model,effort) couples ; edges = a source that measured them on the SAME task.
// DATA-DRIVEN: generated by build.py::groups_data() from raw-data.csv (nodes) + an editorial metadata sidecar
// (label / type / verified config note).
const GROUPS = __GROUPS_DATA__;
const GMODEL = {
 "fable-5":{l:"Fable 5",c:"--fable5",cur:1},"opus-5":{l:"Opus 5",c:"--opus5",cur:1},"opus-4.8":{l:"Opus 4.8",c:"--opus48",cur:1},
 "opus-4.7":{l:"Opus 4.7",c:"--opus47",cur:1},"sonnet-5":{l:"Sonnet 5",c:"--sonnet5",cur:1},
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
const dataAt=(s,px,py)=>{ const g=s.__geo, v=s.__view;   // pixel → view coords (log-cost, symT-quality)
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
  const nSrc=curGroups.length;   // count == what is actually listed (benchmarks touching current models)
  document.querySelectorAll(".nsrc").forEach(e=>e.textContent=nSrc);
  const et=document.getElementById("edge-title"); if(et) et.textContent=`The ${curGroups.length} sources that weave the links`;
  const sl=document.getElementById("src-list");
  if(sl) sl.textContent=curGroups.slice().sort((a,b)=>a.g.localeCompare(b.g,'en')).map(g=>g.g).join(" · ");
}
function renderAll(){drawB();drawPareto();drawTierTuner();drawTiers();drawMatrix();drawEdgeTable();fillMeta();
  ['chartB','chartP'].forEach(id=>{ const sv=document.getElementById(id); if(sv) zoomable(sv); });}
renderAll();
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',renderAll);
new MutationObserver(renderAll).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
