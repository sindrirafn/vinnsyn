export type Job = [id:number, area:number, month:string|null, skills:number[], profession:number|null, method:number|null, location:number, employer:string];
export type Profession = {key:string;label:string};
export type Employer = {key:string;label:string;kind:'advertiser'|'intermediary'|'unidentified';sourceNames:string[]};
export type Location = {key:string;label:string;lat:number|null;lon:number|null;region:string|null;kind:'settlement'|'municipality'|'area'|'remote'|'nationwide'|'multiple'|'outside'|'unknown'};
export type Market = {
  schema:number;source:string;exportedAt:string;categories:string[];skills:string[];
  professions:Profession[];professionMethods:string[];professionClassification:string;
  locations:Location[];locationClassification:string;
  employers:Employer[];employerClassification:string;employerQuality:{sourceField:string;rawDistinct:number;normalizedDistinct:number;missingSourceNames:number;unidentifiedListings:number;intermediaryListings:number;rawSingletonNames:number};
  categoryDescriptions:string[];enrichedListings:number;multipleAreas:number;
  classification:string;skillEvidence:string;jobs:Job[];
};
export type View = 'market'|'industry'|'category'|'professions'|'profession'|'skills'|'trend'|'geography'|'employers';
// Constraints are independent of the current lens. A selected skill becomes a
// persistent scope constraint only when the visitor follows it into Geography.
export type Scope = {area:number|null;profession:string|null;location:string|null;skillFilter:number|null;employer:string|null};
export type TimeScope = {from:number|null;to:number|null};
export type ViewState = {view:View;scope:Scope;skill:number|null;share:boolean;range?:'history'|'recent';time:TimeScope};
export const wholeMarket:Scope={area:null,profession:null,location:null,skillFilter:null,employer:null};
export const allTime:TimeScope={from:null,to:null};
export const areaScope=(area:number):Scope=>({...wholeMarket,area});
export const withoutLocation=(scope:Scope):Scope=>({...scope,location:null});
export const withoutProfession=(scope:Scope):Scope=>({...scope,profession:null});
export const withoutSkill=(scope:Scope):Scope=>({...scope,skillFilter:null});
export const withoutEmployer=(scope:Scope):Scope=>({...scope,employer:null});
export type Point=[number,number];
export type Period={key:string;label:string;count:number;total:number;value:number;partial?:boolean};

export const CATEGORY_CENTERS:Point[]=[
  [.28,.49],[.57,.31],[.77,.51],[.15,.66],[.44,.63],[.79,.74],
  [.85,.19],[.39,.84],[.61,.84],[.23,.79],[.51,.49]
];
export const CATEGORY_COLORS=[
  '#9ac7c0','#c5b9e6','#a9c3d9','#d8c5a9','#c7b8a6',
  '#b8cec3','#b8c5d6','#a9b6cd','#c7c8bf','#b8c9bf','#8b99a9'
];
export const SKILL_CENTERS:Point[]=[
  [.53,.36],[.77,.40],[.85,.65],[.39,.55],[.37,.76],[.47,.82],
  [.58,.83],[.67,.64],[.46,.66],[.81,.82],[.31,.63],[.24,.73],
  [.73,.79],[.89,.78]
];
export const FOCUS_SKILL:Point=[.69,.52];
export const RELATED_SKILL_CENTERS:Point[]=[[.47,.36],[.88,.36],[.88,.70],[.48,.76]];
export const CHART={left:.24,right:.91,top:.47,base:.79};
// These reading positions carry no similarity metric.
export const PROFESSION_CENTERS:Point[]=[
  [.55,.29],[.77,.33],[.88,.53],[.51,.52],[.71,.57],[.91,.75],
  [.43,.73],[.63,.78],[.80,.82],[.45,.43],[.54,.87],[.74,.23]
];
export const PROFESSION_FOCUS:Point=[.70,.52];
// Employer labels take these deliberate reading positions; smaller advertiser
// populations still occupy the surrounding field, without claiming similarity.
export const EMPLOYER_CENTERS:Point[]=[
  [.55,.36],[.69,.40],[.79,.50],[.55,.53],[.68,.59],[.80,.67],
  [.47,.65],[.59,.69],[.70,.70],[.47,.47],[.57,.74],[.66,.31]
];
export const EMPLOYER_FOCUS:Point=[.70,.52];

