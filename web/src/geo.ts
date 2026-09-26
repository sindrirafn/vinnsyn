import outline from './iceland-outline.json';
import type { Point } from './data';

// Natural Earth 1:50m Iceland coastline. Projection is local equirectangular
// with longitude compressed at 65°N; all place clouds use the same projection.
const WEST=-24.475684,EAST=-13.556104,SOUTH=63.406689,NORTH=66.526074;
const COS65=Math.cos(65*Math.PI/180);
export const ICELAND_OUTLINE=outline as Point[];
const NONSPATIAL_KEYS=['remote','nationwide','multiple','outside','unknown'];
const NONSPATIAL_DESKTOP:Point[]=[[.35,.68],[.39,.74],[.35,.80],[.40,.86],[.35,.91]];
const NONSPATIAL_MOBILE:Point[]=[[.13,.84],[.31,.84],[.51,.84],[.71,.84],[.87,.84]];
export function nonspatialPoint(key:string,width:number):Point{
  const index=Math.max(0,NONSPATIAL_KEYS.indexOf(key));
  return (width<690?NONSPATIAL_MOBILE:NONSPATIAL_DESKTOP)[index];
}

export function projectGeo(lon:number,lat:number,width:number,height:number,selected=false):Point{
  const mobile=width<690;
  const left=mobile?22:width*.39,right=mobile?width-22:width*.94;
  const top=mobile?height*(selected ? .63 : .49):height*.18,bottom=mobile?height*(selected ? .94 : .79):height*.82;
  const projectedWidth=(EAST-WEST)*COS65,projectedHeight=NORTH-SOUTH;
  const scale=Math.min((right-left)/projectedWidth,(bottom-top)/projectedHeight);
  const actualWidth=projectedWidth*scale,actualHeight=projectedHeight*scale;
  const x0=left+(right-left-actualWidth)/2,y0=top+(bottom-top-actualHeight)/2;
  return [(x0+(lon-WEST)*COS65*scale)/width,(y0+(NORTH-lat)*scale)/height];
}
export function geographicRadius(count:number,width:number,height:number,kind:string):Point{
  // An intentionally visual density footprint, not source coordinate accuracy.
  const max=width<690?22:58;
  const base=Math.min(max,3+Math.sqrt(count)*.42);
  const multiplier=kind==='municipality'||kind==='area'?1.3:1;
  return [base*multiplier/width,base*multiplier/height];
}
