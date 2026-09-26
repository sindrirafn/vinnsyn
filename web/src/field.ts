import type { Job, Market, Point, ViewState, Period } from './data';
import { CATEGORY_CENTERS, CATEGORY_COLORS, PROFESSION_CENTERS, PROFESSION_FOCUS, EMPLOYER_CENTERS, EMPLOYER_FOCUS, categoryCounts as scopedCategoryCounts, chartBounds, FOCUS_SKILL, RELATED_SKILL_CENTERS, SKILL_CENTERS, employerCounts, hash, locationCounts, locationIndex, matchesScope, periodKey, periods, professionCounts, professionIndex, relatedSkills, skillCounts, topEmployers, topProfessions, topSkills, trendX, trendY, withoutEmployer, withoutLocation, withoutProfession, withoutSkill } from './data';
import { geographicRadius, ICELAND_OUTLINE, nonspatialPoint, projectGeo } from './geo';
export type FieldState = ViewState & { activePeriod: string | null; reducedMotion: boolean; width: number; height: number };
const TAU = Math.PI * 2;
const smooth = (x: number) => x*x*(3-2*x);
const clamp = (x: number, low: number, high: number) => Math.max(low, Math.min(high,x));

export class ParticleField {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private market: Market;
  private state: FieldState;
  private positions: Float32Array;
  private starts: Float32Array;
  private targets: Float32Array;
  private frame = 0;
  private startTime = performance.now();
  private duration = 1;
  private ratio = 1;
  private trendPeriods: Period[] = [];
  private trendPeriod: Int16Array;
  private relations: number[] = [];
  private visibleSkills: number[] = [];
  private plottedSkills: number[] = [];
  private mobileNodeIds: number[] = [];
  private skillCounts: number[] = [];
  private professionCounts: number[] = [];
  private largestProfession = 1;
  private visibleProfessions: number[] = [];
  private scopeProfession: number | null = null;
  private scopeLocation: number | null = null;
  private locationCounts: number[] = [];
  private employerCounts = new Map<string,number>();
  private visibleEmployers: string[] = [];
  private employerRank = new Map<string,number>();
  private employerTailCenters = new Map<string,Point>();
  private employerKinds = new Map<string,string>();
  private largestEmployer = 1;
  private hasVisibleSkill: Uint8Array;
  private categoryCounts: Uint32Array;
  private largestClassified = 1;
  private renderSamples: number[] = [];
  private frameSamples: number[] = [];
  private lastFrame = 0;
  private pointer: Point | null = null;
  private onPointerMove = (event: PointerEvent) => { this.pointer=[event.clientX/Math.max(1,this.state.width),event.clientY/Math.max(1,this.state.height)]; };
  private onPointerLeave = () => { this.pointer=null; };

