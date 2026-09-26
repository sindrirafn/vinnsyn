import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import {
  CATEGORY_CENTERS,CATEGORY_COLORS,FOCUS_SKILL,RELATED_SKILL_CENTERS,SKILL_CENTERS,PROFESSION_CENTERS,EMPLOYER_CENTERS,
  allTime,availableYears,categoryCounts,wholeMarket,loadMarket,locationCounts,locationIndex,matchesScope,parentScope,periods,employerCounts,topEmployers,
  professionCounts,professionIndex,readView,relatedSkills,scopeCount,skillCounts,topLocations,
  topProfessions,topSkills,trendAvailable,trendX,trendY,viewUrl,withoutEmployer,withoutLocation,withoutProfession,withoutSkill,
  type Market,type Scope,type TimeScope,type ViewState
} from './data';
import { nonspatialPoint, projectGeo } from './geo';
import { ParticleField } from './field';
import { localizeField,localizeSkill,preferredLanguage,setPreferredLanguage,translations,type Language } from './i18n';

const state=(view:ViewState['view'],scope:Scope=wholeMarket,skill:number|null=null,time:TimeScope=allTime):ViewState=>({view,scope,skill,share:false,time});
const professionState=(scope:Scope,time:TimeScope=allTime)=>state('profession',scope,null,time);
const geoState=(scope:Scope,time:TimeScope=allTime)=>state('geography',scope,null,time);
type ScopeKey='area'|'profession'|'location'|'skillFilter'|'employer';
function useReducedMotion(){
  const [reduced,setReduced]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(()=>{const q=window.matchMedia('(prefers-reduced-motion: reduce)');const update=()=>setReduced(q.matches);q.addEventListener('change',update);return()=>q.removeEventListener('change',update);},[]);
  return reduced;
}
function parentView(nav:ViewState):ViewState{
  const t=nav.time;
  if(nav.view==='employers')return nav.scope.employer!==null?state('employers',withoutEmployer(nav.scope),null,t):state('industry',{...nav.scope,area:null},null,t);
  if(nav.view==='trend')return nav.skill!==null?state('skills',nav.scope,nav.skill,t):state('skills',nav.scope,null,t);
  if(nav.view==='skills')return nav.scope.location!==null?geoState(nav.scope,t):nav.scope.profession!==null?professionState(nav.scope,t):nav.scope.area!==null?state('category',nav.scope,null,t):state('industry',{...nav.scope,area:null},null,t);
  if(nav.view==='geography')return nav.scope.location!==null?geoState(withoutLocation(nav.scope),t):state('industry',{...nav.scope,area:null},null,t);
  if(nav.view==='profession')return state('professions',withoutProfession(nav.scope),null,t);
  if(nav.view==='professions')return state('industry',{...nav.scope,area:null},null,t);
  if(nav.view==='category')return state('industry',{...nav.scope,area:null},null,t);
  return state('market');
}
function ModeControl({view,go,available,copy}:{view:'skills'|'trend';go:(view:'skills'|'trend')=>void;available:boolean;copy:ReturnType<typeof translations>}){
  return <div className="mode-control" role="group" aria-label={copy.trendMeasure}>
    <button className={view==='skills'?'on':''} aria-pressed={view==='skills'} onClick={()=>go('skills')}>{copy.ecosystem}</button><span aria-hidden="true">/</span>
    <button disabled={!available} title={available?undefined:copy.trendUnavailable} className={view==='trend'?'on':''} aria-pressed={view==='trend'} onClick={()=>go('trend')}>{copy.trend}</button>
  </div>;
}

const DEVELOPMENT_NOTICE_KEY='vinnsyn-development-notice-v1';
function DevelopmentNotice({copy,onContinue}:{copy:ReturnType<typeof translations>;onContinue:()=>void}){
  const continueButton=useRef<HTMLButtonElement>(null);
  useEffect(()=>{continueButton.current?.focus();},[]);
  const notice=copy.developmentNotice;
  return <div className="development-notice" role="presentation">
    <section className="development-card" role="dialog" aria-modal="true" aria-labelledby="development-title" aria-describedby="development-description" aria-label={notice.dialogLabel}>
      <div className="development-signal" aria-hidden="true"><i/><span>Vinnsýn</span></div>
      <div className="development-primary">
        <p className="development-kicker">{copy.developmentBadge}</p>
        <h1 id="development-title">{notice.title}</h1>
        <p id="development-description">{notice.body}</p>
      </div>
      <div className="development-secondary" lang={copy.locale==='is-IS'?'en':'is'}>
        <h2>{notice.otherTitle}</h2><p>{notice.otherBody}</p>
      </div>
      <button ref={continueButton} className="development-continue" onClick={onContinue}>{notice.continue}<span aria-hidden="true">↗</span></button>
    </section>
  </div>;
}

