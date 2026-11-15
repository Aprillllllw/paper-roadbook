import {T,box,finish} from './paperkit.js';
import {setTheme,theme} from '../theme.js';
import {makeYurt} from './yurt.js';
import {makeBridge} from './bridge.js';
import {makeFence} from './fence.js';
import {makeSheepFlock} from './sheep-flock.js';
import {makeRadialTown} from './radial-town.js';
import {makeAirport} from './airport.js';
import {makeSwanFlock} from './swan-flock.js';
import {makeServiceStation} from './service-station.js';
import {makeSpruce} from './spruce.js';
import {makeCabin} from './cabin.js';
import {makeHorse} from './horse.js';
import {makeSUV} from './suv.js';
import {makeCamel} from './camel.js';
import {makeOldTown} from './old-town.js';
import {makeSwan} from './swan.js';
import {makeRedBerryBush} from './red-berry-bush.js';
import {makeRider} from './rider.js';
const factories=new Map();
export function register(type,factory){factories.set(type,factory);}
export function types(){return [...factories.keys()];}
export function make(type,opts={},palette=theme){
 setTheme(palette);
 const factory=factories.get(type);
 if(factory)return factory(opts,palette);
 console.warn(`Unknown component: ${type}`);
 const group=new T.Group();box(group,[.8,.6,.05],[0,.5,0],palette.cream);box(group,[.05,.5,.05],[0,.25,0],palette.coffee);return finish(group);
}
register('yurt',makeYurt);register('bridge',makeBridge);
register('fence',(opts)=>makeFence(opts.span??3.2));
register('sheep-flock',(opts)=>makeSheepFlock(opts.n??12));
register('radial-town',(opts)=>makeRadialTown(opts));
register('airport',(opts)=>makeAirport(opts));
register('swan-flock',(opts)=>makeSwanFlock(opts.n??4));
register('service-station',(opts)=>makeServiceStation(opts));
register('spruce',(opts)=>makeSpruce(opts));
register('cabin',(opts)=>makeCabin(opts));
register('horse',(opts)=>makeHorse(opts));
register('suv',(opts)=>makeSUV(opts));
register('camel',(opts)=>makeCamel(opts));
register('old-town',(opts)=>makeOldTown(opts));
register('swan',(opts)=>makeSwan(opts));
register('red-berry-bush',(opts)=>makeRedBerryBush(opts));
register('rider',(opts)=>makeRider(opts));
const custom=(()=>{try{return import.meta.glob('./custom/*.js',{eager:true});}catch{return {};}})();
for(const module of Object.values(custom)){const c=module.default;if(c?.type&&typeof c.make==='function')register(c.type,c.make);}