  constructor(canvas: HTMLCanvasElement, market: Market, state: FieldState) {
    this.canvas = canvas; this.ctx = canvas.getContext('2d', {alpha:true})!;
    this.market = market; this.state = state;
    for(const employer of market.employers){
      this.employerKinds.set(employer.key,employer.kind);
      let code=2166136261;
      for(const char of employer.key){code^=char.charCodeAt(0);code=Math.imul(code,16777619);}
      const x=hash(code),y=hash(code^0x51b2a719);
      // The long tail belongs to a quiet shared field, while the leading
      // advertisers form readable constellations rather than a star field.
      this.employerTailCenters.set(employer.key,[.43+x*.40,.29+y*.46]);
    }
    this.categoryCounts = new Uint32Array(market.categories.length);
    for(const job of market.jobs)this.categoryCounts[job[1]]++;
    this.largestClassified=Math.max(1,...Array.from(this.categoryCounts.slice(0,-1)));
    const count = market.jobs.length;
    this.positions = new Float32Array(count*2);
    this.starts = new Float32Array(count*2);
    this.targets = new Float32Array(count*2);
    this.trendPeriod = new Int16Array(count).fill(-1);
    this.hasVisibleSkill = new Uint8Array(count);
    this.rebuildDerived();
    market.jobs.forEach((job,i) => {
      const point=this.target(job,i);
      this.positions.set(point,i*2); this.starts.set(point,i*2); this.targets.set(point,i*2);
    });
    this.resize(state.width,state.height);
    window.addEventListener('pointermove',this.onPointerMove,{passive:true});
    window.addEventListener('pointerleave',this.onPointerLeave);
    this.tick=this.tick.bind(this); this.frame=requestAnimationFrame(this.tick);
  }
  resize(width: number,height: number) {
    const oldWidth=this.state.width;
    this.state.width=width; this.state.height=height;
    this.ratio=Math.min(window.devicePixelRatio||1,2);
    this.canvas.width=Math.round(width*this.ratio);
    this.canvas.height=Math.round(height*this.ratio);
    this.ctx.setTransform(this.ratio,0,0,this.ratio,0,0);
    if(oldWidth!==width && (this.state.view==='trend'||this.state.view==='skills'||this.state.view==='professions'||this.state.view==='geography'||this.state.view==='employers')) {
      if(this.state.view==='skills')this.rebuildDerived();
      this.market.jobs.forEach((job,i)=>{
        const point=this.target(job,i);
        this.positions.set(point,i*2);this.starts.set(point,i*2);this.targets.set(point,i*2);
      });
      this.startTime=performance.now();this.duration=1;
    }
  }
  setState(next: FieldState) {
    const structural = next.view!==this.state.view || next.scope.area!==this.state.scope.area || next.scope.profession!==this.state.scope.profession || next.scope.location!==this.state.scope.location || next.scope.skillFilter!==this.state.scope.skillFilter || next.scope.employer!==this.state.scope.employer || next.skill!==this.state.skill || next.share!==this.state.share || next.range!==this.state.range || next.time.from!==this.state.time.from || next.time.to!==this.state.time.to || next.reducedMotion!==this.state.reducedMotion;
    this.state=next;
    if (!structural) return;
    this.starts.set(this.positions);
    this.rebuildDerived();
    this.market.jobs.forEach((job,i) => this.targets.set(this.target(job,i),i*2));
    this.startTime=performance.now(); this.duration=next.reducedMotion?1:1450;
  }
  destroy() { cancelAnimationFrame(this.frame);window.removeEventListener('pointermove',this.onPointerMove);window.removeEventListener('pointerleave',this.onPointerLeave); }
  private rebuildDerived() {
    const parent=withoutProfession(this.state.scope);
    const skillScope=this.state.skill!==null&&this.state.scope.skillFilter===this.state.skill?withoutSkill(this.state.scope):this.state.scope;
    this.scopeProfession=professionIndex(this.market,this.state.scope);
    this.scopeLocation=locationIndex(this.market,this.state.scope);
    this.categoryCounts.set(scopedCategoryCounts(this.market,this.state.scope,this.state.time));
    this.largestClassified=Math.max(1,...Array.from(this.categoryCounts.slice(0,-1)));
    this.professionCounts=professionCounts(this.market,parent,this.state.time).counts;
    this.largestProfession=Math.max(1,...this.professionCounts);
    this.visibleProfessions=topProfessions(this.market,parent,12,this.state.time);
    this.locationCounts=locationCounts(this.market,this.state.scope,this.state.time);
    if(this.state.view==='employers'){
      this.employerCounts=employerCounts(this.market,this.state.scope,this.state.time);
      this.visibleEmployers=topEmployers(this.market,this.employerCounts,12).map(e=>e.key);
      this.employerRank=new Map(this.visibleEmployers.map((key,i)=>[key,i]));
      this.largestEmployer=Math.max(1,...this.employerCounts.values());
    }
    this.skillCounts=skillCounts(this.market,skillScope,this.state.time);
    this.visibleSkills=topSkills(this.market,skillScope,14,this.state.time);
    this.relations=this.state.skill===null ? [] : relatedSkills(this.market,skillScope,this.state.skill,this.state.time).slice(0,4).map(r=>r.skill);
    this.plottedSkills=this.state.skill===null?this.visibleSkills.slice(0,8):[...new Set([this.state.skill,...this.relations,...this.visibleSkills.slice(0,8)])].slice(0,8);
    this.mobileNodeIds=this.plottedSkills;
    const visible=new Set(this.plottedSkills);
    const skillProfession=professionIndex(this.market,skillScope),skillLocation=locationIndex(this.market,skillScope);
    this.market.jobs.forEach((job,i)=>{this.hasVisibleSkill[i]=matchesScope(job,skillScope,skillProfession,skillLocation,this.state.time) && job[3].some(skill=>visible.has(skill))?1:0;});
    this.trendPeriod.fill(-1);
    if (this.state.view!=='trend') { this.trendPeriods=[]; return; }
    const range=this.state.range??'history';
    this.trendPeriods=periods(this.market,this.state.scope,this.state.skill,this.state.share,range,this.state.time);
    const indices=new Map(this.trendPeriods.map((p,i)=>[p.key,i]));
    this.market.jobs.forEach((job,i)=> {
      if (!matchesScope(job,this.state.scope,this.scopeProfession,this.scopeLocation,this.state.time) || (this.state.skill!==null&&!job[3].includes(this.state.skill))) return;
      const period=indices.get(periodKey(job[2],range)||'');
      if (period===undefined) return;
      this.trendPeriod[i]=period;
    });
  }
  private marketPosition(i: number): Point {
    const u=hash(i*13+7), v=hash(i*23+41), lane=hash(i*47+12);
    const x=.035+u*.93;
    const spine=lane<.42 ? .30+.115*Math.sin(u*7.2+.25) : lane<.78 ? .68+.13*Math.sin(u*7.4+2.4) : .49+.16*Math.sin(u*5.2-1.7);
    const spread=(v+hash(i*29+3)+hash(i*59+8))/3-.5;
    return [x, clamp(spine+spread*.49,.055,.945)];
  }
  private organicPoint(i: number, category: number, center: Point, focus=false, population?: number): Point {
    const angle=hash(i*17+category*103)*TAU;
    const radius=Math.pow(hash(i*37+category*29+4),.62);
    const denominator=this.state.view==='professions'?this.largestProfession:this.largestClassified;
    const populationScale=Math.sqrt((population??this.categoryCounts[category]??1)/denominator);
    const mobile=this.state.width<690 && this.state.view==='skills';
    const base=this.state.view==='professions'||this.state.view==='profession'
      ? (focus?.12:.025+.043*populationScale)
      : this.state.view==='skills'
        ? (focus?(mobile?.042:.12):(mobile?.017+.018*populationScale:.019+.037*populationScale))
        : (focus?(mobile?.058:.185):(mobile?.023+.026*populationScale:.040+.064*populationScale));
    const boundary=1+.28*Math.sin(angle*3+category*1.8)+.15*Math.cos(angle*5-category*.9);
    const pocket=hash(i*101+category*7);
    const lobe=pocket<.31?-.42:pocket>.78?.42:0;
    const ax=base*(1+(category%3)*.16), ay=base*(.68+(category%4)*.10)*(mobile?this.state.width/Math.max(1,this.state.height)*1.2:1);
    const rotation=category*.46+.3;
    const localX=Math.cos(angle)*radius*boundary*ax+lobe*base*.65;
    const localY=Math.sin(angle)*radius*boundary*ay+lobe*base*.27;
    return [center[0]+localX*Math.cos(rotation)-localY*Math.sin(rotation),center[1]+localX*Math.sin(rotation)+localY*Math.cos(rotation)];
  }
  private skillCenter(skill: number): Point {
    if(this.state.width<690){
      const rank=this.mobileNodeIds.indexOf(skill);
      if(rank>=0){
        const x=rank%2===0?43:this.state.width/2+27;
        const y=447+79*Math.floor(rank/2);
        return [x/Math.max(1,this.state.width),y/Math.max(1,this.state.height)];
      }
    }
    const rank=this.visibleSkills.indexOf(skill);
    if (this.state.skill===null) return SKILL_CENTERS[rank]??[.76,.82];
    if (skill===this.state.skill) return FOCUS_SKILL;
    const relatedRank=this.relations.indexOf(skill);
    return relatedRank<0 ? SKILL_CENTERS[rank]??[.76,.82] : RELATED_SKILL_CENTERS[relatedRank];
  }
  private professionCenter(rank:number):Point {
    if(this.state.width<690){
      const x=rank%2===0?43:this.state.width/2+27;
      const y=398+73*Math.floor(rank/2);
      return [x/Math.max(1,this.state.width),y/Math.max(1,this.state.height)];
    }
    return PROFESSION_CENTERS[rank];
  }
  private primarySkill(job: Job): number | null {
    const candidates=this.plottedSkills;
    const visible=job[3].filter(skill=>candidates.includes(skill));
    if (!visible.length) return null;
    return visible[Math.floor(hash(job[0]*73+11)*visible.length)];
  }
  private geographicPoint(job:Job,i:number):Point {
    const place=this.market.locations[job[6]];
    const {width,height}=this.state;
    let center:Point;
    let radius:Point;
    if(place.lat!==null&&place.lon!==null){
      center=projectGeo(place.lon,place.lat,width,height,this.scopeLocation!==null&&this.market.locations[this.scopeLocation].lat!==null);
      radius=geographicRadius(this.locationCounts[job[6]],width,height,place.kind);
    }else{
      center=nonspatialPoint(place.key,width);
      const r=Math.min(width<690?13:29,3+Math.sqrt(this.locationCounts[job[6]])*.36);
      radius=[r/width,r/height];
    }
    const angle=hash(i*41+job[6]*137)*TAU;
    const distance=Math.sqrt(hash(i*67+job[6]*23));
    const lobe=1+.16*Math.sin(angle*3+job[6]);
    return [center[0]+Math.cos(angle)*distance*radius[0]*lobe,
      center[1]+Math.sin(angle)*distance*radius[1]*lobe];
  }
  private target(job: Job,i: number): Point {
    const {view,skill,scope}=this.state;
    const category=scope.area;
    if (view==='market') return this.marketPosition(i);
    if (view==='industry' || view==='category') {
      const base={...scope,area:null},profession=professionIndex(this.market,base),location=locationIndex(this.market,base);
      if(!matchesScope(job,base,profession,location,this.state.time))return this.marketPosition(i);
      if (job[1]===this.market.categories.length-1) {
        const point=this.marketPosition(i);
        if (view==='category' && category===job[1]) return [.34+point[0]*.62,.12+point[1]*.76];
        return point;
      }
      const selected=view==='category' && job[1]===category;
      return this.organicPoint(i,job[1],selected?[.70,.52]:CATEGORY_CENTERS[job[1]],selected);
    }
    if(view==='professions'||view==='profession'){
      const parent=withoutProfession(scope);
      if(!matchesScope(job,parent,null,this.scopeLocation,this.state.time)||job[4]===null)return this.marketPosition(i);
      const selected=view==='profession'&&job[4]===this.scopeProfession;
      const rank=this.visibleProfessions.indexOf(job[4]);
      if(rank<0&&!selected)return this.marketPosition(i);
      return this.organicPoint(i,job[4]+71,selected?PROFESSION_FOCUS:this.professionCenter(rank),selected,this.professionCounts[job[4]]);
    }
    if(view==='geography'){
      const parent=withoutLocation(scope);
      return matchesScope(job,parent,this.scopeProfession,null,this.state.time)?this.geographicPoint(job,i):this.marketPosition(i);
    }
    if(view==='employers'){
      const parent=withoutEmployer(scope);
      if(!matchesScope(job,parent,this.scopeProfession,this.scopeLocation,this.state.time))return this.marketPosition(i);
      const selected=scope.employer!==null&&job[7]===scope.employer;
      const rank=this.employerRank.get(job[7]);
      const center=selected?EMPLOYER_FOCUS:rank!==undefined?EMPLOYER_CENTERS[rank]:this.employerTailCenters.get(job[7])??[.80,.81];
      if(this.employerKinds.get(job[7])==='unidentified'&&!selected)return this.marketPosition(i);
      const count=this.employerCounts.get(job[7])??1;
      const scale=Math.sqrt(count/this.largestEmployer);
      const radius=selected?.09:rank!==undefined?.009+.032*scale:.002+Math.min(.006,Math.sqrt(count)*.0008);
      const angle=hash(i*37+17)*TAU,spread=Math.sqrt(hash(i*71+23));
      const lobe=1+.23*Math.sin(angle*3+hash(i*83)*TAU);
      return [center[0]+Math.cos(angle)*radius*spread*lobe,center[1]+Math.sin(angle)*radius*spread*lobe*this.state.width/Math.max(1,this.state.height)];
    }
    if (view==='skills') {
      const skillScope=skill!==null&&scope.skillFilter===skill?withoutSkill(scope):scope;
      const profession=professionIndex(this.market,skillScope),location=locationIndex(this.market,skillScope);
      if (!matchesScope(job,skillScope,profession,location,this.state.time)) return this.marketPosition(i);
      const primary=this.primarySkill(job);
      if (primary===null) return this.marketPosition(i);
      const active=skill!==null && job[3].includes(skill);
      return this.organicPoint(i,primary,active&&this.state.width>=690?FOCUS_SKILL:this.skillCenter(active?skill!:primary),active,this.skillCounts[primary]);
    }
    if (!matchesScope(job,scope,this.scopeProfession,this.scopeLocation,this.state.time) || (skill!==null&&!job[3].includes(skill))) return this.marketPosition(i);
    const period=this.trendPeriod[i];
    if (period<0) return this.organicPoint(i,category??1,[.88,.82],false);
    const row=this.trendPeriods[period];
    const maximum=Math.max(1,...this.trendPeriods.map(p=>p.value));
    const gap=(chartBounds(this.state.width).right-chartBounds(this.state.width).left)/Math.max(1,this.trendPeriods.length-1);
    const scale=.55+.45*Math.sqrt(row.count/Math.max(1,...this.trendPeriods.map(p=>p.count)));
    const radius=Math.sqrt(hash(i*37+17));
    const angle=hash(i*19+period*109)*TAU;
    const rx=Math.min(.043,gap*.29)*scale;
    const ry=Math.min(.046*scale,rx*this.state.width/Math.max(1,this.state.height)*1.2);
    const x=trendX(period,this.trendPeriods.length,this.state.width)+Math.cos(angle)*radius*rx;
    const y=trendY(row.value,maximum,this.state.width)+Math.sin(angle)*radius*ry;
    return [x,y];
  }
  private ambient(x: number,y: number,i: number,t: number,scale: number): Point {
    if (this.state.reducedMotion || scale===0) return [0,0];
    const speed=.32+hash(i*43+5)*.28;
    const phase=hash(i*83+3)*TAU;
    // Coherent currents carry nearby points together; small individual eddies keep them from moving in lockstep.
    const flowX=Math.sin(t*.31+y*6.2+x*2.1)*.013+Math.cos(t*.18+x*7.8-y*2.7)*.009;
    const flowY=Math.cos(t*.27+x*6.4-y*1.4)*.014+Math.sin(t*.21+y*8.1)*.007;
    return [(flowX+Math.sin(t*speed+phase)*.005)*scale,(flowY+Math.cos(t*(speed*.77)+phase)*.005)*scale];
  }
  private drawHalo(x: number,y: number,r: number,color: string,alpha: number) {
    const ctx=this.ctx,w=this.state.width,h=this.state.height;
    const g=ctx.createRadialGradient(x*w,y*h,0,x*w,y*h,r*Math.min(w,h));
    g.addColorStop(0,color); g.addColorStop(1,'transparent');
    ctx.save();ctx.globalAlpha=alpha;ctx.fillStyle=g;ctx.fillRect(x*w-r*h,y*h-r*h,2*r*h,2*r*h);ctx.restore();
  }
  private drawGeoOutline(progress:number) {
    const ctx=this.ctx,{width:w,height:h}=this.state;
    ctx.save();ctx.beginPath();
    ICELAND_OUTLINE.forEach(([lon,lat],i)=>{
      const [x,y]=projectGeo(lon,lat,w,h,this.scopeLocation!==null&&this.market.locations[this.scopeLocation].lat!==null);
      if(i===0)ctx.moveTo(x*w,y*h);else ctx.lineTo(x*w,y*h);
    });
    ctx.closePath();
    ctx.globalAlpha=progress*.035;ctx.fillStyle='#a6c9d0';ctx.fill();
    ctx.globalAlpha=progress*.30;ctx.strokeStyle='#9db9c4';ctx.lineWidth=.9;ctx.stroke();
    ctx.restore();
  }
  private drawTrendLine(progress: number) {
    const ctx=this.ctx,{width:w,height:h,activePeriod}=this.state;
    const category=this.state.scope.area;
    const rows=this.trendPeriods;if (!rows.length) return;
    const max=Math.max(1,...rows.map(p=>p.value));
    const bounds=chartBounds(w);
    const color=category===null?'#a7d2d4':CATEGORY_COLORS[category];
    const points=rows.map((row,i)=>({row,x:trendX(i,rows.length,w)*w,y:trendY(row.value,max,w)*h}));
    ctx.save();
    const veil=ctx.createLinearGradient(0,bounds.top*h,0,bounds.base*h);
    veil.addColorStop(0,color+'24');veil.addColorStop(1,color+'00');
    for(let i=1;i<points.length;i++){
      const a=points[i-1],b=points[i];if(!a.row.total||!b.row.total)continue;
      ctx.globalAlpha=progress*.68;ctx.fillStyle=veil;ctx.beginPath();
      ctx.moveTo(a.x,bounds.base*h);ctx.lineTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.lineTo(b.x,bounds.base*h);ctx.closePath();ctx.fill();
    }
    ctx.globalAlpha=progress*.16;ctx.strokeStyle=color;ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(bounds.left*w,bounds.base*h);ctx.lineTo(bounds.right*w,bounds.base*h);ctx.stroke();
    for(const {row,x,y} of points){
      if(!row.total)continue;
      const selected=activePeriod===row.key;
      const glow=ctx.createRadialGradient(x,y,0,x,y,selected?66:43);
      glow.addColorStop(0,color+(selected?'55':'32'));glow.addColorStop(1,color+'00');
      ctx.globalAlpha=progress;ctx.fillStyle=glow;ctx.fillRect(x-70,y-70,140,140);
      ctx.globalAlpha=progress*(selected?.43:.13);ctx.strokeStyle=color;ctx.lineWidth=1;
      ctx.beginPath();ctx.moveTo(x,y+12);ctx.lineTo(x,bounds.base*h);ctx.stroke();
    }
    for(let i=1;i<points.length;i++){
      const a=points[i-1],b=points[i];if(!a.row.total||!b.row.total)continue;
      ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);
      ctx.globalAlpha=progress*.34;ctx.strokeStyle=color;ctx.lineWidth=5;ctx.shadowColor=color;ctx.shadowBlur=21;ctx.stroke();
      ctx.globalAlpha=progress*.88;ctx.lineWidth=1.7;ctx.shadowBlur=0;ctx.stroke();
    }
    for(const {row,x,y} of points){
      if(!row.total)continue;
      const selected=activePeriod===row.key;
      const radius=selected?8:5;
      ctx.globalAlpha=progress*(selected?1:.88);ctx.strokeStyle=color;ctx.lineWidth=1.1;
      ctx.beginPath();ctx.arc(x,y,radius+5,0,TAU);ctx.stroke();
      ctx.fillStyle=selected?'#f6ffff':color;ctx.beginPath();ctx.arc(x,y,radius,0,TAU);ctx.fill();
    }
    ctx.restore();
  }
  private tick(now: number) {
    const begin=performance.now();if(this.lastFrame)this.frameSamples.push(now-this.lastFrame);this.lastFrame=now;
    const {width:w,height:h,view,scope,skill,activePeriod}=this.state;
    const category=scope.area;
    if (!w||!h) {this.frame=requestAnimationFrame(this.tick);return;}
    const ctx=this.ctx;ctx.clearRect(0,0,w,h);
    const p=smooth(clamp((now-this.startTime)/this.duration,0,1));
    const t=now/1000;
    if(view==='geography')this.drawGeoOutline(clamp((p-.12)/.55,0,1));
    if (view==='category' && category!==null && category!==this.market.categories.length-1) this.drawHalo(.70,.52,.42,CATEGORY_COLORS[category],.075);
    if (view==='profession' && category!==null) this.drawHalo(PROFESSION_FOCUS[0],PROFESSION_FOCUS[1],.35,CATEGORY_COLORS[category],.07);
    if(view==='geography'&&this.scopeLocation!==null){
      const place=this.market.locations[this.scopeLocation];
      if(place.lat!==null&&place.lon!==null){const [x,y]=projectGeo(place.lon,place.lat,w,h,true);this.drawHalo(x,y,w<690?.16:.28,'#b8dbdc',.08);}
    }
    if(view==='employers'&&scope.employer!==null)this.drawHalo(EMPLOYER_FOCUS[0],EMPLOYER_FOCUS[1],.33,'#b9d9dc',.07);
    if (view==='skills' && skill!==null) {const center=this.state.width<690?this.skillCenter(skill):FOCUS_SKILL;this.drawHalo(center[0],center[1],this.state.width<690?.13:.36,'#c3dfe1',.08);}
    if (view==='trend') this.drawTrendLine(clamp((p-.55)/.45,0,1));
    const stride=w<690?2:1;
    const geoParent=withoutLocation(scope),professionParent=withoutProfession(scope),employerParent=withoutEmployer(scope);
    const skillScope=skill!==null&&scope.skillFilter===skill?withoutSkill(scope):scope;
    const skillProfession=professionIndex(this.market,skillScope),skillLocation=locationIndex(this.market,skillScope);
    for (let i=0;i<this.market.jobs.length;i++) {
      const job=this.market.jobs[i],index=i*2;
      const baseX=this.starts[index]+(this.targets[index]-this.starts[index])*p;
      const baseY=this.starts[index+1]+(this.targets[index+1]-this.starts[index+1])*p;
      const ambientScale=view==='market'?1:view==='industry'?.48:view==='category'?.38:view==='professions'||view==='profession'?.36:view==='skills'?.32:view==='geography'?.18:view==='employers'?.20:.13;
      let [dx,dy]=this.ambient(baseX,baseY,i,t,ambientScale);
      if(this.pointer&&!this.state.reducedMotion&&(view==='market'||view==='industry')){
        const vx=baseX-this.pointer[0],vy=baseY-this.pointer[1];
        const distance=Math.hypot(vx,vy);
        if(distance>0&&distance<.15){const push=Math.pow(1-distance/.15,2)*.012;dx+=vx/distance*push;dy+=vy/distance*push;}
      }
      const x=baseX+dx,y=baseY+dy;this.positions[index]=x;this.positions[index+1]=y;
      if (stride>1 && i%stride!==0) continue;
      const selectedCategory=view==='category' && category===job[1];
      const inScope=matchesScope(job,scope,this.scopeProfession,this.scopeLocation,this.state.time);
      const inSkillScope=matchesScope(job,skillScope,skillProfession,skillLocation,this.state.time);
      const inGeoParent=view==='geography'&&matchesScope(job,geoParent,this.scopeProfession,null,this.state.time);
      const inProfessionParent=matchesScope(job,professionParent,null,this.scopeLocation,this.state.time);
      const inEmployerParent=view==='employers'&&matchesScope(job,employerParent,this.scopeProfession,this.scopeLocation,this.state.time);
      const inFieldBase=matchesScope(job,{...scope,area:null},this.scopeProfession,this.scopeLocation,this.state.time);
      const selectedSkill=skill!==null&&inSkillScope&&job[3].includes(skill);
      const plotted=view==='trend'&&inScope&&(skill===null||selectedSkill)&&this.trendPeriod[i]>=0;
      let alpha=view==='market'?.47:view==='industry'?(inFieldBase?(job[1]===this.market.categories.length-1?.105:this.categoryCounts[job[1]]<700?.86:.63):.008):view==='category'?(inFieldBase?(selectedCategory?(w<690&&this.categoryCounts[job[1]]>3000?.42:.82):.035):.008):view==='professions'?(inProfessionParent&&job[4]!==null&&this.visibleProfessions.includes(job[4])?.73:.018):view==='profession'?(inScope?.86:.018):view==='skills'?(inSkillScope?(skill===null?(this.hasVisibleSkill[i]?.58:.035):selectedSkill?.94:.04):.012):view==='geography'?(inGeoParent?(scope.location===null?(this.market.locations[job[6]].lat===null?(w<690?.08:.32):.63):(inScope?.95:.014)):.008):view==='employers'?(inEmployerParent?(scope.employer!==null?(inScope?.92:.012):this.employerKinds.get(job[7])==='unidentified'?.07:this.employerRank.has(job[7])?.78:.34):.008):(plotted?(activePeriod===null||this.trendPeriods[this.trendPeriod[i]]?.key===activePeriod?.92:.14):.008);
      if (job[1]===this.market.categories.length-1 && view==='category' && category===job[1]) alpha=.54;
      const radius=plotted?(activePeriod===this.trendPeriods[this.trendPeriod[i]]?.key?1.65:1.25):selectedCategory||selectedSkill||view==='profession'&&inScope||view==='geography'&&inScope||view==='employers'&&scope.employer!==null&&inScope?1.2:hash(i*71)>.975?1.35:.75;
      const color=view==='trend'&&plotted?(category===null?'#a7d2d4':CATEGORY_COLORS[category]):view==='skills'&&selectedSkill?'#d7e9e4':CATEGORY_COLORS[job[1]];
      ctx.globalAlpha=alpha;ctx.fillStyle=color;
      if(radius<=.75)ctx.fillRect(x*w,y*h,1.2,1.2);
      else{ctx.beginPath();ctx.arc(x*w,y*h,radius,0,TAU);ctx.fill();}
    }
    ctx.globalAlpha=1;
    this.renderSamples.push(performance.now()-begin);
    if(this.renderSamples.length>=90){
      const median=(values:number[])=>values.slice().sort((a,b)=>a-b)[Math.floor(values.length/2)].toFixed(1);
      this.canvas.dataset.renderMs=median(this.renderSamples);this.canvas.dataset.frameMs=median(this.frameSamples);
      this.renderSamples=[];this.frameSamples=[];
    }
    // Reduced motion still draws a stable frame so resizing and focus changes remain visible.
    this.frame=requestAnimationFrame(this.tick);
  }
}
