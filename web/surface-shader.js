// Display-only smoothing. Native vertex positions are never moved or subdivided.
export function smoothSurfaceVertices(faces,selected){
 const triangles=[],normals=new Map(),low=[Infinity,Infinity,Infinity],high=[-Infinity,-Infinity,-Infinity];
 for(const f of faces)for(const p of f.points)for(let k=0;k<3;k++){low[k]=Math.min(low[k],p[k]);high[k]=Math.max(high[k],p[k]);}
 const quantum=Math.max(1e-20,...high.map((v,k)=>(v-low[k])*1e-10));
 const key=(f,p)=>(f.surfaceKey||f.id)+':'+p.map(x=>Math.round(x/quantum)).join(',');
 for(const f of faces){if(f.kind||f.selectionOnly&&f.id!==selected)continue;
  for(let i=1;i<f.points.length-1;i++){
   const p=[f.points[0],f.points[i],f.points[i+1]],a=p[1].map((v,k)=>v-p[0][k]),b=p[2].map((v,k)=>v-p[0][k]);
   const n=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
   if(!n.every(Number.isFinite)||Math.hypot(...n)<1e-20)continue;
   const keys=p.map(q=>key(f,q));keys.forEach(k=>{const adjacent=normals.get(k)||[];adjacent.push(n);normals.set(k,adjacent);});triangles.push({f,p,keys,n});
  }
 }
 const data=[];
 for(const t of triangles)for(let i=0;i<3;i++){
  const n=[0,0,0],faceLength=Math.hypot(...t.n);for(const a of normals.get(t.keys[i])){if(a.reduce((sum,v,k)=>sum+v*t.n[k],0)/(Math.hypot(...a)*faceLength)<.6)continue;for(let k=0;k<3;k++)n[k]+=a[k];}const length=Math.hypot(...n)||1,color=t.f.id===selected?[.43,.64,.52]:[.69,.74,.7];
  data.push(...t.p[i],...n.map(x=>x/length),...color);
 }
 return new Float32Array(data);
}
export function createSurfaceShader(){
 const canvas=document.createElement('canvas'),gl=canvas.getContext('webgl',{alpha:true,antialias:true,premultipliedAlpha:false});
 if(!gl)return null;
 let lost=false;canvas.addEventListener('webglcontextlost',()=>{lost=true;});
 const vertex=`attribute vec3 position;attribute vec3 normal;attribute vec3 color;uniform vec3 center;uniform vec4 camera;uniform vec2 factor;uniform vec2 offset;uniform float extent;varying vec3 N;varying vec3 C;
 void main(){vec3 p=position-center;float u=p.x*camera.x-p.y*camera.y;float d=p.x*camera.y+p.y*camera.x;float depth=d*camera.w+p.z*camera.z;gl_Position=vec4(u*factor.x+offset.x,-(d*camera.z-p.z*camera.w)*factor.y+offset.y,-depth/(extent*4.0),1.0);float nd=normal.x*camera.y+normal.y*camera.x;N=vec3(normal.x*camera.x-normal.y*camera.y,-nd*camera.z+normal.z*camera.w,nd*camera.w+normal.z*camera.z);C=color;}`;
 const fragment=`precision mediump float;varying vec3 N;varying vec3 C;void main(){vec3 n=normalize(N);if(n.z<0.0)n=-n;vec3 light=normalize(vec3(-0.4,0.7,1.0));float diffuse=max(dot(n,light),0.0);float shine=pow(max(dot(n,normalize(light+vec3(0.0,0.0,1.0))),0.0),40.0);gl_FragColor=vec4(C*(0.42+0.65*diffuse)+vec3(0.16*shine),1.0);}`;
 function compile(type,source){const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(shader));return shader;}
 let program;
 try{program=gl.createProgram();gl.attachShader(program,compile(gl.VERTEX_SHADER,vertex));gl.attachShader(program,compile(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))return null;}catch{return null;}
 const buffer=gl.createBuffer(),uniform=name=>gl.getUniformLocation(program,name);let previous=null,previousSelected=null,count=0;
 return {draw(faces,view){
  if(lost||gl.isContextLost())return null;
  canvas.width=Math.round(view.width*view.dpr);canvas.height=Math.round(view.height*view.dpr);gl.viewport(0,0,canvas.width,canvas.height);gl.useProgram(program);gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  if(faces!==previous||view.selected!==previousSelected){const data=smoothSurfaceVertices(faces,view.selected);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);count=data.length/9;previous=faces;previousSelected=view.selected;}
  ['position','normal','color'].forEach((name,i)=>{const at=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(at);gl.vertexAttribPointer(at,3,gl.FLOAT,false,36,i*12);});
  gl.uniform3fv(uniform('center'),view.center);gl.uniform4fv(uniform('camera'),[Math.cos(view.yaw),Math.sin(view.yaw),Math.sin(view.pitch),Math.cos(view.pitch)]);gl.uniform2fv(uniform('factor'),[2*view.scale/view.width,2*view.scale/view.height]);gl.uniform2fv(uniform('offset'),[2*view.panX/view.width,-.12-2*view.panY/view.height]);gl.uniform1f(uniform('extent'),view.extent);
  gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.drawArrays(gl.TRIANGLES,0,count);return canvas;
 }};
}
