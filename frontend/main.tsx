import React,{useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import ReviewBoard from "./app/review-board";
import "./app/globals.css";
type Sample={id:string;label:string;unit:string;value:number|null;observedAt:string|null;ageSeconds:number|null;health:string;hash:string|null;history:{at:string;value:number|null}[]};
type Snapshot={status:string;measurements:Sample[];attempts:{id:number;url:string;retrieved_at:string;result:string;error:string|null}[];speedEnergyIndex:number|null;couplingIndex:number|null;staleSeconds:number};
function Trace({samples}:{samples:Sample["history"]}){
 const good=samples.filter(s=>s.value!==null);
 if(good.length<2)return <p>Waiting for two distinct observations.</p>;
 const lo=Math.min(...good.map(s=>s.value!)),hi=Math.max(...good.map(s=>s.value!)),span=hi-lo||1;
 const first=Date.parse(samples[0].at),duration=Date.parse(samples.at(-1)!.at)-first||1;
 const points=samples.map(s=>s.value===null?null:[(Date.parse(s.at)-first)/duration*300,65-(s.value-lo)/span*55]);
 return <svg viewBox="0 0 300 75" role="img" aria-label="Stored observations over measurement time">{points.map((p,i)=>p&&i>0&&points[i-1]?<line key={i} x1={points[i-1]![0]} y1={points[i-1]![1]} x2={p[0]} y2={p[1]} stroke="#48d7d1" strokeWidth="2"/>:null)}</svg>;
}
function App(){
 const [data,setData]=useState<Snapshot|null>(null),[error,setError]=useState(""),[last,setLast]=useState<string|null>(null);
 useEffect(()=>{let stopped=false,timer:ReturnType<typeof setTimeout>;const controller=new AbortController();
 const poll=async()=>{try{const r=await fetch("/api/observatory",{cache:"no-store",signal:AbortSignal.any([controller.signal,AbortSignal.timeout(10000)])});if(!r.ok)throw new Error("API unavailable");const d=await r.json();if(!stopped){setData(d);setError("");setLast(new Date().toISOString());}}catch(e){if(!stopped)setError("Connection lost. Displayed observations are retained history; derived indices paused.");}finally{if(!stopped)timer=setTimeout(poll,15000);}};
 poll();return()=>{stopped=true;controller.abort();clearTimeout(timer)};},[]);
 return <main className="mx-auto max-w-[1600px] p-5"><header className="mb-6"><h1 className="text-2xl">MoStar Sovereign Signal Observatory</h1><p className="mt-2 text-[#a1b8ac]">Persistent observations · source evidence · independent review</p></header>
 <section className="panel p-5 mb-6"><h2 className="text-xl">Telemetry: {error?"OFFLINE":data?.status.toUpperCase()??"CONNECTING"}</h2><p className="mt-2">{error||"Collector runs independently of this page. Empty channels stay empty."}</p>
 <div className="grid gap-4 md:grid-cols-3 mt-5">{data?.measurements.map(m=>{const a=m.history.at(-1),b=m.history.at(-2);const delta=!error&&m.health==="fresh"&&a?.value!=null&&b?.value!=null?a.value-b.value:null;return <article className="metric-card" key={m.id}><h3>{m.label}</h3><p className="text-3xl mt-3">{m.value??"N/A"} <small className="text-sm">{m.unit}</small></p><p className="mt-2">{error?"Connection lost":m.health} · Δ {delta===null?"paused / unavailable":delta.toFixed(2)}</p><Trace samples={m.history}/><p className="text-sm">Measured: {m.observedAt??"No observation"}</p><p className="text-sm">Age at API check: {m.ageSeconds===null?"N/A":Math.floor(m.ageSeconds/60)+" min"}</p>{m.hash&&<a className="case-link mt-3" href={"/api/evidence/"+m.hash}>Download original evidence</a>}</article>})}</div>
 <p className="mt-5">Speed-energy index: {error?"paused":data?.speedEnergyIndex?.toFixed(3)??"paused"} · Southward coupling index: {error?"paused":data?.couplingIndex?.toFixed(3)??"paused"}</p><p className="text-sm mt-2">Operational proxies, not physical energy measurements. Require fresh, timestamp-aligned wind and Bz.</p></section>
 <p className="mb-5"><a className="case-link" href="/api/observatory" download="observatory-report.json">Download current telemetry and acquisition report (JSON)</a></p>
 <ReviewBoard lastPoll={last}/>
 <section className="panel p-5 mt-6"><h2 className="text-xl">Acquisition audit</h2><p className="mt-2">Refresh does not create new measurements. Same-time conflicts are excluded from derived results.</p><div className="overflow-x-auto"><table className="w-full text-left mt-4"><thead><tr><th>Retrieved UTC</th><th>Source</th><th>Result</th><th>Detail</th></tr></thead><tbody>{data?.attempts.map(a=><tr key={a.id}><td className="p-2">{a.retrieved_at}</td><td className="p-2 break-all">{a.url}</td><td className="p-2">{a.result}</td><td className="p-2">{a.error??"Response retained"}</td></tr>)}</tbody></table></div>{!data?.attempts.length&&<p className="mt-3">No collection attempts stored yet. Configure SOURCE_URLS and start the collector.</p>}</section>
 </main>;
}
createRoot(document.getElementById("root")!).render(<App/>);
