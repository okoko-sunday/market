"use client";
import {useEffect,useState} from "react";
import {staffFetch} from "@/lib/staff-api";
type Dealer={id:string;name:string;slug:string;source_active:boolean;marketplace_suspended:boolean;last_source_update:string;public_inventory:number};
export default function Dealers(){
  const [items,setItems]=useState<Dealer[]>([]),[notice,setNotice]=useState("");
  const load=()=>staffFetch("/api/v1/staff/dealers/?page_size=48").then(x=>setItems(x.results)).catch(()=>setNotice("Could not load dealers."));
  useEffect(()=>{void load()},[]);
  async function toggle(dealer:Dealer){if(!window.confirm(`${dealer.marketplace_suspended?"Restore":"Suspend"} ${dealer.name} on the public marketplace?`))return;try{await staffFetch(`/api/v1/staff/dealers/${dealer.id}/`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({marketplace_suspended:!dealer.marketplace_suspended})});setNotice("Dealer visibility updated.");void load()}catch{setNotice("Dealer update failed.")}}
  return <main className="reviewPage"><div className="staffTop"><div><span className="eyebrow">Dealer operations</span><h1>Dealer directory</h1></div><a href="/staff">Back to overview</a></div>{notice&&<p role="status">{notice}</p>}<table className="dataTable"><thead><tr><th>Dealer</th><th>Source</th><th>Public inventory</th><th>Last update</th><th></th></tr></thead><tbody>{items.map(x=><tr key={x.id}><td><strong>{x.name}</strong><br/><small>{x.slug}</small></td><td><span className={`statusChip ${x.source_active?"processed":"failed"}`}>{x.source_active?"Active":"Inactive"}</span></td><td>{x.public_inventory}</td><td>{new Date(x.last_source_update).toLocaleString("en-NG")}</td><td><button className={x.marketplace_suspended?"secondary":""} onClick={()=>toggle(x)}>{x.marketplace_suspended?"Restore":"Suspend"}</button></td></tr>)}</tbody></table></main>
}
