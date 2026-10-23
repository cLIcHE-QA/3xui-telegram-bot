import type { ReactNode } from "react";

type Option={value:string;label:string};
type Props={label:string;value:string;options:Option[];onChange:(value:string)=>void;testId:string;children?:ReactNode};

/** Keyboard-operable group; plain buttons preserve readable 44px targets on narrow viewports. */
export function PreviewModePicker({label,value,options,onChange,testId}:Props){
 return <div className="preview-mode-picker" role="group" aria-label={label} data-testid={testId}>
   {options.map(option=><button key={option.value} type="button"
     className="preview-mode-button" aria-pressed={value===option.value}
     onClick={()=>onChange(option.value)}>{option.label}</button>)}
 </div>;
}
