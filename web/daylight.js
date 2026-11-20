/* Local solar schedule; SunCalc attribution and BSD license are in vendor/. */
(function () {
  'use strict';
  var config=window.JARVIS_CONFIG,options=config.daylight||{},layer=document.getElementById('wallpaper-layer');
  if(!layer||!window.SunCalc)return;
  var latitude=typeof options.latitude==='number'?options.latitude:51.4769;
  var longitude=typeof options.longitude==='number'?options.longitude:0.0;
  var calendar=new Intl.DateTimeFormat('en-US',{timeZone:config.timezone,year:'numeric',month:'2-digit',day:'2-digit'});
  var cacheKey='',times=null,lastMinute=null,lastState=null,instantGeneration=0;

  function smooth(start,end,value){
    var fraction=Math.max(0,Math.min(1,(value-start)/(end-start)));
    return fraction*fraction*(3-2*fraction);
  }
  function solarTimes(date){
    var parts={};calendar.formatToParts(date).forEach(function(part){parts[part.type]=part.value;});
    var key=parts.year+'-'+parts.month+'-'+parts.day;
    if(key!==cacheKey){
      // Anchor near local solar noon so pre-dawn, UTC rollover and DST select the right local day.
      var noon=Date.UTC(Number(parts.year),Number(parts.month)-1,Number(parts.day))+(12-longitude/15)*3600000;
      times=window.SunCalc.getTimes(new Date(noon),latitude,longitude);cacheKey=key;
    }
    return times;
  }
  function calculate(value){
    var date=new Date(value===undefined?Date.now():value),now=date.getTime();
    if(!isFinite(now))return null;
    var sun=solarTimes(date),dawn=sun.dawn.getTime(),morning=sun.goldenHourEnd.getTime();
    var evening=sun.goldenHour.getTime(),dusk=sun.dusk.getTime(),phase='day',night=0,twilight=0;
    if([dawn,morning,evening,dusk].every(isFinite)){
      if(now<dawn||now>=dusk){phase='night';night=1;}
      else if(now<morning){phase='dawn';night=1-smooth(dawn,morning,now);twilight=Math.sin(Math.PI*(1-night));}
      else if(now>=evening){phase='dusk';night=smooth(evening,dusk,now);twilight=Math.sin(Math.PI*night);}
    }else{
      // Polar-day/night safety if the configured location is changed in future.
      var position=window.SunCalc.getPosition(date,latitude,longitude);
      night=1-smooth(-6,6,position.altitude*180/Math.PI);
      phase=night===1?'night':night===0?'day':position.azimuth>0?'dusk':'dawn';
      twilight=Math.sin(Math.PI*night);
    }
    if(options.enabled===false){phase='day';night=0;twilight=0;}
    return {phase:phase,night:night,twilight:twilight,
      sunrise:isFinite(sun.sunrise.getTime())?sun.sunrise.getTime():null,
      sunset:isFinite(sun.sunset.getTime())?sun.sunset.getTime():null};
  }
  function refresh(force,value){
    var now=value===undefined?Date.now():new Date(value).getTime(),minute=Math.floor(now/60000);
    if(!force&&lastMinute===minute)return lastState;
    var state=calculate(now);if(!state)return lastState;
    lastMinute=minute;lastState=state;
    if(force){
      layer.classList.add('scene-instant');var generation=++instantGeneration;
      requestAnimationFrame(function(){requestAnimationFrame(function(){
        if(generation===instantGeneration)layer.classList.remove('scene-instant');
      });});
    }
    layer.style.setProperty('--winter-night',state.night.toFixed(4));
    layer.style.setProperty('--winter-twilight',state.twilight.toFixed(4));
    document.body.setAttribute('data-light-phase',state.phase);
    return state;
  }
  window.JarvisDaylight={calculate:calculate,refresh:refresh,state:function(){return lastState;}};
  var snowVisibility=window.jarvisVisibility;
  window.jarvisVisibility=function(visible){
    if(visible!==false)refresh(true);
    if(snowVisibility)snowVisibility(visible);
  };
  document.addEventListener('visibilitychange',function(){if(!document.hidden)refresh(true);});
  refresh(true);
}());
