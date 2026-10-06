export const API=process.env.API_INTERNAL_URL||process.env.NEXT_PUBLIC_API_URL||"http://localhost:8002";
export type Seller={id?:string;slug?:string;name:string;location?:string;logo_url?:string;website_url?:string};
export type Vehicle={id:string;slug:string;title:string;make:string;model:string;year:number;price:string;currency:string;mileage_km:number;transmission:string;fuel_type:string;condition:string;location:string;description:string;features:string[];known_issues:string;seller_history:string;video_url:string;images:{url:string;alt:string;position:number}[];availability:"available"|"reserved"|"sold";is_featured:boolean;ownership:"dealer"|"marketplace";seller:Seller;updated_at:string;decision?:string;source_version?:number};
export type Page<T>={count:number;page:number;pages:number;results:T[]};
export async function getJson<T>(path:string):Promise<T>{const r=await fetch(`${API}${path}`,{cache:"no-store"});if(!r.ok)throw new Error(`API returned ${r.status}`);return r.json() as Promise<T>}
export const money=(value:string,currency="NGN")=>new Intl.NumberFormat("en-NG",{style:"currency",currency,maximumFractionDigits:0}).format(Number(value));
