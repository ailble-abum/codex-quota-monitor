const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../quota_monitor/panel_layout_data.js'),'utf8');
let value,denied=false,legacy=null;
const ctx=vm.createContext({POSITION_KEY:'position',localStorage:{getItem:key=>{if(denied)throw Error('denied');return key==='position'?legacy:value;}}});vm.runInContext(source,ctx);
const read=input=>{value=typeof input==='string'?input:JSON.stringify(input);return JSON.parse(JSON.stringify(ctx.readLayout()));};
for(const input of ['broken','null','true','123','"text"','[]'])assert.deepEqual(read(input),{});
assert.deepEqual(read({expanded:{x:-20,y:80,width:350,edge:'right',extra:'drop'},compact:{width:180},extra:{}}),{expanded:{x:-20,y:80,width:350,edge:'right'},compact:{width:180}});
assert.deepEqual(read({expanded:{x:'20',y:1e999,width:'bad',edge:'top'},compact:{width:200,edge:'left'}}),{compact:{width:200,edge:'left'}});
for(const width of [0,-1,159,601,'292'])assert.deepEqual(read({expanded:{width}}),{});
for(const width of [160,600])assert.deepEqual(read({expanded:{width}}),{expanded:{width}});
assert.deepEqual(read({expanded:[],compact:{x:12,y:34}}),{compact:{x:12,y:34}});
assert.deepEqual(read('{"__proto__":{"expanded":{"width":500}},"compact":null}'),{});
denied=true;assert.deepEqual(JSON.parse(JSON.stringify(ctx.readLayout())),{});
console.log('layout data: invalid JSON/root/mode, bounded width, finite coordinates, edges and unknown fields passed');

denied=false;value='{}';
const initial=()=>JSON.parse(JSON.stringify(ctx.initialPanelLayout()));
for(const item of [null,[],true,'text',{left:'10',top:null}]){legacy=JSON.stringify(item);assert.deepEqual(initial(),{});}
legacy=JSON.stringify({left:-20,top:40,extra:'ignored'});assert.deepEqual(initial(),{compact:{x:-20,y:40}});
value=JSON.stringify({compact:{width:200},expanded:{edge:'right'}});assert.deepEqual(initial(),{compact:{width:200},expanded:{edge:'right'}});
value=JSON.stringify({compact:{width:'invalid'},expanded:{y:80}});assert.deepEqual(initial(),{compact:{x:-20,y:40},expanded:{y:80}});
legacy=JSON.stringify({left:12,top:'bad'});value='broken';assert.deepEqual(initial(),{compact:{x:12}});
legacy='broken';assert.deepEqual(initial(),{});
console.log('legacy migration: finite axes, malformed records, compact precedence and independent fallback passed');