export async function loadMarket():Promise<Market>{
  const response=await fetch('/market.json');
  if(!response.ok)throw new Error('Market export could not be loaded');
  const data:Market=await response.json();
  if(data.schema!==5||!Array.isArray(data.jobs)||!Array.isArray(data.professions)||!Array.isArray(data.locations)||!Array.isArray(data.employers))throw new Error('Unexpected market export');
  return data;
}
export function hash(n:number):number{
  let x=n|0;x^=x>>>16;x=Math.imul(x,0x7feb352d);x^=x>>>15;
  x=Math.imul(x,0x846ca68b);x^=x>>>16;return(x>>>0)/4294967296;
}
export function professionIndex(market:Market,scope:Scope):number|null{
  if(scope.profession===null)return null;
  const index=market.professions.findIndex(p=>p.key===scope.profession);
  return index<0?null:index;
}
export function locationIndex(market:Market,scope:Scope):number|null{
  if(scope.location===null)return null;
  const index=market.locations.findIndex(p=>p.key===scope.location);
  return index<0?null:index;
}
export function matchesTime(job:Job,time:TimeScope=allTime):boolean{
  if(time.from===null&&time.to===null)return true;
  if(!job[2])return false;
  const year=Number(job[2].slice(0,4));
  return (time.from===null||year>=time.from)&&(time.to===null||year<=time.to);
}
export function matchesScope(job:Job,scope:Scope,profession:number|null=null,location:number|null=null,time:TimeScope=allTime):boolean{
  return (scope.area===null||job[1]===scope.area)
    &&(scope.profession===null||job[4]===profession)
    &&(scope.location===null||job[6]===location)
    &&(scope.skillFilter===null||job[3].includes(scope.skillFilter))
    &&(scope.employer===null||job[7]===scope.employer)
    &&matchesTime(job,time);
}
export function scopeCount(market:Market,scope:Scope,time:TimeScope=allTime):number{
  const profession=professionIndex(market,scope),location=locationIndex(market,scope);
  return market.jobs.reduce((count,job)=>count+(matchesScope(job,scope,profession,location,time)?1:0),0);
}
export function categoryCounts(market:Market,scope:Scope,time:TimeScope=allTime):number[]{
  const counts=Array(market.categories.length).fill(0) as number[];
  const base={...scope,area:null},profession=professionIndex(market,base),location=locationIndex(market,base);
  for(const job of market.jobs)if(matchesScope(job,base,profession,location,time))counts[job[1]]++;
  return counts;
}
export function professionCounts(market:Market,scope:Scope,time:TimeScope=allTime):{counts:number[];unclassified:number}{
  const counts=Array(market.professions.length).fill(0) as number[];let unclassified=0;
  const base=withoutProfession(scope),location=locationIndex(market,base);
  for(const job of market.jobs)if(matchesScope(job,base,null,location,time)){
    if(job[4]===null)unclassified++;else counts[job[4]]++;
  }
  return{counts,unclassified};
}
export function topProfessions(market:Market,scope:Scope,limit=12,time:TimeScope=allTime):number[]{
  return professionCounts(market,scope,time).counts.map((count,index)=>({count,index}))
    .filter(row=>row.count>0).sort((a,b)=>b.count-a.count||market.professions[a.index].label.localeCompare(market.professions[b.index].label))
    .slice(0,limit).map(row=>row.index);
}
export function locationCounts(market:Market,scope:Scope,time:TimeScope=allTime):number[]{
  const counts=Array(market.locations.length).fill(0) as number[];
  const base=withoutLocation(scope),profession=professionIndex(market,base);
  for(const job of market.jobs)if(matchesScope(job,base,profession,null,time))counts[job[6]]++;
  return counts;
}
export function topLocations(market:Market,scope:Scope,limit=9,time:TimeScope=allTime):number[]{
  return locationCounts(market,scope,time).map((count,index)=>({count,index}))
    .filter(row=>row.count>0&&market.locations[row.index].lat!==null)
    .sort((a,b)=>b.count-a.count||market.locations[a.index].label.localeCompare(market.locations[b.index].label))
    .slice(0,limit).map(row=>row.index);
}
export function skillCounts(market:Market,scope:Scope,time:TimeScope=allTime):number[]{
  const counts=Array(market.skills.length).fill(0) as number[];
  const profession=professionIndex(market,scope),location=locationIndex(market,scope);
  for(const job of market.jobs)if(matchesScope(job,scope,profession,location,time))for(const skill of job[3])counts[skill]++;
  return counts;
}
export function topSkills(market:Market,scope:Scope,limit=14,time:TimeScope=allTime):number[]{
  return skillCounts(market,scope,time).map((count,skill)=>({count,skill}))
    .filter(row=>row.count>0).sort((a,b)=>b.count-a.count||market.skills[a.skill].localeCompare(market.skills[b.skill]))
    .slice(0,limit).map(row=>row.skill);
}
export function employerCounts(market:Market,scope:Scope,time:TimeScope=allTime):Map<string,number>{
  const counts=new Map<string,number>();
  const base=withoutEmployer(scope),profession=professionIndex(market,base),location=locationIndex(market,base);
  for(const job of market.jobs)if(matchesScope(job,base,profession,location,time))counts.set(job[7],(counts.get(job[7])??0)+1);
  return counts;
}
export function topEmployers(market:Market,counts:Map<string,number>,limit=12):Employer[]{
  return market.employers.filter(e=>(counts.get(e.key)??0)>0&&e.kind!=='unidentified')
    .sort((a,b)=>(counts.get(b.key)??0)-(counts.get(a.key)??0)||a.label.localeCompare(b.label))
    .slice(0,limit);
}
export function relatedSkills(market:Market,scope:Scope,selected:number,time:TimeScope=allTime):{skill:number;count:number}[]{
  const counts=Array(market.skills.length).fill(0) as number[];
  const profession=professionIndex(market,scope),location=locationIndex(market,scope);
  for(const job of market.jobs)if(matchesScope(job,scope,profession,location,time)&&job[3].includes(selected))
    for(const skill of job[3])if(skill!==selected)counts[skill]++;
  return counts.map((count,skill)=>({skill,count})).filter(row=>row.count>0)
    .sort((a,b)=>b.count-a.count||market.skills[a.skill].localeCompare(market.skills[b.skill]));
}
export function parentScope(scope:Scope):Scope{
  if(scope.employer!==null)return withoutEmployer(scope);
  if(scope.location!==null)return withoutLocation(scope);
  if(scope.profession!==null)return withoutProfession(scope);
  if(scope.skillFilter!==null)return{...scope,skillFilter:null};
  if(scope.area!==null)return wholeMarket;
  return wholeMarket;
}
export function availableYears(market:Market):{year:number;count:number;thin:boolean;partial:boolean}[]{
  const totals=new Map<number,number>();
  for(const job of market.jobs)if(job[2]){const year=Number(job[2].slice(0,4));totals.set(year,(totals.get(year)??0)+1);}
  const complete=[...totals.entries()].filter(([year])=>year<new Date(market.exportedAt).getUTCFullYear()).map(([,count])=>count).sort((a,b)=>a-b);
  const median=complete[Math.floor(complete.length/2)]??1,current=new Date(market.exportedAt).getUTCFullYear();
  return [...totals.entries()].sort((a,b)=>a[0]-b[0]).map(([year,count])=>({year,count,thin:year<current&&count<median*.35,partial:year===current}));
}
export function periodKey(month:string|null,range:'history'|'recent'='recent'):string|null{
  if(!month||month.length<7)return null;
  const year=Number(month.slice(0,4)),quarter=Math.ceil(Number(month.slice(5,7))/3);
  return range==='history'?String(year):`${year}-Q${quarter}`;
}
export function periods(market:Market,scope:Scope,skill:number|null,share:boolean,range:'history'|'recent'='history',time:TimeScope=allTime):Period[]{
  const exported=new Date(market.exportedAt),currentYear=exported.getUTCFullYear();
  const currentQuarter=Math.ceil((exported.getUTCMonth()+1)/3);
  const lastYear=currentQuarter===1?currentYear-1:currentYear,lastQuarter=currentQuarter===1?4:currentQuarter-1;
  const base=skill===null?parentScope(scope):scope;
  const baseProfession=professionIndex(market,base),baseLocation=locationIndex(market,base);
  const profession=professionIndex(market,scope),location=locationIndex(market,scope);
  const dated=market.jobs.filter(job=>job[2]&&Number(job[2].slice(0,4))<=currentYear&&matchesScope(job,base,baseProfession,baseLocation,time));
  const result:Period[]=[];
  if(range==='history'){
    const yearly=new Map<number,number>();
    for(const job of dated){const year=Number(job[2]!.slice(0,4));yearly.set(year,(yearly.get(year)??0)+1);}
    const first=[...yearly].filter(([,count])=>count>=20).sort((a,b)=>a[0]-b[0])[0]?.[0];
    if(first===undefined)return[];
    for(let year=first;year<=currentYear;year++)result.push({key:String(year),label:year===currentYear?`${year} YTD`:String(year),count:0,total:0,value:0,partial:year===currentYear});
  }else{
    for(let year=Math.max(2018,lastYear-3);year<=lastYear;year++)for(let quarter=1;quarter<=4;quarter++){
      if(year===lastYear&&quarter>lastQuarter)break;
      result.push({key:`${year}-Q${quarter}`,label:`Q${quarter} ${year}`,count:0,total:0,value:0});
    }
    result.splice(0,Math.max(0,result.length-12));
  }
  const byKey=new Map(result.map(p=>[p.key,p]));
  for(const job of dated){
    const row=byKey.get(periodKey(job[2],range)||'');if(!row)continue;
    row.total++;
    if(matchesScope(job,scope,profession,location)&&(skill===null||job[3].includes(skill)))row.count++;
  }
  for(const row of result)row.value=share&&row.total?row.count/row.total*100:row.count;
  return result;
}
export function trendAvailable(market:Market,scope:Scope,skill:number|null,time:TimeScope=allTime):boolean{
  const rows=periods(market,scope,skill,false,'history',time);
  return rows.reduce((sum,row)=>sum+row.count,0)>=(skill===null?40:20)
    &&rows.filter(row=>row.count>=(skill===null?8:4)).length>=3;
}
export function chartBounds(width:number){return width<690?{left:.13,right:.91,top:.59,base:.79}:CHART;}
export function trendX(index:number,length:number,width=window.innerWidth):number{
  const b=chartBounds(width);return length<=1?(b.left+b.right)/2:b.left+index/(length-1)*(b.right-b.left);
}
export function trendY(value:number,maximum:number,width=window.innerWidth):number{
  const b=chartBounds(width);return b.base-value/Math.max(1,maximum)*(b.base-b.top);
}
export function readView(url=window.location.href):ViewState{
  const q=new URL(url).searchParams,view=q.get('view');
  const category=Number(q.get('category')),skill=Number(q.get('skill')),filterSkill=Number(q.get('filterSkill'));
  const scope:Scope={
    area:q.has('category')&&Number.isInteger(category)&&category>=0&&category<11?category:null,
    profession:q.get('profession')||null,
    location:q.get('location')||null,
    skillFilter:q.has('filterSkill')&&Number.isInteger(filterSkill)&&filterSkill>=0?filterSkill:null,
    employer:q.get('employer')||null
  };
  const validSkill=q.has('skill')&&Number.isInteger(skill)&&skill>=0;
  const from=Number(q.get('from')),to=Number(q.get('to'));
  const time:TimeScope={from:q.has('from')&&Number.isInteger(from)?from:null,to:q.has('to')&&Number.isInteger(to)?to:null};
  if(view==='industry')return{view,scope:{...scope,area:null},skill:null,share:false,time};
  if(view==='category')return{view,scope,skill:null,share:false,time};
  if(view==='professions')return{view,scope:withoutProfession(scope),skill:null,share:false,time};
  if(view==='profession'||view==='geography')return{view,scope,skill:null,share:false,time};
  if(view==='employers')return{view,scope,skill:null,share:false,time};
  if(view==='skills'||view==='trend')return{view,scope,skill:validSkill?skill:null,share:q.get('measure')==='share',range:q.get('range')==='recent'?'recent':'history',time};
  return{view:'market',scope:wholeMarket,skill:null,share:false,time:allTime};
}
export function viewUrl(state:ViewState):string{
  const q=new URLSearchParams();
  if(state.view!=='market')q.set('view',state.view);
  if(state.scope.area!==null)q.set('category',String(state.scope.area));
  if(state.scope.profession!==null)q.set('profession',state.scope.profession);
  if(state.scope.location!==null)q.set('location',state.scope.location);
  if(state.scope.skillFilter!==null)q.set('filterSkill',String(state.scope.skillFilter));
  if(state.scope.employer!==null)q.set('employer',state.scope.employer);
  if(state.time.from!==null)q.set('from',String(state.time.from));
  if(state.time.to!==null)q.set('to',String(state.time.to));
  if((state.view==='skills'||state.view==='trend')&&state.skill!==null)q.set('skill',String(state.skill));
  if(state.view==='trend'&&state.share)q.set('measure','share');
  if(state.view==='trend'&&state.range==='recent')q.set('range','recent');
  const query=q.toString();return query?`${window.location.pathname}?${query}`:window.location.pathname;
}
