import "@fontsource-variable/manrope";
import "@fontsource-variable/newsreader";
import "./globals.css";
import Link from "next/link";
import type {Metadata} from "next";
export const metadata:Metadata={title:{default:"Motori — Cars worth your time",template:"%s · Motori"},description:"Browse dealer and marketplace vehicles across Nigeria with clear seller information."};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><header className="siteHeader"><Link className="brand" href="/"><span className="brandMark">M</span>Motori</Link><nav aria-label="Main navigation"><Link href="/vehicles">Buy a car</Link><Link href="/dealers">Dealers</Link><Link href="/staff">Staff</Link></nav></header>{children}<footer><div><Link className="brand footerBrand" href="/">Motori</Link><p>A marketplace for finding cars from Nigerian dealers. Vehicle details are supplied by sellers unless stated otherwise.</p></div><div><Link href="/vehicles">Browse inventory</Link><Link href="/dealers">Dealer directory</Link></div></footer></body></html>}