type Lens='fields'|'professions'|'skills'|'geography'|'employers';
function Instrument({market,nav,scopeLabels,onBack,onRemove,onLens,onTime,onTrend,copy}:{
  market:Market;nav:ViewState;scopeLabels:{key:ScopeKey;label:string}[];
  onBack:()=>void;onRemove:(key:ScopeKey)=>void;copy:ReturnType<typeof translations>;
  onLens:(lens:Lens)=>void;onTime:(time:TimeScope,mode:'preview'|'commit')=>void;onTrend:()=>void;
}){
  const years=useMemo(()=>availableYears(market),[market]),min=years[0]?.year??2019,max=years.at(-1)?.year??min;
  const from=nav.time.from??min,to=nav.time.to??max,isAll=nav.time.from===null&&nav.time.to===null;
  const lens:Lens=nav.view==='trend'?(nav.skill!==null||nav.scope.skillFilter!==null?'skills':nav.scope.employer!==null?'employers':nav.scope.location!==null?'geography':nav.scope.profession!==null?'professions':'fields'):nav.view==='industry'||nav.view==='category'?'fields':nav.view==='professions'||nav.view==='profession'?'professions':nav.view==='geography'?'geography':nav.view==='employers'?'employers':'skills';
  const maxCoverage=Math.max(1,...years.map(y=>y.count));
  const canTrend=useMemo(()=>trendAvailable(market,nav.scope,nav.skill),[market,nav.scope.area,nav.scope.profession,nav.scope.location,nav.scope.skillFilter,nav.scope.employer,nav.skill]);
  const origin=useRef<TimeScope|null>(null),latest=useRef<TimeScope>(nav.time);
  latest.current=nav.time;
  const begin=()=>{origin.current={...nav.time};};
  const preview=(next:TimeScope)=>{latest.current=next;onTime(next,'preview');};
  const commit=()=>{if(origin.current){onTime(latest.current,'commit');origin.current=null;}};
  const rangeLabel=isAll?copy.allAvailableTime:from===to?`${from}${to===max?' YTD':''}`:`${from}–${to}${to===max?' YTD':''}`;
  return <aside className="instrument" aria-label="Vinnsýn instrument">
    <div className="instrument-line">
      <button className="history-back" onClick={onBack} aria-label={copy.backLabel}>{copy.back}</button>
      <div className="scope-readout" aria-label={copy.scope}><span className="instrument-kicker">{copy.scope}</span><strong>{copy.market}</strong>
        {scopeLabels.map(item=><button key={item.key} onClick={()=>onRemove(item.key)} aria-label={copy.remove(item.label)} title={copy.remove(item.label)}><span aria-hidden="true">/</span>{item.label}<i aria-hidden="true">×</i></button>)}
      </div>
      <details className="mobile-scope"><summary>{scopeLabels.length?`${scopeLabels[0].label}${scopeLabels[1]?` + ${scopeLabels[1].label}`:''}${scopeLabels.length>2?copy.more(scopeLabels.length-2):''}`:copy.market}</summary><div><strong>{copy.market}</strong>{scopeLabels.map(item=><button key={item.key} onClick={()=>onRemove(item.key)} aria-label={copy.remove(item.label)}>{item.label}<i aria-hidden="true">×</i></button>)}</div></details>
      <div className="lens-selector" role="group" aria-label={copy.viewBy}><span className="instrument-kicker">{copy.viewBy}</span>{(['fields','professions','skills','geography','employers'] as Lens[]).map(value=><button key={value} className={lens===value?'on':''} aria-pressed={lens===value} onClick={()=>onLens(value)}>{copy.lenses[value]}</button>)}</div>
      <button className={`trend-entry ${nav.view==='trend'?'on':''}`} onClick={onTrend} aria-pressed={nav.view==='trend'} disabled={!canTrend} title={canTrend?undefined:copy.trendUnavailable}>{copy.detailedTrend}</button>
    </div>
    <div className="time-instrument" aria-label={copy.time}>
      <div className="time-heading"><span className="instrument-kicker">{copy.time}</span><output aria-live="polite">{rangeLabel}</output><button className={isAll?'on':''} aria-pressed={isAll} onClick={()=>onTime(allTime,'commit')}>{copy.all}</button>
        {[5,3].map(yearsBack=>{const start=Math.max(min,max-yearsBack+1),active=!isAll&&from===start&&to===max;return <button key={yearsBack} className={active?'on':''} aria-pressed={active} onClick={()=>onTime({from:start,to:max},'commit')}>{yearsBack}Y</button>;})}
        <button className={!isAll&&from===max&&to===max?'on':''} aria-pressed={!isAll&&from===max&&to===max} onClick={()=>onTime({from:max,to:max},'commit')}>YTD</button>
      </div>
      <div className="time-track" style={{'--from':`${((from-min)/Math.max(1,max-min))*100}%`,'--to':`${((to-min)/Math.max(1,max-min))*100}%`} as CSSProperties}>
        <div className="coverage-bars" aria-hidden="true">{years.map(y=><i key={y.year} className={`${y.thin?'thin':''} ${y.partial?'partial':''}`} style={{height:`${Math.max(8,y.count/maxCoverage*100)}%`}}/>)}</div>
        <div className="time-selection" aria-hidden="true"/>
        <input type="range" min={min} max={max} value={from} aria-label={copy.startYear} onPointerDown={begin} onFocus={()=>{if(!origin.current)begin();}} onChange={e=>preview({from:Math.min(Number(e.target.value),to),to})} onPointerUp={commit} onBlur={commit}/>
        <input type="range" min={min} max={max} value={to} aria-label={copy.endYear} onPointerDown={begin} onFocus={()=>{if(!origin.current)begin();}} onChange={e=>preview({from,to:Math.max(Number(e.target.value),from)})} onPointerUp={commit} onBlur={commit}/>
      </div>
      <div className="time-years" aria-hidden="true"><span>{min}</span><span>{max} YTD</span></div>
      <p className="coverage-note"><span className="thin-mark" aria-hidden="true"/> {copy.thinCoverage(years.filter(y=>y.thin).map(y=>y.year).join(', '))}</p>
    </div>
  </aside>;
}

