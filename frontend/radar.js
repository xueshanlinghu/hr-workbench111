export function drawRadar(canvas,data,isQualified){
  const dpr=window.devicePixelRatio||1;
  const rect=canvas.getBoundingClientRect();
  canvas.width=rect.width*dpr;
  canvas.height=rect.height*dpr;
  const ctx=canvas.getContext("2d");
  ctx.scale(dpr,dpr);
  const w=rect.width,h=rect.height,cx=w/2,cy=h/2+4;
  // 为左右两侧的中文标签留出宽度，窄窗口中也不裁切。
  const r=Math.min(h * .30, Math.max(30, (w / 2 - 108) / (1.24 * .866)));
  const labels=["业务理解","方案判断","编程与集成","评估与排错","沟通与协作","交付与复用"];
  const values=[data.business_understanding||0,data.solution_judgment||0,data.engineering_integration||0,data.evaluation_troubleshooting||0,data.communication_collaboration||0,data.delivery_reuse||0];
  const sides=labels.length;
  const angleFor=i=>-Math.PI/2+i*Math.PI*2/sides;
  const point=(i,scale)=>{const a=angleFor(i);return[cx+Math.cos(a)*r*scale,cy+Math.sin(a)*r*scale]};
  ctx.font='17.1px "Microsoft YaHei","PingFang SC",sans-serif';
  ctx.textBaseline="middle";
  for(let level=1;level<=4;level++){
    ctx.beginPath();
    for(let i=0;i<sides;i++){const p=point(i,level/4);i?ctx.lineTo(...p):ctx.moveTo(...p)}
    ctx.closePath();
    ctx.strokeStyle="#dbe4e0";
    ctx.stroke();
  }
  for(let i=0;i<sides;i++){
    const a=angleFor(i);
    const p=point(i,1);
    ctx.beginPath();
    ctx.moveTo(cx,cy);
    ctx.lineTo(...p);
    ctx.strokeStyle="#e3e9e6";
    ctx.stroke();
    const lp=point(i,1.24);
    ctx.textAlign=Math.cos(a)>0.35?"left":Math.cos(a)<-0.35?"right":"center";
    ctx.textBaseline=Math.sin(a)>0.35?"top":Math.sin(a)<-0.35?"bottom":"middle";
    ctx.fillStyle="#5e6b65";
    ctx.fillText(labels[i],...lp);
  }
  const radarColor=isQualified===false?"#da1e28":"#0f62fe";
  const radarFill=isQualified===false?"rgba(218,30,40,.18)":"rgba(15,98,254,.18)";
  ctx.beginPath();
  values.forEach((v,i)=>{const p=point(i,v/100);i?ctx.lineTo(...p):ctx.moveTo(...p)});
  ctx.closePath();
  ctx.fillStyle=radarFill;
  ctx.fill();
  ctx.strokeStyle=radarColor;
  ctx.lineWidth=2;
  ctx.stroke();
  values.forEach((v,i)=>{const p=point(i,v/100);ctx.beginPath();ctx.arc(...p,3,0,Math.PI*2);ctx.fillStyle=radarColor;ctx.fill();});
}
