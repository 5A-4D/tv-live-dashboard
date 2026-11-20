/* Snowfall motion adapted from JavaScript Snow, Copyright (c) 2023 Peter Wetherall.
 * MIT license and pinned source attribution: vendor/javascript-snow.LICENSE.txt / .NOTICE.txt.
 * TV integration, frame limits, lifecycle and preference controls are local adaptations.
 */
(function () {
  'use strict';
  var canvas=document.getElementById('snowfall-layer');
  if(!canvas)return;
  var context=canvas.getContext('2d',{alpha:true});
  if(!context)return;
  var options=window.JARVIS_CONFIG.snowfall||{};
  var fps=Math.min(30,Math.max(12,options.maxFps||24)),interval=1000/fps;
  var maxFlakes=Math.min(80,Math.max(16,options.maxFlakes||70));
  var flakes=[],frameId=null,lastPaint=0,lastStep=0,painted=0;
  var foreground=true;
  var reduced=window.matchMedia('(prefers-reduced-motion: reduce)');

  function enabled(){
    var saved=localStorage.getItem('jarvis-snowfall');
    return saved===null?options.enabled!==false&&!reduced.matches:saved==='on';
  }
  function shouldRun(){
    return enabled()&&foreground&&!document.hidden&&document.body.classList.contains('winter');
  }
  function resize(){
    var scale=Math.min(1,1280/window.innerWidth);
    canvas.width=Math.round(window.innerWidth*scale);
    canvas.height=Math.round(window.innerHeight*scale);
    flakes=[];
    var count=Math.min(maxFlakes,Math.max(24,Math.ceil(canvas.width*canvas.height/8500)));
    for(var i=0;i<count;i++){
      var depth=.35+Math.random()*.65;
      flakes.push({baseX:Math.random()*canvas.width,y:Math.random()*canvas.height,
        radius:.45+depth*1.55,opacity:.2+depth*.45,phase:Math.random()*Math.PI*2,
        distance:6+Math.random()*20,speed:12+depth*30});
    }
  }
  function stop(){
    if(frameId!==null)cancelAnimationFrame(frameId);
    frameId=null;lastPaint=0;lastStep=0;
    context.clearRect(0,0,canvas.width,canvas.height);
  }
  function draw(now){
    frameId=null;
    if(!shouldRun()){stop();return;}
    frameId=requestAnimationFrame(draw);
    if(lastPaint&&now-lastPaint<interval)return;
    var elapsed=lastStep?Math.min((now-lastStep)/1000,.12):1/fps;
    lastPaint=lastPaint?now-((now-lastPaint)%interval):now;
    lastStep=now;
    context.clearRect(0,0,canvas.width,canvas.height);
    context.fillStyle='#eef7ff';
    for(var i=0;i<flakes.length;i++){
      var flake=flakes[i];
      flake.y+=flake.speed*elapsed;
      flake.phase+=.25*elapsed;
      if(flake.y>canvas.height+flake.radius){flake.y=-flake.radius;flake.baseX=Math.random()*canvas.width;}
      var x=flake.baseX+flake.distance*Math.sin(flake.phase);
      context.globalAlpha=flake.opacity;
      context.beginPath();context.arc(x,flake.y,flake.radius,0,Math.PI*2);context.fill();
    }
    context.globalAlpha=1;painted++;
  }
  function refresh(){
    if(shouldRun()){
      if(frameId===null){lastPaint=0;lastStep=0;frameId=requestAnimationFrame(draw);}
    }else stop();
  }
  window.JarvisSnow={
    refresh:refresh,
    isEnabled:enabled,
    toggle:function(){var next=!enabled();localStorage.setItem('jarvis-snowfall',next?'on':'off');refresh();return next;},
    stats:function(){return {running:frameId!==null,particles:flakes.length,frames:painted,fpsCap:fps,width:canvas.width,height:canvas.height};}
  };
  window.jarvisVisibility=function(visible){foreground=visible!==false;refresh();};
  window.addEventListener('resize',function(){resize();refresh();});
  document.addEventListener('visibilitychange',refresh);
  if(reduced.addEventListener)reduced.addEventListener('change',refresh);
  resize();refresh();
}());