export function App(){
  const [market,setMarket]=useState<Market|null>(null),[error,setError]=useState('');
  const [language,setLanguage]=useState<Language>(preferredLanguage);
  const [showDevelopmentNotice,setShowDevelopmentNotice]=useState(()=>{try{return window.localStorage.getItem(DEVELOPMENT_NOTICE_KEY)!=='seen';}catch{return true;}});
  const [nav,setNav]=useState<ViewState>(()=>readView());
  const [activePeriod,setActivePeriod]=useState<string|null>(null),[lockedPeriod,setLockedPeriod]=useState<string|null>(null);
  const [size,setSize]=useState(()=>({width:window.innerWidth,height:window.innerHeight}));
  const [contentReady,setContentReady]=useState(true),[relationsReady,setRelationsReady]=useState(false);
  const [employerQuery,setEmployerQuery]=useState(''),[employerMore,setEmployerMore]=useState(20);
  const depth=useRef(0),previousView=useRef(nav.view),canvas=useRef<HTMLCanvasElement>(null),field=useRef<ParticleField|null>(null),scrubOrigin=useRef<ViewState|null>(null);
  const reducedMotion=useReducedMotion();
  const copy=translations(language),number=useMemo(()=>new Intl.NumberFormat(copy.locale),[copy.locale]);

  function dismissDevelopmentNotice(){
    try{window.localStorage.setItem(DEVELOPMENT_NOTICE_KEY,'seen');}catch{/* A session-only dismissal is still kinder than repeating the notice. */}
    setShowDevelopmentNotice(false);
  }

  useEffect(()=>{setPreferredLanguage(language);document.title=language==='is'?'Vinnsýn — íslenski vinnumarkaðurinn á hreyfingu':'Vinnsýn — the Icelandic job market, in motion';},[language]);

  useEffect(()=>{loadMarket().then(setMarket).catch(e=>setError(e.message));},[]);
  useEffect(()=>{
    if(!market)return;
    const area=nav.scope.area,p=professionIndex(market,nav.scope),l=locationIndex(market,nav.scope);
    let fallback:ViewState|null=null;
    if(area!==null&&(area<0||area>=market.categories.length))fallback=state('industry',{...nav.scope,area:null},null,nav.time);
    else if(nav.view==='category'&&area===null)fallback=state('industry',nav.scope,null,nav.time);
    else if(nav.scope.skillFilter!==null&&(nav.scope.skillFilter>=market.skills.length||scopeCount(market,nav.scope)===0))
      fallback=geoState({...nav.scope,skillFilter:null,location:null},nav.time);
    else if(nav.scope.location!==null&&(l===null||scopeCount(market,nav.scope)===0))
      fallback=geoState(withoutLocation(nav.scope),nav.time);
    else if(nav.scope.profession!==null&&(p===null||scopeCount(market,nav.scope)===0))
      fallback=state('professions',withoutProfession(nav.scope),null,nav.time);
    else if(nav.scope.employer!==null&&(!market.employers.some(e=>e.key===nav.scope.employer)||scopeCount(market,nav.scope)===0))
      fallback=state('employers',withoutEmployer(nav.scope),null,nav.time);
    else if(nav.view==='profession'&&nav.scope.profession===null)
      fallback=state('professions',nav.scope,null,nav.time);
    else if(nav.skill!==null&&(nav.skill>=market.skills.length||!market.jobs.some(job=>matchesScope(job,nav.scope,p,l)&&job[3].includes(nav.skill!))))
      fallback=state('skills',nav.scope,null,nav.time);
    else if(nav.view==='trend'&&!trendAvailable(market,nav.scope,nav.skill))
      fallback=state('skills',nav.scope,nav.skill,nav.time);
    if(fallback){window.history.replaceState(window.history.state,'',viewUrl(fallback));setNav(fallback);}
  },[market,nav]);
  useEffect(()=>{
    const existing=window.history.state?.vinnsynDepth;
    if(typeof existing==='number')depth.current=existing;
    else window.history.replaceState({vinnsynDepth:0},'',window.location.href);
    const canonical=viewUrl(readView());
    if(canonical!==window.location.pathname+window.location.search)window.history.replaceState({vinnsynDepth:depth.current},'',canonical);
    const pop=()=>{depth.current=window.history.state?.vinnsynDepth??0;setNav(readView());setActivePeriod(null);setLockedPeriod(null);};
    const resize=()=>setSize({width:window.innerWidth,height:window.innerHeight});
    window.addEventListener('popstate',pop);window.addEventListener('resize',resize);
    return()=>{window.removeEventListener('popstate',pop);window.removeEventListener('resize',resize);};
  },[]);
  useEffect(()=>{
    if(previousView.current===nav.view)return;
    previousView.current=nav.view;setContentReady(false);
    const timer=window.setTimeout(()=>setContentReady(true),reducedMotion?0:490);
    return()=>window.clearTimeout(timer);
  },[nav.view,reducedMotion]);
  useEffect(()=>{
    if(!market||!canvas.current)return;
    const instance=new ParticleField(canvas.current,market,{...nav,activePeriod,reducedMotion,...size});
    field.current=instance;return()=>{instance.destroy();field.current=null;};
  },[market]);
  useEffect(()=>{field.current?.setState({...nav,activePeriod,reducedMotion,...size});},[nav,activePeriod,reducedMotion,market]);
  useEffect(()=>{field.current?.resize(size.width,size.height);},[size]);
  useEffect(()=>{
    setRelationsReady(false);if(nav.view!=='skills'||nav.skill===null)return;
    const timer=window.setTimeout(()=>setRelationsReady(true),reducedMotion?0:850);
    return()=>window.clearTimeout(timer);
  },[nav.view,nav.skill,reducedMotion]);
  function navigate(next:ViewState){
    if(viewUrl(next)===viewUrl(nav))return;
    depth.current++;window.history.pushState({vinnsynDepth:depth.current},'',viewUrl(next));
    setNav(next);setActivePeriod(null);setLockedPeriod(null);if(window.scrollY)window.scrollTo(0,0);
  }
  function goBack(){if(depth.current>0)window.history.back();else navigate(parentView(nav));}
  function removeScope(key:ScopeKey){
    let scope={...nav.scope};
    if(key==='area')scope.area=null;
    if(key==='profession')scope.profession=null;
    if(key==='location')scope.location=null;
    if(key==='skillFilter')scope.skillFilter=null;
    if(key==='employer')scope.employer=null;
    const view=nav.view==='category'&&scope.area===null?'industry':nav.view==='profession'&&scope.profession===null?'professions':nav.view;
    navigate(state(view,scope,key==='skillFilter'?null:nav.skill,nav.time));
  }
  function instrumentScope(){return nav.skill!==null?{...nav.scope,skillFilter:nav.skill}:nav.scope;}
  function changeLens(lens:Lens){
    const scope=instrumentScope(),time=nav.time;
    if(lens==='fields')navigate(state(scope.area===null?'industry':'category',scope,null,time));
    if(lens==='professions')navigate(state(scope.profession===null?'professions':'profession',scope,null,time));
    if(lens==='skills')navigate(state('skills',scope,scope.skillFilter,time));
    if(lens==='geography')navigate(geoState(scope,time));
    if(lens==='employers')navigate(state('employers',scope,null,time));
  }
  function changeTime(time:TimeScope,mode:'preview'|'commit'){
    const next={...nav,time};
    if(mode==='preview'){
      if(!scrubOrigin.current)scrubOrigin.current=nav;
      window.history.replaceState(window.history.state,'',viewUrl(next));setNav(next);return;
    }
    if(scrubOrigin.current){
      const origin=scrubOrigin.current;scrubOrigin.current=null;
      window.history.replaceState(window.history.state,'',viewUrl(origin));
      depth.current++;window.history.pushState({vinnsynDepth:depth.current},'',viewUrl(next));
      setNav(next);setActivePeriod(null);setLockedPeriod(null);return;
    }
    navigate(next);
  }
  function openTrend(){
    const scope=nav.skill!==null&&nav.scope.skillFilter===nav.skill?withoutSkill(nav.scope):nav.skill!==null?nav.scope:instrumentScope();
    navigate({...state('trend',scope,nav.skill,nav.time),range:nav.range??'history',share:nav.share});
  }
  const area=nav.scope.area,areaName=area===null?(language==='is'?'íslenski vinnumarkaðurinn':'the Icelandic market'):localizeField(language,market?.categories[area]??'');
  const selectedLocation=market?.locations.find(loc=>loc.key===nav.scope.location);
  const selectedProfession=market?.professions.find(p=>p.key===nav.scope.profession);
  const selectedEmployer=market?.employers.find(e=>e.key===nav.scope.employer);
  const filteredSkillName=nav.scope.skillFilter===null?null:localizeSkill(language,market?.skills[nav.scope.skillFilter]??'');
  const scopeParts=[area===null?null:areaName,selectedLocation?.label,selectedProfession?.label,filteredSkillName,selectedEmployer?.label].filter(Boolean) as string[];
  const contextName=scopeParts.length?scopeParts.join(' / '):(language==='is'?'íslenski vinnumarkaðurinn':'the Icelandic market');
  const scopeName=selectedEmployer?.label??selectedProfession?.label??selectedLocation?.label??(area===null?(language==='is'?'íslenski vinnumarkaðurinn':'the Icelandic market'):areaName);
  const professionBase=withoutProfession(nav.scope),geoBase=withoutLocation(nav.scope),employerBase=withoutEmployer(nav.scope);
  const professionContextName=[area===null?null:areaName,selectedLocation?.label,filteredSkillName,selectedEmployer?.label].filter(Boolean).join(' / ')||(language==='is'?'íslenski vinnumarkaðurinn':'the Icelandic market');
  const total=market?scopeCount(market,nav.scope,nav.time):0;
  const professionBaseCount=market?scopeCount(market,professionBase,nav.time):0;
  const geoBaseCount=market?scopeCount(market,geoBase,nav.time):0;
  const counts=useMemo(()=>market?categoryCounts(market,nav.scope,nav.time):[],[market,nav.scope.profession,nav.scope.location,nav.scope.skillFilter,nav.scope.employer,nav.time.from,nav.time.to]);
  const fieldBaseCount=counts.reduce((sum,count)=>sum+count,0);
  const professionData=useMemo(()=>market?professionCounts(market,professionBase,nav.time):{counts:[],unclassified:0},[market,professionBase.area,professionBase.location,professionBase.skillFilter,professionBase.employer,nav.time.from,nav.time.to]);
  const professions=useMemo(()=>market?topProfessions(market,professionBase,12,nav.time):[],[market,professionBase.area,professionBase.location,professionBase.skillFilter,professionBase.employer,nav.time.from,nav.time.to]);
  const remainingProfessions=useMemo(()=>market?topProfessions(market,professionBase,market.professions.length,nav.time).slice(12):[],[market,professionBase.area,professionBase.location,professionBase.skillFilter,professionBase.employer,nav.time.from,nav.time.to]);
  const geoCounts=useMemo(()=>market?locationCounts(market,geoBase,nav.time):[],[market,geoBase.area,geoBase.profession,geoBase.skillFilter,geoBase.employer,nav.time.from,nav.time.to]);
  const locationRanks=useMemo(()=>market?topLocations(market,geoBase,market.locations.length,nav.time):[],[market,geoBase.area,geoBase.profession,geoBase.skillFilter,geoBase.employer,nav.time.from,nav.time.to]);
  const employerData=useMemo(()=>market&&nav.view==='employers'?employerCounts(market,employerBase,nav.time):new Map<string,number>(),[market,nav.view,employerBase.area,employerBase.profession,employerBase.location,employerBase.skillFilter,nav.time.from,nav.time.to]);
  const employerRanks=useMemo(()=>market&&nav.view==='employers'?topEmployers(market,employerData,market.employers.length):[],[market,nav.view,employerData]);
  const employerLabels=employerRanks.slice(0,12),employerBaseCount=market&&nav.view==='employers'?scopeCount(market,employerBase,nav.time):0;
  const unidentifiedEmployer=market?.employers.find(e=>e.kind==='unidentified');
  const unidentifiedCount=unidentifiedEmployer?employerData.get(unidentifiedEmployer.key)??0:0;
  const employerNeedle=employerQuery.trim().toLocaleLowerCase();
  const employerDiscovery=employerNeedle?employerRanks.filter(e=>e.label.toLocaleLowerCase().includes(employerNeedle)||e.sourceNames.some(name=>name.toLocaleLowerCase().includes(employerNeedle))).slice(0,20):employerRanks.slice(12,12+employerMore);
  const geoStatus=market?market.locations.map((loc,i)=>({loc,i,count:geoCounts[i]})).filter(row=>row.loc.lat===null&&row.count>0):[];
  const physicalCount=market?locationRanks.reduce((sum,i)=>sum+geoCounts[i],0):0;
  const geoLabels=useMemo(()=>{
    if(!market)return[] as number[];
    const out:number[]=[],used:[number,number][]=[];
    const selected=market.locations.findIndex(loc=>loc.key===nav.scope.location);
    if(selected>=0)return market.locations[selected].lat===null?[]:[selected];
    const order=locationRanks;
    const limit=size.width<690?4:9;
    for(const i of order){
      const loc=market.locations[i],point=projectGeo(loc.lon!,loc.lat!,size.width,size.height);
      const x=point[0]*size.width,y=point[1]*size.height;
      if(used.some(([px,py])=>Math.abs(px-x)<(size.width<690?88:105)&&Math.abs(py-y)<(size.width<690?42:42)))continue;
      out.push(i);used.push([x,y]);if(out.length>=limit)break;
    }
    return out;
  },[market,locationRanks,nav.scope.location,size.width,size.height]);
  const skillScope=nav.skill!==null&&nav.scope.skillFilter===nav.skill?withoutSkill(nav.scope):nav.scope;
  const skillContextName=nav.skill!==null&&nav.scope.skillFilter===nav.skill?[area===null?null:areaName,selectedLocation?.label,selectedProfession?.label,selectedEmployer?.label].filter(Boolean).join(' / ')||(language==='is'?'íslenski vinnumarkaðurinn':'the Icelandic market'):contextName;
  const skills=useMemo(()=>market?skillCounts(market,skillScope,nav.time):[],[market,skillScope.area,skillScope.profession,skillScope.location,skillScope.skillFilter,skillScope.employer,nav.time.from,nav.time.to]);
  const visible=useMemo(()=>market?topSkills(market,skillScope,14,nav.time):[],[market,skillScope.area,skillScope.profession,skillScope.location,skillScope.skillFilter,skillScope.employer,nav.time.from,nav.time.to]);
  const prominent=visible.slice(0,8);
  const related=useMemo(()=>market&&nav.skill!==null?relatedSkills(market,skillScope,nav.skill,nav.time):[],[market,skillScope.area,skillScope.profession,skillScope.location,skillScope.skillFilter,skillScope.employer,nav.skill,nav.time.from,nav.time.to]);
  const nodeIds=nav.skill===null?prominent:[...new Set([nav.skill,...related.slice(0,4).map(row=>row.skill),...prominent])].slice(0,8);
  const range=nav.range??'history';
  const series=useMemo(()=>market&&nav.view==='trend'?periods(market,nav.scope,nav.skill,nav.share,range,nav.time):[],[market,nav.view,nav.scope.area,nav.scope.profession,nav.scope.location,nav.scope.skillFilter,nav.scope.employer,nav.skill,nav.share,range,nav.time.from,nav.time.to]);
  const trendMaximum=Math.max(1,...series.map(row=>row.value)),plotted=series.reduce((sum,p)=>sum+p.count,0);
  const selectedPeriod=series.find(p=>p.key===activePeriod);
  const skillName=nav.skill===null?'':localizeSkill(language,market?.skills[nav.skill]??'');
  const denominator=market?scopeCount(market,skillScope,nav.time):0;
  const skillShare=nav.skill!==null?((skills[nav.skill]||0)/Math.max(1,denominator)*100).toFixed(1):'0';
  const trendBase=parentScope(nav.scope);
  const trendBaseName=trendBase.employer!==null?market?.employers.find(x=>x.key===trendBase.employer)?.label??'selected advertiser':trendBase.location!==null?market?.locations.find(x=>x.key===trendBase.location)?.label??'selected place':trendBase.profession!==null?market?.professions.find(x=>x.key===trendBase.profession)?.label??'selected profession':trendBase.area!==null?market?.categories[trendBase.area]??'job area':'all archived listings';
  const trendComparisonName=nav.time.from!==null||nav.time.to!==null?`${trendBaseName} in this time range`:trendBaseName;
  const trendDenominator=nav.skill!==null?skillContextName:trendBaseName;
  const datedContext=trendDenominator==='all archived listings'?'the archive':trendDenominator;
  const typicalPeriodTotal=useMemo(()=>{
    const totals=series.filter(p=>!p.partial&&p.total>0).map(p=>p.total).sort((a,b)=>a-b);
    return totals[Math.floor(totals.length/2)]??0;
  },[series]);
  const thinPeriods=useMemo(()=>series.filter(p=>!p.partial&&p.total>0&&p.total<typicalPeriodTotal*.35),[series,typicalPeriodTotal]);
  const thinPeriodKeys=new Set(thinPeriods.map(p=>p.key));
  const genericTrend=nav.view==='trend'&&nav.skill===null;
  const categoryShare=area!==null&&market?((counts[area]||0)/Math.max(1,fieldBaseCount)*100).toFixed(1):'0';
  const professionCoverage=professionBaseCount?((professionBaseCount-professionData.unclassified)/professionBaseCount*100).toFixed(0):'0';
  const locationCoverage=geoBaseCount?(physicalCount/geoBaseCount*100).toFixed(0):'0';
  const displayedGeoCount=selectedLocation?geoCounts[market?.locations.indexOf(selectedLocation)??-1]??0:geoBaseCount;
  const selectedColor=area===null?'#b6d4d2':CATEGORY_COLORS[area];
  const activeSkillName=nav.skill!==null?localizeSkill(language,market?.skills[nav.skill]??''):filteredSkillName;
  const scopeLabels=[
    area===null?null:{key:'area' as const,label:areaName},
    selectedProfession?{key:'profession' as const,label:selectedProfession.label}:null,
    selectedLocation?{key:'location' as const,label:selectedLocation.label}:null,
    activeSkillName?{key:'skillFilter' as const,label:activeSkillName}:null,
    selectedEmployer?{key:'employer' as const,label:selectedEmployer.label}:null
  ].filter(Boolean) as {key:ScopeKey;label:string}[];

  return <main className={`app view-${nav.view} ${nav.skill!==null?'has-selection':''} ${nav.scope.location!==null?'has-location':''} ${nav.scope.employer!==null?'has-employer':''}`}>
    <canvas ref={canvas} className="field" aria-hidden="true"/>
    <header className="masthead"><button className="brand" onClick={()=>navigate(state('market'))} aria-label={copy.brandDescription}>Vinn<span>sýn</span><i aria-hidden="true"/></button><span className="development-badge" title={copy.developmentBadge}>{copy.developmentBadge}</span><span className="masthead-note">{copy.masthead}</span><button className="language-toggle" onClick={()=>setLanguage(value=>value==='is'?'en':'is')} aria-label={copy.switchLanguage} title={copy.switchLanguage}><span aria-hidden="true">{language==='is'?'ÍS':'EN'}</span><small>{language==='is'?'EN':'ÍS'}</small></button></header>
    {market&&nav.view!=='market'&&<Instrument market={market} nav={nav} scopeLabels={scopeLabels} onBack={goBack} onRemove={removeScope} onLens={changeLens} onTime={changeTime} onTrend={openTrend} copy={copy}/>} 
    {error&&<p className="error" role="alert">{error}</p>}
    {!market&&!error&&<p className="loading">{copy.loading}</p>}
    {market&&<><div className={`content ${contentReady?'ready':''}`}>
      {nav.view==='market'&&<section className="opening" aria-labelledby="opening-title">
        <p className="overline">{copy.archiveOverline}</p><h1 id="opening-title"><span>{number.format(market.jobs.length)}</span><small>{copy.listingsObserved}</small></h1>
        <p className="opening-thought">{copy.openingThought}</p>
        <p className="opening-description">{copy.openingDescription}</p>
        <button className="text-action" onClick={()=>navigate(state('industry'))}>{copy.exploreMarket} <span aria-hidden="true">↗</span></button>
        <button className="quiet-action geography-invitation" onClick={()=>navigate(geoState(wholeMarket))}>{copy.watchIceland}</button>
      </section>}
      {nav.view==='industry'&&<section className="view-intro" aria-labelledby="industry-title">
        <p className="overline">{contextName} · {copy.reorganizedByField}</p><h1 id="industry-title">{copy.whereWorkGathers}</h1>
        <p>{copy.listingsInScope(number.format(fieldBaseCount))}</p>
      </section>}
      {nav.view==='industry'&&<div className="category-labels" aria-label={copy.exploreFields}>{market.categories.map((name,i)=>({name:localizeField(language,name),i})).filter(({i})=>counts[i]>0).map(({name,i})=>{
        const other=i===market.categories.length-1,center=CATEGORY_CENTERS[i];
        return <button key={name} className={`category-label ${other?'unclassified':''}`} style={other?undefined:{left:`${center[0]*100}%`,top:`${center[1]*100}%`,color:CATEGORY_COLORS[i]}} onClick={()=>navigate(state('category',{...nav.scope,area:i},null,nav.time))} aria-label={`${name}: ${number.format(counts[i])} ${copy.listings}, ${copy.inspectGroup}`}><strong>{name}</strong><span>{number.format(counts[i])} {copy.listings}</span></button>;
      })}</div>}
      {nav.view==='category'&&area!==null&&<><section className="category-detail" aria-labelledby="category-title">
        <p className="overline">{copy.closerLook}</p><h1 id="category-title">{areaName}<span className="title-dot" style={{background:selectedColor}}/></h1>
        <p className="large-figure">{number.format(counts[area])}</p><p className="figure-caption">{copy.archivedListings} <span>·</span> {categoryShare}% {copy.ofScope}</p>
        <p className="category-description">{market.categoryDescriptions[area]}. {area===market.categories.length-1?copy.unclassifiedDescription:copy.categoryDescription}</p>
      </section><div className="category-picker" aria-label={copy.chooseField}><span>{copy.chooseField}</span>{market.categories.map((name,i)=>({name:localizeField(language,name),i})).filter(({i})=>counts[i]>0||i===area).map(({name,i})=><button key={name} className={area===i?'on':''} onClick={()=>navigate(state('category',{...nav.scope,area:i},null,nav.time))}>{name}</button>)}</div></>}
      {nav.view==='professions'&&<><section className="profession-intro">
        <p className="overline">{contextName} · {copy.anotherView}</p><h1>{copy.workByProfession}</h1>
        <p>{copy.professionIntro(number.format(professionBaseCount))}</p>
        <small>{copy.provisionalClassified(professionCoverage,number.format(professionData.unclassified))}</small>
      </section><div className="profession-labels" aria-label={copy.professionsIn(contextName)}>{professions.map((i,rank)=>{
        const p=market.professions[i],point=PROFESSION_CENTERS[rank];
        return <button key={p.key} className="profession-label" style={{left:`${point[0]*100}%`,top:`${point[1]*100}%`,color:selectedColor}} onClick={()=>navigate(professionState({...professionBase,profession:p.key},nav.time))} aria-label={`${p.label}, ${number.format(professionData.counts[i])} ${copy.listings} · ${contextName}`}><strong>{p.label}</strong><span>{number.format(professionData.counts[i])} {copy.listings}</span></button>;
      })}</div><div className="profession-footnote"><span>{copy.namedProfessions(professions.length,number.format(professionData.unclassified))}</span>
        {remainingProfessions.length>0&&<details className="remaining-professions"><summary>{copy.exploreSmallerProfessions(remainingProfessions.length)}</summary><div>{remainingProfessions.map(i=><button key={i} onClick={()=>navigate(professionState({...professionBase,profession:market.professions[i].key},nav.time))}>{market.professions[i].label} <small>{professionData.counts[i]}</small></button>)}</div></details>}
      </div></>}
      {nav.view==='profession'&&selectedProfession&&<><section className="profession-detail">
        <p className="overline">{professionContextName} / {copy.profession}</p><h1>{selectedProfession.label}<span className="title-dot" style={{background:selectedColor}}/></h1>
        <p className="large-figure">{number.format(total)}</p><p className="figure-caption">{copy.classifiedListings}</p>
        <p className="category-description">{copy.professionDescription}</p>
        {visible.length===0&&<p className="hint">{copy.noSkillEvidence}</p>}
      </section><div className="profession-picker"><span>{copy.anotherProfession(professionContextName)}</span>{professions.filter(i=>market.professions[i].key!==nav.scope.profession).slice(0,8).map(i=><button key={i} onClick={()=>navigate(professionState({...professionBase,profession:market.professions[i].key},nav.time))}>{market.professions[i].label}</button>)}</div></>}
      {nav.view==='employers'&&<>
        {selectedEmployer?<section className="employer-detail" aria-labelledby="employer-title">
          <p className="overline">{[area===null?null:areaName,selectedProfession?.label,selectedLocation?.label,filteredSkillName].filter(Boolean).join(' / ')||(language==='is'?'íslenski vinnumarkaðurinn':'the Icelandic market')} · {copy.advertiser}</p>
          <h1 id="employer-title">{selectedEmployer.label}<span className="title-dot"/></h1>
          <p className="large-figure">{number.format(employerData.get(selectedEmployer.key)??0)}</p>
          <p className="figure-caption">{copy.archivedListings} · {((employerData.get(selectedEmployer.key)??0)/Math.max(1,employerBaseCount)*100).toFixed(1)}% {copy.ofScope}</p>
          <p className="category-description">{selectedEmployer.kind==='intermediary'?copy.recruitmentIntermediaryDescription:selectedEmployer.kind==='unidentified'?copy.unidentifiedEmployerDescription:copy.employerDescription}</p>
        </section>:<section className="employer-intro" aria-labelledby="employer-title">
          <p className="overline">{contextName} · {copy.gatheredByAdvertiser}</p>
          <h1 id="employer-title">{copy.whoPosted}</h1>
          <p>{copy.advertisersIntro(number.format(employerBaseCount),number.format(employerRanks.length))}</p>
          <small>{copy.advertiserCaveat}</small>
        </section>}
        {!selectedEmployer&&<div className="employer-labels" aria-label={copy.exploreAdvertisers(contextName)}>{employerLabels.map((entry,rank)=>{
          const point=EMPLOYER_CENTERS[rank],count=employerData.get(entry.key)??0;
          return <button key={entry.key} className="employer-label" style={{left:`${point[0]*100}%`,top:`${point[1]*100}%`}} onClick={()=>navigate(state('employers',{...nav.scope,employer:entry.key},null,nav.time))} aria-label={`${entry.label}, ${number.format(count)} ${copy.archivedListings}${entry.kind==='intermediary'?`, ${copy.intermediary}`:''}`} title={`${entry.label} · ${number.format(count)} ${copy.archivedListings}${entry.kind==='intermediary'?` · ${copy.intermediary}`:''}`}><strong>{entry.label}</strong><span>{number.format(count)} {copy.listings}{entry.kind==='intermediary'?` · ${copy.intermediary}`:''}</span></button>;
        })}</div>}
        <div className="employer-discovery">
          {unidentifiedEmployer&&unidentifiedCount>0&&<button className="employer-unidentified" onClick={()=>navigate(state('employers',{...employerBase,employer:unidentifiedEmployer.key},null,nav.time))}>{copy.employerNotIdentified} <small>{number.format(unidentifiedCount)}</small></button>}
          <details key={`${nav.scope.area}-${nav.scope.profession}-${nav.scope.location}-${nav.scope.skillFilter}-${nav.time.from}-${nav.time.to}`}><summary>{copy.exploreNamedAdvertisers(number.format(employerRanks.length))}</summary>
            <div className="employer-discovery-body"><label>{copy.findAdvertiser}<input type="search" value={employerQuery} onChange={e=>setEmployerQuery(e.target.value)} placeholder={copy.advertiserName} autoComplete="off"/></label>
              <div className="employer-discovery-results">{employerDiscovery.map(entry=><button key={entry.key} onClick={()=>navigate(state('employers',{...employerBase,employer:entry.key},null,nav.time))}>{entry.label}<small>{number.format(employerData.get(entry.key)??0)}</small></button>)}
                {employerNeedle&&employerDiscovery.length===0&&<p>{copy.noAdvertiserMatch}</p>}</div>
              {!employerNeedle&&employerRanks.length>12+employerMore&&<button className="employer-show-more" onClick={()=>setEmployerMore(value=>value+20)}>{copy.showMore}</button>}
            </div>
          </details>
          <p>{copy.advertiserNote}</p>
        </div>
      </>}
      {nav.view==='geography'&&<><section className="geo-intro">
        <p className="overline">{contextName} · {copy.located}</p>
        <h1>{selectedLocation?selectedLocation.label:geoBaseCount<100?copy.whereJobsAppear:copy.whereJobsGather}</h1>
        <p className="geo-figure">{number.format(displayedGeoCount)}</p>
        <p className="figure-caption">{selectedLocation?(selectedLocation.lat===null?copy.listingsInGroup:copy.listingsInPlace):copy.archivedListings}</p>
        <p className="geo-description">{selectedLocation?(selectedLocation.lat===null?copy.nonspatialDescription(selectedLocation.label):copy.placeDescription(selectedLocation.kind)):copy.mapDescription(locationCoverage)}</p>
        {selectedLocation&&visible.length===0&&<p className="hint">{copy.noSkillEvidence}</p>}
      </section>
      <div className="geo-labels" aria-label={selectedLocation?copy.selectedLocation(selectedLocation.label):copy.exploreLocations(contextName)}>{geoLabels.map(i=>{
        const loc=market.locations[i],point=projectGeo(loc.lon!,loc.lat!,size.width,size.height,Boolean(selectedLocation));
        return <button key={loc.key} className={`geo-label ${nav.scope.location===loc.key?'selected':''}`} style={{left:`${point[0]*100}%`,top:`${point[1]*100}%`}} onClick={()=>navigate(geoState({...geoBase,location:loc.key},nav.time))} aria-label={`${loc.label}, ${number.format(geoCounts[i])} ${copy.listings}, ${loc.kind} ${copy.centroid}`}><strong>{loc.label}</strong><span>{number.format(geoCounts[i])}</span></button>;
      })}{selectedLocation&&selectedLocation.lat===null&&<div className="geo-satellite-label" style={{left:`${nonspatialPoint(selectedLocation.key,size.width)[0]*100}%`,top:`${nonspatialPoint(selectedLocation.key,size.width)[1]*100}%`}}><strong>{selectedLocation.label}</strong><span>{number.format(displayedGeoCount)}</span></div>}</div>
      {!selectedLocation&&<div className="geo-secondary"><p>{copy.alsoInArchive}</p>{geoStatus.map(({loc,count})=><button key={loc.key} onClick={()=>navigate(geoState({...geoBase,location:loc.key},nav.time))}>{loc.label} <small>{number.format(count)}</small></button>)}
        {locationRanks.length>geoLabels.length&&<details><summary>{copy.exploreOtherPlaces(locationRanks.length-geoLabels.length)}</summary><div>{locationRanks.filter(i=>!geoLabels.includes(i)).map(i=><button key={i} onClick={()=>navigate(geoState({...geoBase,location:market.locations[i].key},nav.time))}>{market.locations[i].label} <small>{geoCounts[i]}</small></button>)}</div></details>}
      </div>}
      <p className="geo-map-note">{copy.mapNote}</p></>}
      {(nav.view==='skills'||nav.view==='trend')&&<section className="skill-copy" aria-labelledby="skill-heading">
        <p className="overline">{skillContextName} · {genericTrend?copy.observedScope:copy.explicitSkills}</p>
        <h1 id="skill-heading">{genericTrend?scopeName:nav.skill===null?copy.skillsInMotion:skillName}</h1>
        {nav.view==='skills'&&nav.skill===null?<><p className="skill-intro">{copy.skillIntro(contextName)}</p><p className="hint">{copy.skillHint}</p></>:<>
          <p className="skill-number">{number.format(genericTrend?total:skills[nav.skill!])}<span>{copy.listings} · {genericTrend?`${(total/Math.max(1,market?scopeCount(market,trendBase,nav.time):1)*100).toFixed(1)}% ${copy.ofScope} ${trendComparisonName}`:`${skillShare}% ${copy.ofScope} ${skillContextName}`}</span></p>
          <ModeControl view={nav.view==='trend'?'trend':'skills'} available={genericTrend||nav.skill!==null&&trendAvailable(market,nav.scope,nav.skill)} copy={copy} go={view=>navigate(view==='trend'&&nav.skill===nav.scope.skillFilter?{...nav,view,scope:withoutSkill(nav.scope)}:{...nav,view})}/>
          {nav.view==='skills'&&nav.skill!==null&&<>{!trendAvailable(market,nav.scope,nav.skill)&&<p className="trend-unavailable">{copy.trendUnavailable}</p>}<div className="related-reading"><p>{copy.oftenMentioned}</p>{related.slice(0,3).map(row=><button key={row.skill} onClick={()=>navigate({...nav,skill:row.skill})}><span>{localizeSkill(language,market.skills[row.skill])}</span><small>{copy.sharedListings(row.count)}</small></button>)}</div></>}
        </>}
      </section>}
      {nav.view==='skills'&&<><svg className={`relation-lines ${relationsReady?'shown':''}`} viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true">{nav.skill!==null&&related.slice(0,4).map((row,i)=>{
        const [x,y]=RELATED_SKILL_CENTERS[i],[sx,sy]=FOCUS_SKILL,midX=(sx+x)/2;
        return <path key={row.skill} d={`M ${sx*1000} ${sy*1000} Q ${midX*1000} ${((sy+y)/2-.04)*1000} ${x*1000} ${y*1000}`} style={{opacity:.18+Math.min(.4,row.count/150)}}/>;
      })}</svg>{visible.length===0&&<p className="empty-evidence">{copy.noSkillMentions}</p>}
        <div className="skill-nodes" aria-label={copy.exploreSkills}>{nodeIds.map(id=>{
          const selected=nav.skill===id,relatedIndex=nav.skill===null?-1:related.findIndex(r=>r.skill===id);
          const point=selected?FOCUS_SKILL:relatedIndex>=0&&relatedIndex<4?RELATED_SKILL_CENTERS[relatedIndex]:SKILL_CENTERS[visible.indexOf(id)]??[.76,.82];
          const dim=nav.skill!==null&&!selected&&(relatedIndex<0||relatedIndex>3);
          const diameter=selected?158:26+Math.sqrt(skills[id]/Math.max(1,skills[prominent[0]]))*90;
          const label=localizeSkill(language,market.skills[id]);
          return <button key={id} className={`skill-node ${selected?'selected':''} ${dim?'dimmed':''}`} style={{left:`${point[0]*100}%`,top:`${point[1]*100}%`}} onClick={()=>navigate({...nav,skill:id})} aria-pressed={selected} aria-label={`${label}, ${skills[id]} ${skillContextName} ${copy.listings}${selected?', selected':''}`}><span className="node-disc" style={{width:diameter,height:diameter}}><span>{number.format(skills[id])}</span></span><strong>{label}</strong></button>;
        })}</div><div className="more-skills"><span>{copy.otherMentions}</span>{visible.slice(8).map(id=><button key={id} className={nav.skill===id?'on':''} onClick={()=>navigate({...nav,skill:id})}>{localizeSkill(language,market.skills[id])} <small>{skills[id]}</small></button>)}</div>
      </>}
      {nav.view==='trend'&&<><p className="trend-overline">{nav.share?`Share among dated listings in ${datedContext}`:`${genericTrend?'Selected listings':'Skill mentions'} among dated listings in ${datedContext}`} · {range==='history'?'archive years':'recent complete quarters'}</p>
        <div className="range-control" role="group" aria-label="Time range"><button className={range==='history'?'on':''} aria-pressed={range==='history'} onClick={()=>navigate({...nav,range:'history'})}>All years</button><span>/</span><button className={range==='recent'?'on':''} aria-pressed={range==='recent'} onClick={()=>navigate({...nav,range:'recent'})}>Recent quarters</button></div>
        <div className="measure-control" role="group" aria-label="Trend measure"><button className={!nav.share?'on':''} aria-pressed={!nav.share} onClick={()=>navigate({...nav,share:false})}>Absolute</button><span>/</span><button className={nav.share?'on':''} aria-pressed={nav.share} onClick={()=>navigate({...nav,share:true})}>Share of jobs</button></div>
        {thinPeriods.length>0&&<p className="trend-coverage">Thin archive coverage: {thinPeriods.slice(0,3).map(p=>p.label).join(', ')}{thinPeriods.length>3?' and others':''}. Compare those periods with care.</p>}
        <div className="period-targets" aria-label={`Inspect ${range==='history'?'a year':'a quarter'}`}>{series.map((row,i)=>row.total>0?<button key={row.key} className={`${activePeriod===row.key?'active':''} ${thinPeriodKeys.has(row.key)?'thin':''}`} style={{left:`${trendX(i,series.length,size.width)*100}%`,top:`${trendY(row.value,trendMaximum,size.width)*100}%`}} onMouseEnter={()=>setActivePeriod(row.key)} onMouseLeave={()=>setActivePeriod(lockedPeriod)} onFocus={()=>setActivePeriod(row.key)} onClick={()=>{const next=lockedPeriod===row.key?null:row.key;setLockedPeriod(next);setActivePeriod(next);}} aria-pressed={lockedPeriod===row.key} aria-label={`${row.label}: ${row.count} of ${row.total} dated listings in ${datedContext}, ${row.total?(row.count/row.total*100).toFixed(1):0}%${thinPeriodKeys.has(row.key)?', thin archive coverage':''}`}><span aria-hidden="true"/></button>:null)}</div>
        <div className={`time-axis ${series.length===1?'single':''}`} aria-hidden="true">{series.length===1?<span>{series[0].label}</span>:<><span>{series[0]?.label}</span><span>{series[Math.floor(series.length/2)]?.label}</span><span>{series.at(-1)?.label}</span></>}</div>
        <div className="trend-reading" aria-live="polite">{selectedPeriod?<><strong>{selectedPeriod.label}{thinPeriodKeys.has(selectedPeriod.key)?' · thin coverage':''}</strong><span>{number.format(selectedPeriod.count)} listings · {selectedPeriod.total?(selectedPeriod.count/selectedPeriod.total*100).toFixed(1):'0'}% of {number.format(selectedPeriod.total)} dated listings in {datedContext}{selectedPeriod.partial?' · year to date':''}</span></>:<><strong>{number.format(plotted)} dated {genericTrend?'listings':'mentions'} shown</strong><span>Select a glowing point to inspect its observations. Select it again to clear.</span></>}</div>
        <p className="trend-caveat">{series.length?range==='history'?series.length===1?`${series[0].label} only; it is a partial year.`:`${series[0].label} to ${series.at(-1)?.label}. The first year has at least 20 dated listings in ${datedContext}; ${series.at(-1)?.label} is partial.`:`${series[0].label} to ${series.at(-1)?.label}. These are the latest twelve complete quarters.`:'There are not enough dated observations to chart yet.'} Undated observations stay in the archive. This is observed archive activity, not total Icelandic demand.</p>
      </>}
    </div><footer className="provenance"><span>{copy.basedOn(market.source,number.format(market.jobs.length))}</span><span>{nav.view==='industry'||nav.view==='category'?copy.sourceFields:copy.snapshot(new Date(market.exportedAt).toLocaleDateString(copy.locale,{day:'numeric',month:'short',year:'numeric'}))}</span></footer></>}
    {showDevelopmentNotice&&<DevelopmentNotice copy={copy} onContinue={dismissDevelopmentNotice}/>}</main>;
}
