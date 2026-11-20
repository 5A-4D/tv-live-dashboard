(function () {
  'use strict';
  var config = window.JARVIS_CONFIG;
  var native = window.JarvisNative;
  var apps = [], snapshot = null, live = false, focusBeforeModal = null, newsIndex = 0;
  var lastInput = Date.now(), receivedAt = 0;
  var $ = function (id) { return document.getElementById(id); };
  var overlay = $('overlay');
  var clockFormat = new Intl.DateTimeFormat('en-US', {timeZone:config.timezone,hour:'numeric',minute:'2-digit',hour12:true});
  var dateFormat = new Intl.DateTimeFormat('en-US', {timeZone:config.timezone,weekday:'long',month:'long',day:'numeric'});

  function text(tag, value, className) {
    var node = document.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  }
  function button(label, className, action) {
    var node = text('button', label, className);
    node.setAttribute('data-nav', '');
    node.onclick = action;
    return node;
  }
  function toast(message) {
    $('toast').textContent = message;
    $('toast').hidden = false;
    setTimeout(function () { $('toast').hidden = true; }, 3500);
  }
  function duration(seconds) {
    if (typeof seconds !== 'number') return 'Unavailable';
    var days = Math.floor(seconds / 86400), hours = Math.floor(seconds / 3600) % 24, minutes = Math.floor(seconds / 60) % 60;
    return days ? days + 'd ' + hours + 'h' : hours ? hours + 'h ' + minutes + 'm' : minutes + 'm';
  }
  function setFocus(node) { if (node) { node.focus({preventScroll:true}); if (!overlay.hidden) node.scrollIntoView({block:'nearest',inline:'nearest'}); } }
  function interaction() { lastInput = Date.now(); document.body.classList.remove('ambient'); }
  function modal(title, eyebrow) {
    focusBeforeModal = document.activeElement;
    $('overlayTitle').textContent = title;
    $('overlayEyebrow').textContent = eyebrow || 'TV LIVE DASHBOARD';
    $('overlayContent').replaceChildren();
    overlay.hidden = false;
    setFocus($('closeOverlay'));
    return $('overlayContent');
  }
  function closeModal() { overlay.hidden = true; setFocus(focusBeforeModal || $('firstApp')); }
  function launch(pkg) {
    if (!native) { toast('App shortcuts work on the TV.'); return; }
    if (!apps.some(function (app) { return app.package === pkg; })) { toast('This app is not available on this TV.'); return; }
    native.launch(pkg);
  }
  function allApps() {
    var content = modal('Your apps', 'MAKE YOURSELF AT HOME');
    if (!apps.length) { content.appendChild(text('p','Loading the TV app list…','empty-state')); return; }
    var grid = text('div','', 'app-grid');
    apps.forEach(function (app) {
      var node = button('', 'installed-app', function () { launch(app.package); });
      if (app.icon && app.icon.indexOf('data:image/png;base64,') === 0) {
        var icon = document.createElement('img'); icon.src = app.icon; icon.alt = ''; node.appendChild(icon);
      }
      node.appendChild(text('span',app.label)); grid.appendChild(node);
    });
    content.appendChild(grid);
    setFocus(grid.querySelector('button'));
  }
  function reminders() {
    var content = modal('All reminders', 'YOUR CURRENT LIST');
    var data = snapshot && snapshot.reminders;
    if (!data || !data.available) { content.appendChild(text('p','Your reminder file is unavailable.','empty-state')); return; }
    if (!isFresh()) content.appendChild(text('p','Showing the last received list. Reconnect to Home server for updates.','offline-note'));
    var pre = text('pre',data.raw || '(Your reminder file is empty.)','reminder-file');
    pre.setAttribute('data-nav',''); pre.tabIndex = 0; content.appendChild(pre); setFocus(pre);
  }
  function systems() {
    var content = modal('Systems', 'A LOOK BEHIND THE SCENES');
    if (!snapshot) { content.appendChild(text('p','Connect to Home server to see service status.','empty-state')); return; }
    (snapshot.services || []).forEach(function (service) {
      var row = text('div','', 'detail-row');
      row.appendChild(text('strong',service.label));
      row.appendChild(text('span',!isFresh() || service.stale ? 'Status stale' : service.online ? 'Running' : service.state));
      row.appendChild(text('span','Uptime: ' + (isFresh() ? duration(service.uptime_seconds) : 'Unavailable')));
      content.appendChild(row);
    });
    content.appendChild(text('p','Home server uptime: ' + (snapshot.host ? duration(snapshot.host.uptime_seconds) : 'Unavailable') + '. Status refreshes while Home is open.','detail-note'));
  }
  function setTheme(name,persist){
    name=name==='winter'?'winter':'midnight';
    document.body.classList.toggle('winter',name==='winter');
    if(window.JarvisDaylight)window.JarvisDaylight.refresh(true);
    if(window.JarvisSnow)window.JarvisSnow.refresh();
    if(persist!==false)localStorage.setItem('jarvis-theme',name);
  }
  function themes(){
    var homeFocus=focusBeforeModal;
    var content=modal('Choose your view','THEMES');
    focusBeforeModal=homeFocus&&homeFocus.isConnected?homeFocus:$('settingsButton');
    var grid=text('div','','theme-grid');
    var choices=[['winter','Snowfall','Falling snow with local dawn, daylight, dusk and night scenery.'],['midnight','Midnight','The original dark background and solid panels.']];
    choices.forEach(function(choice){
      var current=document.body.classList.contains('winter')?choice[0]==='winter':choice[0]==='midnight';
      var option=button('','theme-option',function(){setTheme(choice[0]);closeModal();});
      option.setAttribute('aria-pressed',String(current));
      option.appendChild(text('span','','theme-preview '+choice[0]+'-preview'));
      option.appendChild(text('strong',choice[1]+(current?' · Selected':'')));
      option.appendChild(text('small',choice[2]));
      grid.appendChild(option);
    });
    content.appendChild(grid);setFocus(grid.querySelector('button'));
  }
  function settings() {
    var content = modal('Make it yours', 'HOME SETTINGS');
    var grid = text('div','', 'settings-grid');
    var choices = [
      ['TV settings','Picture, sound, inputs and network',function () { if (native) native.settings(); }],
      ['Home screen setup','Manage the launcher accessibility service',function () { if (native) native.accessibility(); }],
      ['Projectivy','Open your alternative home screen',function () { launch('com.spocky.projengmenu'); }],
      ['Refresh dashboard','Ask Home server for the latest information',function () { if (native) native.refresh(); closeModal(); }],
      ['Theme','Choose Snowfall or Midnight',themes],
      ['Accent color','Switch between warm gold and muted rose',function () { document.body.classList.toggle('warm'); localStorage.setItem('jarvis-accent',document.body.classList.contains('warm')?'rose':'gold'); }],
      ['Ambient dimming','Dim Home after five minutes without input',function () { var enabled=localStorage.getItem('jarvis-dim')!=='off'; localStorage.setItem('jarvis-dim',enabled?'off':'on'); toast(enabled?'Ambient dimming off':'Ambient dimming on'); }],
      ['Falling snow','Turn the Snowfall theme animation on or off',function () {if(window.JarvisSnow)toast(window.JarvisSnow.toggle()?'Falling snow on':'Falling snow off');}]
    ];
    choices.forEach(function (choice) { var node=button('', 'setting-option',choice[2]); node.appendChild(text('strong',choice[0])); node.appendChild(text('small',choice[1])); grid.appendChild(node); });
    content.appendChild(grid); setFocus(grid.querySelector('button'));
  }
  function isFresh() { return Boolean(snapshot && live && !snapshot.feed_stale && typeof snapshot.collected_at === 'number' && Date.now()/1000 - snapshot.collected_at < 60 && Date.now()/1000 - snapshot.collected_at >= -5); }
  function renderReminders() {
    var target = $('reminderPreview'); target.replaceChildren();
    var data = snapshot && snapshot.reminders;
    if (!data || !data.available) { target.appendChild(text('p','Your reminders are unavailable.','empty-state')); $('reminderCount').textContent='—'; return; }
    $('reminderCount').textContent=data.unfinished;
    var unfinished=(data.items || []).filter(function (item) {return !item.done;});
    unfinished.slice(0,config.maxReminderPreview).forEach(function (item) {
      var label=item.priority===null?item.text:item.text.replace(/^(?:\*\*)?(?:(?:priority|p)\s*)?\d+[.):\s-]+\s*/i,'');
      var row=text('div','', 'reminder-row'); row.appendChild(text('span',item.priority===null?'·':String(item.priority),'priority')); row.appendChild(text('span',label)); target.appendChild(row);
    });
    if (!unfinished.length) target.appendChild(text('p',data.raw.trim() && !(data.items || []).length ? 'Open your full list to see your reminders.' : 'All caught up. Your full list is one click away.','empty-state'));
  }
  function renderServices() {
    var target=$('servicePreview'); target.replaceChildren();
    var services=snapshot && snapshot.services || [];
    ['jarvis-discord','jellyfin'].forEach(function (id) {
      var service=services.find(function (item) {return item.id===id;});
      var healthy=service && isFresh() && !service.stale && service.online;
      if (id==='jarvis-discord') healthy=healthy && snapshot.jarvis && snapshot.jarvis.ready;
      var stale=!isFresh() || !service || service.stale;
      var state=stale?'stale':healthy?'online':'offline';
      var activity=snapshot&&snapshot.jarvis&&snapshot.jarvis.activity;
      var activityLabel=activity&&activity.state==='working'?'Working · '+activity.active_count:activity&&activity.state==='idle'?'Idle · ready':'Ready';
      var row=text('div','', 'service '+state); row.appendChild(text('span','', 'service-dot '+state)); row.appendChild(text('span',id==='jarvis-discord'?'Jarvis':'Jellyfin')); row.appendChild(text('strong',stale?'Status stale':healthy?(id==='jarvis-discord'?activityLabel:'Healthy'):'Unavailable')); target.appendChild(row);
    });
    var activity=snapshot&&snapshot.jarvis&&snapshot.jarvis.activity;
    var success=activity&&activity.last_success_at;
    var note=activity&&activity.state==='working'&&isFresh()?'Working for '+duration(Math.max(0,Date.now()/1000-activity.started_at)):
      success?'Last success '+ago(success)+(isFresh()?'':' · saved'):'No recent activity recorded';
    target.appendChild(text('div',note,'activity-note'));
    var uptime=text('div','', 'host-uptime'); uptime.appendChild(text('span','Home server uptime')); uptime.appendChild(text('strong',isFresh() && snapshot.host?duration(snapshot.host.uptime_seconds):'Unavailable')); target.appendChild(uptime);
  }
  function renderNews() {
    var target=$('newsPreview');target.replaceChildren();
    var news=snapshot && snapshot.news;
    if (!news || !news.items || !news.items.length) {target.appendChild(text('p',snapshot?'Headlines are temporarily unavailable.':'Fetching your headlines…','empty-state'));return;}
    var stale=!news.checked_at || Date.now()/1000-news.checked_at>3600 || !live;
    var count=Math.min(config.maxNewsPreview,news.items.length);
    target.style.setProperty('--headline-count',count);
    for(var index=0;index<count;index++){
      var item=news.items[(newsIndex+index)%news.items.length],row=text('div','','headline');
      row.appendChild(text('span',item.source+(stale?' · cached':''),'headline-source'));
      row.appendChild(text('h3',item.title));target.appendChild(row);
    }
  }
  function moreNews(){
    var content=modal('Headlines','WORLD & TECHNOLOGY'),items=snapshot&&snapshot.news&&snapshot.news.items||[];
    if(!items.length){content.appendChild(text('p','Headlines are temporarily unavailable.','empty-state'));return;}
    var list=text('div','','reminder-file');list.setAttribute('data-nav','');list.tabIndex=0;
    items.forEach(function(item){var row=text('div','','news-list-item');row.appendChild(text('small',item.source));row.appendChild(text('div',item.title));list.appendChild(row);});
    content.appendChild(list);setFocus(list);
  }
  function clockAt(seconds){return clockFormat.format(new Date(seconds*1000));}
  function ago(seconds){var elapsed=Math.max(0,Date.now()/1000-seconds);return elapsed<60?'just now':duration(elapsed)+' ago';}
  function countdown(seconds){seconds=Math.max(0,Math.ceil(seconds));return seconds<60?seconds+'s':duration(Math.ceil(seconds/60)*60);}
  function todayKey(){var p=new Intl.DateTimeFormat('en-US',{timeZone:config.timezone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()),values={};p.forEach(function(x){values[x.type]=x.value;});return values.year+'-'+values.month+'-'+values.day;}
  function workAge(){var work=snapshot&&snapshot.work;return work&&typeof work.checked_at==='number'?Date.now()/1000-work.checked_at:Infinity;}
  function workSaved(){var work=snapshot&&snapshot.work;return Boolean(work&&work.available&&Array.isArray(work.days)&&workAge()>=-5&&workAge()<86400);}
  function workFresh(){return Boolean(workSaved()&&isFresh()&&!snapshot.work.refresh_failed&&workAge()<600);}
  function workSavedNote(){return (live?'Calendar update delayed':'Offline')+' · saved '+ago(snapshot.work.checked_at);}
  function timeline(day){
    var wrapper=text('div','','work-timeline'),result=text('div','','timeline'),hours=text('div','','timeline-hours'),span=day.end-day.start;
    wrapper.appendChild(result);
    if(!(span>0))return wrapper;
    (day.busy||[]).forEach(function(interval){var block=text('span','','busy-block');block.style.left=(interval.start-day.start)/span*100+'%';block.style.width=(interval.end-interval.start)/span*100+'%';result.appendChild(block);});
    var first=Math.ceil(day.start/60)*60,parts=clockFormat.formatToParts(new Date(first*1000));
    var minute=Number(parts.find(function(part){return part.type==='minute';}).value);
    first+=(60-minute)%60*60;
    for(var hour=first;hour<=day.end;hour+=3600){
      var position=(hour-day.start)/span*100,tick=text('span','','timeline-tick');
      tick.style.left=position+'%';tick.setAttribute('aria-hidden','true');result.appendChild(tick);
      if(position>3&&position<97){
        var label=text('span',clockFormat.formatToParts(new Date(hour*1000)).find(function(part){return part.type==='hour';}).value,'timeline-hour');
        label.style.left=position+'%';label.title=clockAt(hour);hours.appendChild(label);
      }
    }
    var now=Date.now()/1000;if(now>=day.start&&now<day.end){var mark=text('span','','now-marker');mark.style.left=(now-day.start)/span*100+'%';result.appendChild(mark);}
    wrapper.appendChild(hours);
    var labels=text('div','','timeline-labels');labels.appendChild(text('span',clockAt(day.start)));labels.appendChild(text('span',clockAt(day.end)));wrapper.appendChild(labels);
    return wrapper;
  }
  function renderWork(){
    var target=$('workPreview');target.replaceChildren();
    if(!workSaved()){target.appendChild(text('p','Work availability is unavailable or out of date.','empty-state'));return;}
    var day=(snapshot.work.days||[]).find(function(item){return item.date===todayKey();});
    if(!day){target.appendChild(text('p','Today’s availability is unavailable.','empty-state'));return;}
    if(!workFresh()){
      target.appendChild(text('p','Saved schedule','work-status saved'));
      target.appendChild(text('p',workSavedNote(),'work-saved-note'));
      if(day.working)target.appendChild(timeline(day));
      else target.appendChild(text('p','No work scheduled in the saved calendar.','empty-state'));
      return;
    }
    if(!day.working){target.appendChild(text('p','No work scheduled today','work-status'));appendNextWork(target);return;}
    var now=Date.now()/1000,busy=(day.busy||[]).find(function(item){return item.start<=now&&item.end>now;}),next=(day.busy||[]).find(function(item){return item.start>now;});
    var inside=now>=day.start&&now<day.end;
    target.appendChild(text('p',inside?(busy?'Busy now':'Free now'):'Outside work hours','work-status'+(busy?' busy':'')));
    if(inside)target.appendChild(text('p',(busy?'Free in ':next?'Busy in ':'Work ends in ')+countdown((busy?busy.end:next?next.start:day.end)-now),'work-countdown'));
    else appendNextWork(target);
    target.appendChild(timeline(day));
  }
  function appendNextWork(target){
    var now=Date.now()/1000,next=(snapshot.work.days||[]).find(function(day){return day.working&&day.start>now;});
    target.appendChild(text('p',next?'Work starts in '+countdown(next.start-now):'No upcoming work in this calendar window','work-countdown'));
  }

  function weatherLabel(code){
    if(code===0)return 'Clear skies';if(code<=2)return 'Partly cloudy';if(code===3)return 'Overcast';
    if(code===45||code===48)return 'Foggy';if(code>=51&&code<=57)return 'Drizzle';
    if(code>=61&&code<=67)return 'Rain';if(code>=71&&code<=77)return 'Snow';
    if(code>=80&&code<=82)return 'Rain showers';if(code===85||code===86)return 'Snow showers';
    if(code>=95)return 'Thunderstorms';return 'Conditions unavailable';
  }
  function weatherFresh(){var data=snapshot&&snapshot.weather,now=Date.now()/1000;return Boolean(data&&data.available&&live&&now-data.checked_at<1800&&now-data.checked_at>=-5&&now-data.observed_at<3600);}
  function degrees(value){return typeof value==='number'?Math.round(value)+'°':'—';}
  function renderWeather(){
    var data=snapshot&&snapshot.weather,available=data&&data.available;
    $('weatherTemp').textContent=available?degrees(data.temperature)+'F':'—°F';
    $('weatherCondition').textContent=available?weatherLabel(data.code):'Weather unavailable';
    $('weatherLocation').textContent=(available?data.location:'Lakeview')+(available&&!weatherFresh()?' · saved':'');
    $('weatherForecast').textContent=available?'H '+degrees(data.high)+'  L '+degrees(data.low)+' · Rain '+(typeof data.rain_chance==='number'?Math.round(data.rain_chance)+'%':'—'):'Waiting for a local forecast';
  }
  function weatherDetails(){
    var content=modal('Local weather','LOCAL WEATHER · FAHRENHEIT'),data=snapshot&&snapshot.weather;
    if(!data||!data.available){content.appendChild(text('p','Local weather is temporarily unavailable.','empty-state'));return;}
    content.appendChild(text('p',degrees(data.temperature)+'F · '+weatherLabel(data.code),'work-status'));
    content.appendChild(text('p','Feels like '+degrees(data.feels_like)+'F · Wind '+Math.round(data.wind_mph)+' mph','detail-note'));
    content.appendChild(text('p','Today: high '+degrees(data.high)+'F / low '+degrees(data.low)+'F · Precipitation chance '+data.rain_chance+'%','detail-note'));
    content.appendChild(text('p',(weatherFresh()?'Updated ':'Saved forecast · updated ')+ago(data.checked_at)+'. Forecast data, not severe weather warnings.','detail-note'));
    content.appendChild(text('p','Weather data by Open-Meteo · open-meteo.com · CC BY 4.0','detail-note'));
  }
  function currentAlerts(){
    if(!isFresh())return [{id:'connection',severity:'warning',message:snapshot?'Home server data is stale · check Tailscale or the server':'Home server is unavailable · check Tailscale or the server'}];
    var result=(snapshot.alerts||[]).slice();
    if(!weatherFresh()&&!result.some(function(a){return a.id==='weather-stale';}))result.push({id:'weather-stale',severity:'warning',message:'Local weather needs an update'});
    return result;
  }
  function serviceNews(){
    var data=snapshot&&snapshot.outages,now=Date.now()/1000;
    var fresh=Boolean(data&&live&&typeof data.checked_at==='number'&&now-data.checked_at>=-5&&now-data.checked_at<900);
    var failed=data&&data.unavailable_sources||[];
    var items=(data&&data.items||[]).filter(function(item){return typeof item.checked_at==='number'&&now-item.checked_at>=-5&&now-item.checked_at<3600;});
    return {items:items,fresh:fresh,failed:failed};
  }
  function serviceNewsMessage(news){
    return !news.fresh?'Service news is unavailable or out of date':news.failed.length?'Status checks unavailable · '+news.failed.join(', '):'No active incidents reported by monitored providers';
  }
  function renderAlerts(){
    var alerts=currentAlerts(),index=Math.floor(Date.now()/1000/8)%Math.max(1,alerts.length),selected=alerts[index];
    $('alertDot').className='service-dot '+(selected?(selected.severity==='critical'?'offline':'stale'):'online');
    $('alertMessage').textContent=selected?selected.message:'All clear · no alerts';
    $('alertCount').textContent=alerts.length>1?(index+1)+' / '+alerts.length+' · Details →':'Details →';
    var news=serviceNews(),item=news.items[Math.floor(Date.now()/1000/12)%Math.max(1,news.items.length)];
    var saved=item&&(!news.fresh||news.failed.indexOf(item.source)>=0||Date.now()/1000-item.checked_at>=900);
    $('breakingLabel').textContent=item?(saved?'SAVED':'BREAKING'):'STATUS';
    $('breakingDot').className='service-dot '+(item?(saved?'unknown':item.severity==='critical'?'offline':'stale'):news.fresh&&!news.failed.length?'online':'unknown');
    $('breakingMessage').textContent=item?item.source+' · '+item.title+' · '+item.status:serviceNewsMessage(news);
  }
  function alertDetails(){
    var modalContent=modal('Alerts & service news','THINGS THAT NEED ATTENTION'),content=text('div','','reminder-file alerts-details'),alerts=currentAlerts(),news=serviceNews();
    content.setAttribute('data-nav','');content.tabIndex=0;
    if(!alerts.length)content.appendChild(text('p','All clear. No monitored issues need attention.','work-status'));
    alerts.forEach(function(alert){content.appendChild(text('p',alert.message,'alert-detail '+alert.severity));});
    content.appendChild(text('p','Checks: selected service health, Jarvis heartbeat, storage ≥90%, Codex limits ≥90%, and data freshness. Alerts refresh while Home is open.','detail-note'));
    content.appendChild(text('h3','Service news'));
    if(!news.items.length)content.appendChild(text('p',serviceNewsMessage(news),'detail-note'));
    news.items.forEach(function(item){
      var saved=!news.fresh||news.failed.indexOf(item.source)>=0||Date.now()/1000-item.checked_at>=900;
      var row=text('div',item.source+' · '+item.title,'alert-detail '+item.severity);
      row.appendChild(text('span',(saved?'Saved report · ':'Official report · ')+item.status+' · checked '+ago(item.checked_at)+(typeof item.updated_at==='number'?' · updated '+ago(item.updated_at):''),'outage-source'));
      row.appendChild(text('span',item.url,'outage-source'));content.appendChild(row);
    });
    if(news.failed.length)content.appendChild(text('p','Could not refresh: '+news.failed.join(', ')+'. Saved reports may have changed.','detail-note'));
    content.appendChild(text('p','Public status reports refresh every five minutes. Only active incidents are shown; provider reports may lag.','detail-note'));
    modalContent.appendChild(content);setFocus(content);
  }
  function workWeek(){
    var content=modal('Your work week','ANONYMOUS AVAILABILITY');
    if(!workSaved()){content.appendChild(text('p','Work availability is unavailable or out of date.','empty-state'));return;}
    if(!workFresh())content.appendChild(text('p',workSavedNote()+'. Availability may have changed.','detail-note'));
    content.appendChild(text('p','Chicago time · green is free, rose is busy. Outlook publishing may lag.','detail-note'));
    var list=text('div','','reminder-file');list.setAttribute('data-nav','');list.tabIndex=0;
    (snapshot.work.days||[]).forEach(function(day){var row=text('div','','work-day'),heading=text('div','','work-day-heading');heading.appendChild(text('strong',new Intl.DateTimeFormat('en-US',{timeZone:config.timezone,weekday:'long',month:'short',day:'numeric'}).format(new Date(day.start*1000))));heading.appendChild(text('span',day.working?clockAt(day.start)+' – '+clockAt(day.end):'No work scheduled'));row.appendChild(heading);if(day.working)row.appendChild(timeline(day));list.appendChild(row);});
    content.appendChild(list);setFocus(list);
  }
  function windowLabel(minutes){return minutes>=1440&&minutes%1440===0?(minutes/1440)+'d window':minutes>=60&&minutes%60===0?(minutes/60)+'h window':minutes+'m window';}
  function renderCodex(){
    var target=$('codexPreview');target.replaceChildren();var codex=snapshot&&snapshot.codex;
    if(!codex||!codex.available||!codex.windows||!codex.windows.length){$('usageFreshness').textContent='Unavailable';target.appendChild(text('p','Usage data is temporarily unavailable.','empty-state'));return;}
    var age=Date.now()/1000-codex.checked_at,stale=!live||age>900;
    $('usageFreshness').textContent=stale?'Last observed':age<60?'Updated just now':'Updated '+Math.floor(age/60)+'m ago';
    codex.windows.slice(0,2).forEach(function(window){var row=text('div','','usage-window'),label=text('div','','usage-label');label.appendChild(text('span',windowLabel(window.window_minutes)));label.appendChild(text('strong',Math.round(window.used_percent)+'% used'));row.appendChild(label);var bar=text('div','','usage-bar'),fill=text('div','','usage-fill');fill.style.width=window.used_percent+'%';bar.appendChild(fill);row.appendChild(bar);if(window.resets_at){var seconds=window.resets_at-Date.now()/1000;row.appendChild(text('div',seconds>0?'Resets in '+duration(seconds):'Reset pending refresh','usage-reset'));}target.appendChild(row);});
  }
  function renderFreshness() {
    var fresh=isFresh(), badge=$('linkBadge');
    badge.className='badge '+(fresh?'online':snapshot?'stale':'offline');
    badge.querySelector('span').textContent=fresh?'Home server connected':snapshot?'Showing saved data':'Home server unavailable';
    var age=snapshot && snapshot.collected_at ? Math.max(0,Math.floor(Date.now()/1000-snapshot.collected_at)) : null;
    $('freshness').textContent=age===null?'Local home is ready':fresh?'Updated '+(age<5?'just now':age+'s ago'):'Last update '+(age<60?age+'s':duration(age))+' ago';
  }
  function teamsLive(){var age=snapshot&&Date.now()/1000-snapshot.served_at;return Boolean(live&&typeof age==='number'&&age>=-5&&age<60);}
  function teamsPending(){var data=snapshot&&snapshot.teams;return Boolean(data&&data.pending&&data.last_received_at&&localStorage.getItem('jarvis-teams-dismissed')!==String(data.last_received_at));}
  function renderTeams(){
    var data=snapshot&&snapshot.teams,pending=teamsPending(),fresh=teamsLive();
    var label=!data||!data.configured?'Not linked':!fresh?(pending?'Saved alert':'Status stale'):!data.initialized?'Awaiting first signal':pending?'New notification':'No new signal';
    $('teamsLabel').textContent='Teams · '+label;
    $('teamsButton').className='teams-button'+(pending?' pending':'')+(!fresh?' saved':'');
    $('teamsDot').className='service-dot '+(pending?'stale':fresh&&data&&data.initialized?'online':'unknown');
    var notice=$('teamsNotice'),hadFocus=document.activeElement===notice;
    notice.hidden=!pending;$('welcomeMessage').hidden=pending;
    $('teamsNoticeTitle').textContent=fresh?'Teams notification':'Saved Teams notification';
    $('teamsNoticeSubtitle').textContent=fresh?'New notification received · Select to view':'Status out of date · Select to view';
    if(!pending&&focusBeforeModal===notice)focusBeforeModal=$('teamsButton');
    if(!pending&&hadFocus)setFocus($('teamsButton'));
  }
  function teamsDetails(){
    var content=modal('Teams notifications','PRIVATE NOTIFICATION SIGNAL'),data=snapshot&&snapshot.teams,pending=teamsPending();
    if(!data||!data.configured){content.appendChild(text('p','Your iPhone relay is not linked yet.','empty-state'));return;}
    if(!teamsLive())content.appendChild(text('p','Showing saved status. Reconnect to Home server for new signals.','offline-note'));
    content.appendChild(text('p',!data.initialized?'Waiting for the first iPhone signal.':pending?'A Teams notification arrived.':'No new notification signal.','work-status'));
    if(data.last_received_at)content.appendChild(text('p','Last notification '+ago(data.last_received_at)+'.','detail-note'));
    if(pending){var dismiss=button('Dismiss on this TV','teams-dismiss',function(){localStorage.setItem('jarvis-teams-dismissed',String(data.last_received_at));renderTeams();closeModal();});content.appendChild(dismiss);setFocus(dismiss);}
    content.appendChild(text('p','Only Teams notifications delivered to your iPhone are detected. Names and message text are not sent. This is a notification signal, not an unread-message count.','detail-note'));
    content.appendChild(text('p','Keep Tailscale connected on the iPhone. Opening Teams clears this badge only if you add the optional clear automation. Dismissing here does not mark messages read.','detail-note'));
  }
  window.receiveApps=function (value) {
    try { apps=JSON.parse(value); } catch (error) {return;}
    $('appCount').textContent=apps.length+' apps on your TV';
  };
  window.receiveSnapshot=function (value,connected) {
    try {snapshot=JSON.parse(value);} catch (error) {return;}
    live=connected; receivedAt=Date.now();
    renderReminders();renderServices();renderNews();renderFreshness();renderWork();renderCodex();renderWeather();renderAlerts();renderTeams();
    if (snapshot.reminders && snapshot.reminders.available) $('daySummary').textContent=snapshot.reminders.unfinished+' reminders on your radar. Everything in one place.';
  };
  window.receiveNetworkError=function () {live=false;renderFreshness();renderServices();renderNews();renderWork();renderCodex();renderWeather();renderAlerts();renderTeams();};

  window.jarvisKey=function (key) {
    interaction();
    if (key==='menu') { settings(); return; }
    if (key==='back') { if(!overlay.hidden)closeModal(); else setFocus($('firstApp')); return; }
    var active=document.activeElement;
    if(key==='ok') { if(active && active.tagName==='BUTTON')active.click(); return; }
    if(active && active.classList.contains('reminder-file') && (key==='down'||key==='up')) {active.scrollTop+=(key==='down'?1:-1)*100;return;}
    var scope=overlay.hidden?$('home'):overlay;
    var nodes=Array.prototype.filter.call(scope.querySelectorAll('[data-nav]'),function(node){return node.getClientRects().length && !node.disabled;});
    if(!nodes.length)return;
    if(nodes.indexOf(active)===-1){setFocus(nodes[0]);return;}
    var current=active.getBoundingClientRect(),cx=current.left+current.width/2,cy=current.top+current.height/2;
    var horizontal=key==='left'||key==='right',positive=key==='right'||key==='down';
    var best=null,bestScore=Infinity;
    nodes.forEach(function(node){
      if(node===active)return;
      var rect=node.getBoundingClientRect(),dx=rect.left+rect.width/2-cx,dy=rect.top+rect.height/2-cy;
      var axis=horizontal?dx:dy,cross=horizontal?dy:dx;
      if((positive?axis:-axis)<2)return;
      var overlap=horizontal?Math.min(current.bottom,rect.bottom)>Math.max(current.top,rect.top):Math.min(current.right,rect.right)>Math.max(current.left,rect.left);
      var score=Math.abs(axis)+Math.abs(cross)*(overlap?.25:3)+(overlap?0:50);
      if(score<bestScore){bestScore=score;best=node;}
    });
    setFocus(best);
  };

  function tick() {
    var now=new Date(),parts=clockFormat.formatToParts(now),time='',period='';
    if(window.JarvisDaylight)window.JarvisDaylight.refresh(false,now);
    parts.forEach(function(part){if(part.type==='dayPeriod')period=part.value;else if(part.type!=='literal'||part.value.indexOf(':')>=0)time+=part.value;});
    $('clockTime').textContent=time.trim();$('clockPeriod').textContent=period;
    $('date').textContent=dateFormat.format(now);
    var hour=Number(new Intl.DateTimeFormat('en-US',{timeZone:config.timezone,hour:'numeric',hourCycle:'h23'}).format(now));
    $('greeting').textContent=(hour<12?'Good morning':hour<17?'Good afternoon':'Good evening')+', '+config.name+'.';
    renderFreshness();
    renderWork();renderWeather();renderAlerts();renderTeams();
    if(snapshot && !isFresh()){renderServices();renderWork();renderCodex();}
    if(snapshot && now.getSeconds()===0){renderWork();renderCodex();}
    var ambient=localStorage.getItem('jarvis-dim')!=='off' && Date.now()-lastInput>config.ambientAfterSeconds*1000;
    document.body.classList.toggle('ambient',ambient);
    $('home').style.transform=ambient?'translate('+((now.getMinutes()%3)-1)*2+'px,'+((now.getMinutes()%5)-2)+'px)':'';
  }
  $('settingsButton').onclick=settings;$('allAppsButton').onclick=allApps;$('remindersButton').onclick=reminders;$('servicesButton').onclick=systems;$('closeOverlay').onclick=closeModal;
  $('newsButton').onclick=moreNews;$('workButton').onclick=workWeek;
  $('weatherButton').onclick=weatherDetails;$('alertsButton').onclick=alertDetails;
  $('teamsButton').onclick=teamsDetails;
  $('teamsNotice').onclick=teamsDetails;
  Array.prototype.forEach.call(document.querySelectorAll('[data-package]'),function(node){node.onclick=function(){launch(node.getAttribute('data-package'));};});
  document.addEventListener('keydown',function(event){var keys={ArrowLeft:'left',ArrowRight:'right',ArrowUp:'up',ArrowDown:'down',Enter:'ok',Escape:'back'};if(keys[event.key]){event.preventDefault();window.jarvisKey(keys[event.key]);}});
  document.addEventListener('pointerdown',interaction);
  setTheme(localStorage.getItem('jarvis-theme')||config.defaultTheme,false);
  if(localStorage.getItem('jarvis-accent')==='rose')document.body.classList.add('warm');
  tick();setInterval(tick,1000);setInterval(function(){newsIndex++;renderNews();},config.newsRotationSeconds*1000);
  setFocus($('firstApp'));
  if(native)native.ready();
}());
