import { IconAppWindow, IconCheck, IconChevronRight, IconDeviceMobile, IconInfoCircle, IconLock, IconShieldCheck, IconStar } from "@tabler/icons-react";
import type { ReactNode } from "react";
import { SafeSvgIcon } from "./SafeSvgIcon";
type App={name:string;featured?:boolean;svgIconKey?:string;blocks:{title:Record<string,string>;description:Record<string,string>;buttons:{text:Record<string,string>;type:string;link:string}[]}[]};
type Props={apps:App[];selectedIndex:number;onSelect:(index:number)=>void;t:(key:string)=>string;svgLibrary?:Record<string,string>};
const glyph=(name:string):ReactNode=>{
 const n=name.toLowerCase();
 if(n.includes("happ")||n.includes("incy"))return <IconShieldCheck size={25} stroke={1.8}/>;
 if(n.includes("shadow")||n.includes("v2ray")||n.includes("v2box"))return <IconDeviceMobile size={25} stroke={1.8}/>;
 if(n.includes("karing")||n.includes("throne")||n.includes("rabbithole"))return <IconAppWindow size={25} stroke={1.8}/>;
 return <IconShieldCheck size={25} stroke={1.8}/>;
};
/** Neutral icons are not third-party trademarks and do not assert client compatibility. */
export function ClientChooser({apps,selectedIndex,onSelect,t,svgLibrary}:Props){
 if(!apps.length)return <div className="empty-clients" role="status"><span className="empty-clients-icon"><IconInfoCircle size={28}/></span><div><strong>{t("noClients")}</strong><p>{t("noClientsHint")}</p></div></div>;
 return <div className="client-list" role="group" aria-label={t("application")}>
 {apps.map((app,i)=><button type="button" key={i} aria-pressed={i===selectedIndex} data-testid="client-choice" className={"client-choice "+(i===selectedIndex?"active":"")} onClick={()=>onSelect(i)}>
   <span className="client-icon" aria-hidden="true"><SafeSvgIcon iconKey={app.svgIconKey} library={svgLibrary} fallback={glyph(app.name)}/></span>
   <span className="client-copy"><strong>{app.name}</strong><small>{app.featured?<><IconStar size={13}/>{t("recommendedDemo")}</>:<><IconLock size={13}/>{t("safeDemoApp")}</>}</small></span>
   <span className="client-end">{i===selectedIndex?<IconCheck size={20}/>:<IconChevronRight size={20}/>}</span>
 </button>)}
 </div>;
}
