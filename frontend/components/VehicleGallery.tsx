"use client";
import Image from "next/image";
import {useState} from "react";
import type {Vehicle} from "@/lib/api";

export default function VehicleGallery({vehicle}:{vehicle:Vehicle}){
  const images=[...(vehicle.images||[])].sort((a,b)=>a.position-b.position);
  const [selected,setSelected]=useState(0);
  const image=images[selected];
  return <div className="gallery"><div className="detailImage">{image?<Image src={image.url} alt={image.alt} fill priority sizes="(max-width: 900px) 100vw, 60vw"/>:<div className="imageFallback"><span>{vehicle.make.slice(0,1)}</span></div>}<span className={`status ${vehicle.availability}`}>{vehicle.availability}</span>{images.length>1&&<div className="galleryCount">{selected+1} / {images.length}</div>}</div>{images.length>1&&<div className="thumbnails" aria-label="Vehicle images">{images.map((item,index)=><button key={`${item.url}-${index}`} aria-label={`Show image ${index+1}: ${item.alt}`} aria-pressed={selected===index} onClick={()=>setSelected(index)}><Image src={item.url} alt="" fill sizes="90px"/></button>)}</div>}</div>
}
