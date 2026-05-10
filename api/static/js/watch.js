/* ═══════════════════════════════════════════════════════════════
 *  YumeZone Watch — Custom HLS.js Player (Kurovexa architecture)
 *  Fixes: segment looping · infinite buffer · retry loops
 * ═══════════════════════════════════════════════════════════════ */

// ── MSE Codec Patch ──────────────────────────────────────────────
(function () {
    if (typeof MediaSource === 'undefined') return;
    const _orig = MediaSource.prototype.addSourceBuffer;
    MediaSource.prototype.addSourceBuffer = function (t) {
        return _orig.call(this, t.replace('mp4a.40.1', 'mp4a.40.2'));
    };
})();

// ── State ────────────────────────────────────────────────────────
let hlsInstance = null;
let _lastProbe   = { t: 0, ct: -1 };
let _ctrlTimer   = null;
let _watchedMarked = false;
let _isFallbackInProgress = false;
let _failedProviders = new Set();
const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];

// ── Helpers ──────────────────────────────────────────────────────
function fmt(s) {
    if (!isFinite(s) || s < 0) return '0:00';
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = Math.floor(s % 60);
    return h ? `${h}:${String(m).padStart(2,'0')}:${String(ss).padStart(2,'0')}`
             : `${m}:${String(ss).padStart(2,'0')}`;
}

function isPlaybackHealthy() {
    const vid = document.getElementById('yz-video');
    if (!vid || vid.paused || vid.ended || vid.readyState < 3 || !(vid.currentTime > 0)) return false;
    const now = Date.now(), moved = vid.currentTime !== _lastProbe.ct, fresh = (now - _lastProbe.t) < 1500;
    _lastProbe = { t: now, ct: vid.currentTime };
    return !fresh || moved;
}

// ── Build Custom Player HTML ──────────────────────────────────────
function buildCustomPlayer(playerArea, video) {
    playerArea.innerHTML = '';
    video.id = 'yz-video';
    video.style.cssText = 'width:100%;height:100%;display:block;background:#000;';

    const shell = document.createElement('div');
    shell.className = 'yz-player'; shell.id = 'yz-player';
    shell.innerHTML = `
<div id="yz-buffering" class="yz-buffering" style="display:none"><div class="yz-spinner"></div></div>
<button id="yz-skip-btn" class="yz-skip-btn" style="display:none">Skip Intro</button>
<div id="yz-overlay" class="yz-overlay"></div>
<div id="yz-dt-left" class="yz-dt-zone yz-dt-left">
  <div class="yz-dt-indicator"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 .49-3.51"/></svg><span>10s</span></div>
</div>
<div id="yz-dt-right" class="yz-dt-zone yz-dt-right">
  <div class="yz-dt-indicator"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round"><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-.49-3.51"/></svg><span>10s</span></div>
</div>
<div id="yz-pause-flash" class="yz-pause-flash">
  <svg width="56" height="56" viewBox="0 0 24 24" fill="rgba(255,255,255,.85)"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
</div>
<div id="yz-resume-toast" class="yz-resume-toast" style="display:none"></div>
<div id="yz-controls" class="yz-controls yz-hidden">
  <div class="yz-progress-wrap" id="yz-progress-wrap">
    <div class="yz-buf-bar" id="yz-buf-bar"></div>
    <div class="yz-play-bar" id="yz-play-bar"></div>
    <input type="range" id="yz-seek" class="yz-seek" min="0" max="100" step="0.01" value="0">
    <div class="yz-tooltip" id="yz-tooltip">0:00</div>
  </div>
  <div class="yz-ctrl-row">
    <div class="yz-ctrl-left">
      <button id="yz-play-btn" class="yz-btn" title="Play/Pause (K)">
        <svg class="icon-play" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
        <svg class="icon-pause" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" style="display:none"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
      </button>
      <button id="yz-back10" class="yz-btn" title="-10s">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 .49-3.51"/></svg>
      </button>
      <button id="yz-fwd10" class="yz-btn" title="+10s">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-.49-3.51"/></svg>
      </button>
      <button id="yz-mute-btn" class="yz-btn" title="Mute (M)">
        <svg class="icon-vol" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
        <svg class="icon-muted" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:none"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>
      </button>
      <input type="range" id="yz-vol" class="yz-vol" min="0" max="1" step="0.02" value="1">
      <span id="yz-time" class="yz-time">0:00 / 0:00</span>
    </div>
    <div class="yz-ctrl-right">
      <button id="yz-sett-btn" class="yz-btn" title="Settings">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
      </button>
      <button id="yz-fs-btn" class="yz-btn" title="Fullscreen (F)">
        <svg class="icon-fs" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>
        <svg class="icon-exit-fs" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:none"><polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="14" y1="10" x2="21" y2="3"/><line x1="3" y1="21" x2="10" y2="14"/></svg>
      </button>
    </div>
  </div>
</div>
<div id="yz-settings" class="yz-settings" style="display:none">
  <div id="yz-sett-main">
    <button class="yz-sett-row" id="yz-speed-row"><span>Speed</span><span id="yz-cur-speed" class="yz-sett-val">1x</span></button>
    <button class="yz-sett-row" id="yz-qual-row" style="display:none"><span>Quality</span><span id="yz-cur-qual" class="yz-sett-val">Auto</span></button>
  </div>
  <div id="yz-sett-speed" style="display:none">
    <button class="yz-sett-back" id="yz-speed-back">&#8592; Speed</button>
    <div id="yz-speed-opts" class="yz-sett-opts"></div>
  </div>
  <div id="yz-sett-qual" style="display:none">
    <button class="yz-sett-back" id="yz-qual-back">&#8592; Quality</button>
    <div id="yz-qual-opts" class="yz-sett-opts"></div>
  </div>
</div>`;
    shell.prepend(video);
    playerArea.appendChild(shell);
    attachPlayerControls(shell, video);
}

// ── Attach Controls ───────────────────────────────────────────────
function attachPlayerControls(shell, vid) {
    const g = id => shell.querySelector('#' + id) || document.getElementById(id);
    const controls    = g('yz-controls'),  playBtn   = g('yz-play-btn'),
          muteBtn     = g('yz-mute-btn'),  volSlider = g('yz-vol'),
          seekSlider  = g('yz-seek'),      progWrap  = g('yz-progress-wrap'),
          playBar     = g('yz-play-bar'),  bufBar    = g('yz-buf-bar'),
          timeEl      = g('yz-time'),      tooltip   = g('yz-tooltip'),
          bufEl       = g('yz-buffering'), skipBtn   = g('yz-skip-btn'),
          settBtn     = g('yz-sett-btn'), settPanel  = g('yz-settings'),
          settMain    = g('yz-sett-main'), settSpeed  = g('yz-sett-speed'),
          settQual    = g('yz-sett-qual'), speedOpts  = g('yz-speed-opts'),
          qualOpts    = g('yz-qual-opts'), curSpeedLbl= g('yz-cur-speed'),
          curQualLbl  = g('yz-cur-qual'),  qualRow   = g('yz-qual-row'),
          fsBtn       = g('yz-fs-btn'),    overlay   = g('yz-overlay'),
          pauseFlash  = g('yz-pause-flash'),back10   = g('yz-back10'),
          fwd10       = g('yz-fwd10');

    const cfg = window.WATCH_CONFIG || {};
    let skipTarget = null;

    // Skip intro/outro
    vid.addEventListener('timeupdate', () => {
        if (!skipBtn) return;
        const cur = vid.currentTime, i = cfg.intro, o = cfg.outro;
        let found = false;
        if (i && cur >= i.start && cur <= i.end)       { skipBtn.textContent='Skip Intro'; skipBtn.style.display='block'; skipTarget=i.end; found=true; }
        else if (o && cur >= o.start && cur <= o.end)  { skipBtn.textContent='Skip Outro'; skipBtn.style.display='block'; skipTarget=o.end; found=true; }
        if (!found) { skipBtn.style.display='none'; skipTarget=null; }
    });
    skipBtn?.addEventListener('click', e => { e.stopPropagation(); if (skipTarget!==null){vid.currentTime=skipTarget;skipBtn.style.display='none';} });

    // Buffering
    vid.addEventListener('waiting', ()=>{ if(bufEl) bufEl.style.display='flex'; });
    vid.addEventListener('playing', ()=>{ if(bufEl) bufEl.style.display='none'; });
    vid.addEventListener('canplay', ()=>{ if(bufEl) bufEl.style.display='none'; });

    // Play/Pause
    function syncPlay() {
        g('yz-play-btn')?.querySelector('.icon-play')?.style.setProperty('display', vid.paused?'':'none');
        g('yz-play-btn')?.querySelector('.icon-pause')?.style.setProperty('display', vid.paused?'none':'');
    }
    playBtn?.addEventListener('click', ()=> vid.paused ? vid.play() : vid.pause());
    vid.addEventListener('play', syncPlay);
    vid.addEventListener('pause', ()=>{ syncPlay(); flashEl(pauseFlash); });
    function flashEl(el) { if(!el) return; el.classList.remove('yz-flash'); void el.offsetWidth; el.classList.add('yz-flash'); }

    // Volume
    function syncMute() {
        const m = vid.muted||vid.volume===0;
        muteBtn?.querySelector('.icon-vol')?.style.setProperty('display', m?'none':'');
        muteBtn?.querySelector('.icon-muted')?.style.setProperty('display', m?'':'none');
        if(volSlider) volSlider.style.setProperty('--pct', (m?0:vid.volume*100)+'%');
    }
    volSlider?.addEventListener('input', ()=>{ vid.volume=parseFloat(volSlider.value); vid.muted=(volSlider.value==0); syncMute(); });
    muteBtn?.addEventListener('click', ()=>{ vid.muted=!vid.muted; if(!vid.muted&&vid.volume===0) vid.volume=0.5; if(volSlider) volSlider.value=vid.muted?0:vid.volume; syncMute(); });

    // Seek & time
    const resumeKey = `yumeResume_${cfg.animeId||''}_ep${cfg.episodeNumber||''}`;
    let _lastSave = 0;
    vid.addEventListener('timeupdate', ()=>{
        if (!vid.duration) return;
        const pct = (vid.currentTime/vid.duration)*100;
        if (seekSlider) { seekSlider.value=pct; seekSlider.style.setProperty('--pct',pct+'%'); }
        if (playBar)    playBar.style.width = pct+'%';
        if (timeEl)     timeEl.textContent  = `${fmt(vid.currentTime)} / ${fmt(vid.duration)}`;
        
        const now = Date.now();
        if (now - _lastSave > 3000) {
            _lastSave = now;
            if(vid.currentTime>3&&(vid.duration-vid.currentTime)>5){ 
                try{localStorage.setItem(resumeKey,Math.floor(vid.currentTime));}catch{} 
                saveWatchHistory(vid.currentTime,vid.duration); 
            }
        }
        if (vid.duration>0 && (vid.currentTime/vid.duration)>=0.8) markEpisodeWatched();
    });
    vid.addEventListener('progress', ()=>{
        if (!vid.duration||!bufBar) return;
        let buf=0; for(let i=0;i<vid.buffered.length;i++) if(vid.buffered.start(i)<=vid.currentTime) buf=vid.buffered.end(i);
        bufBar.style.width = ((buf/vid.duration)*100)+'%';
    });
    vid.addEventListener('canplay', ()=>{ 
        try {
            const s=parseInt(localStorage.getItem(resumeKey)); 
            if(s>5) {
                if (vid.duration && s >= vid.duration-10) return;
                vid.currentTime=s; 
                var rt=g('yz-resume-toast'); 
                if(rt){rt.textContent='Resuming from '+fmt(s);rt.style.display='flex';setTimeout(function(){rt.style.display='none';},3000);} 
            }
        } catch{} 
    }, {once:true});
    vid.addEventListener('ended',   ()=>{ try{localStorage.removeItem(resumeKey);}catch{} });
    vid.addEventListener('pause',   ()=>{ 
        if(vid.currentTime>3&&vid.duration&&(vid.duration-vid.currentTime)>5) { 
            try{localStorage.setItem(resumeKey,Math.floor(vid.currentTime));}catch{} 
            saveWatchHistory(vid.currentTime,vid.duration); 
        } 
    });

    seekSlider?.addEventListener('input', ()=>{ if(vid.duration) vid.currentTime=(seekSlider.value/100)*vid.duration; seekSlider.style.setProperty('--pct',seekSlider.value+'%'); });
    progWrap?.addEventListener('mousemove', e=>{
        if(!vid.duration||!tooltip) return;
        const r=progWrap.getBoundingClientRect(), f=Math.max(0,Math.min(1,(e.clientX-r.left)/r.width));
        tooltip.textContent=fmt(f*vid.duration); tooltip.style.left=(f*100)+'%'; tooltip.style.opacity='1';
    });
    progWrap?.addEventListener('mouseleave', ()=>{ if(tooltip) tooltip.style.opacity='0'; });

    // ±10s
    back10?.addEventListener('click', e=>{ e.stopPropagation(); vid.currentTime=Math.max(0,vid.currentTime-10); });
    fwd10?.addEventListener('click',  e=>{ e.stopPropagation(); vid.currentTime=Math.min(vid.duration||0,vid.currentTime+10); });

    // ── Keyboard Shortcuts ──
    document.addEventListener('keydown', function(e) {
        // Ignore if user is typing in an input/textarea (like search or comments)
        if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
        
        switch (e.key.toLowerCase()) {
            case 'f':
                e.preventDefault();
                fsBtn?.click();
                break;
            case ' ':
                e.preventDefault();
                vid.paused ? vid.play() : vid.pause();
                showCtrls();
                break;
            case 'arrowright':
                e.preventDefault();
                vid.currentTime = Math.min(vid.duration || 0, vid.currentTime + 10);
                showCtrls();
                break;
            case 'arrowleft':
                e.preventDefault();
                vid.currentTime = Math.max(0, vid.currentTime - 10);
                showCtrls();
                break;
            case 'arrowup':
                e.preventDefault();
                vid.volume = Math.min(1, vid.volume + 0.05);
                vid.muted = (vid.volume === 0);
                if (volSlider) volSlider.value = vid.volume;
                syncMute();
                showCtrls();
                break;
            case 'arrowdown':
                e.preventDefault();
                vid.volume = Math.max(0, vid.volume - 0.05);
                vid.muted = (vid.volume === 0);
                if (volSlider) volSlider.value = vid.volume;
                syncMute();
                showCtrls();
                break;
            case 'm':
                e.preventDefault();
                muteBtn?.click();
                showCtrls();
                break;
        }
    });

    // ── Right-click to skip 10s ──
    shell.addEventListener('contextmenu', function(e) {
        e.preventDefault(); // Prevent default browser context menu
        vid.currentTime = Math.min(vid.duration || 0, vid.currentTime + 10);
        showCtrls();
    });

    // Controls auto-hide
    function showCtrls() {
        controls?.classList.remove('yz-hidden'); shell.style.cursor='';
        clearTimeout(_ctrlTimer);
        if (!vid.paused) _ctrlTimer = setTimeout(()=>{ controls?.classList.add('yz-hidden'); shell.style.cursor='none'; if(settPanel) settPanel.style.display='none'; }, 3000);
    }
    shell.addEventListener('mousemove', showCtrls);
    shell.addEventListener('mouseenter', showCtrls);

    // ── Mobile double-tap seek & tap-to-toggle ──
    var _isMobile = navigator.maxTouchPoints > 0;
    var _dtLeftZone = g('yz-dt-left'), _dtRightZone = g('yz-dt-right');
    if (_isMobile && _dtLeftZone && _dtRightZone) {
        function setupDoubleTap(zone, seekDelta) {
            var lastTap = 0, tapTimeout = null;
            zone.addEventListener('click', function(e) {
                e.stopPropagation();
                var now = Date.now();
                if (now - lastTap < 300) {
                    clearTimeout(tapTimeout);
                    vid.currentTime = Math.max(0, Math.min(vid.duration || 0, vid.currentTime + seekDelta));
                    var ind = zone.querySelector('.yz-dt-indicator');
                    if (ind) { ind.classList.remove('yz-dt-active','yz-dt-fade'); void ind.offsetWidth; ind.classList.add('yz-dt-active'); setTimeout(function(){ ind.classList.remove('yz-dt-active'); ind.classList.add('yz-dt-fade'); }, 300); setTimeout(function(){ ind.classList.remove('yz-dt-fade'); }, 800); }
                    showCtrls();
                } else {
                    tapTimeout = setTimeout(function() {
                        controls?.classList.contains('yz-hidden') ? showCtrls() : controls?.classList.add('yz-hidden');
                    }, 300);
                }
                lastTap = now;
            });
        }
        setupDoubleTap(_dtLeftZone, -10);
        setupDoubleTap(_dtRightZone, 10);
    }

    overlay?.addEventListener('click', ()=>{
        vid.paused ? vid.play() : vid.pause();
        if (_isMobile) showCtrls();
    });

    // Settings
    function showSettPage(p) { settMain.style.display=p==='main'?'':'none'; settSpeed.style.display=p==='speed'?'':'none'; settQual.style.display=p==='qual'?'':'none'; }
    settBtn?.addEventListener('click', e=>{ e.stopPropagation(); settPanel.style.display=settPanel.style.display==='none'?'block':'none'; if(settPanel.style.display!=='none'){showSettPage('main');showCtrls();} });
    g('yz-speed-row')?.addEventListener('click', ()=>showSettPage('speed'));
    qualRow?.addEventListener('click', ()=>showSettPage('qual'));
    g('yz-speed-back')?.addEventListener('click', ()=>showSettPage('main'));
    g('yz-qual-back')?.addEventListener('click',  ()=>showSettPage('main'));
    document.addEventListener('click', e=>{ if(settPanel&&!settPanel.contains(e.target)&&!settBtn?.contains(e.target)) settPanel.style.display='none'; }, true);
    settPanel?.addEventListener('click', e=>e.stopPropagation());

    // Speed options
    if (speedOpts) {
        speedOpts.innerHTML = SPEEDS.map(s=>`<button class="yz-opt${s===1?' active':''}" data-speed="${s}">${s}x</button>`).join('');
        speedOpts.addEventListener('click', e=>{ const b=e.target.closest('[data-speed]'); if(!b) return; vid.playbackRate=parseFloat(b.dataset.speed); if(curSpeedLbl) curSpeedLbl.textContent=b.dataset.speed+'x'; speedOpts.querySelectorAll('.yz-opt').forEach(x=>x.classList.toggle('active',x===b)); setTimeout(()=>showSettPage('main'),250); });
    }

    // Quality builder (called by playHLS after MANIFEST_PARSED)
    shell._buildQuality = function(levels, current) {
        if (!qualOpts||!levels||levels.length<=1) { if(qualRow) qualRow.style.display='none'; return; }
        if (qualRow) qualRow.style.display='';
        if (curQualLbl) curQualLbl.textContent = current||levels[0]?.label||'Auto';
        qualOpts.innerHTML = levels.map(l=>`<button class="yz-opt${l.label===current?' active':''}" data-label="${l.label}" data-url="${l.url||''}">${l.label}</button>`).join('');
        qualOpts.addEventListener('click', e=>{
            const b=e.target.closest('[data-label]'); if(!b) return;
            if(curQualLbl) curQualLbl.textContent=b.dataset.label;
            qualOpts.querySelectorAll('.yz-opt').forEach(x=>x.classList.toggle('active',x===b));
            if (b.dataset.url && hlsInstance) { hlsInstance.loadSource(b.dataset.url); }
            setTimeout(()=>showSettPage('main'),250);
        });
    };

    // Fullscreen + mobile landscape rotation
    fsBtn?.addEventListener('click', ()=>{
        if (!document.fullscreenElement) shell.requestFullscreen?.()?.catch(()=>{});
        else document.exitFullscreen?.();
    });
    document.addEventListener('fullscreenchange', ()=>{
        const fs=!!document.fullscreenElement;
        fsBtn?.querySelector('.icon-fs')?.style.setProperty('display',fs?'none':'');
        fsBtn?.querySelector('.icon-exit-fs')?.style.setProperty('display',fs?'':'none');
        // Lock landscape on mobile fullscreen
        if (_isMobile && screen.orientation && screen.orientation.lock) {
            if (fs) { try { screen.orientation.lock('landscape').catch(function(){}); } catch(e){} }
            else    { try { screen.orientation.unlock(); } catch(e){} }
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', e=>{
        if (['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) return;
        if (e.key===' '||e.key==='k') { e.preventDefault(); vid.paused?vid.play():vid.pause(); }
        if (e.key==='ArrowRight') { e.preventDefault(); vid.currentTime=Math.min(vid.duration||0,vid.currentTime+5); }
        if (e.key==='ArrowLeft')  { e.preventDefault(); vid.currentTime=Math.max(0,vid.currentTime-5); }
        if (e.key==='m')          { vid.muted=!vid.muted; syncMute(); }
        if (e.key==='f')          { fsBtn?.click(); }
    });

    syncPlay(); syncMute();
    if (volSlider) { volSlider.value=vid.muted?0:vid.volume; volSlider.style.setProperty('--pct',(vid.muted?0:vid.volume*100)+'%'); }
}
// ── playHLS ───────────────────────────────────────────────────────
function playHLS(rawUrl, allStreams) {
    const playerArea = document.getElementById('player-area');
    if (!playerArea) return;
    if (hlsInstance) { hlsInstance.destroy(); hlsInstance = null; }

    const video = document.createElement('video');
    video.crossOrigin = 'anonymous';
    video.autoplay    = true;
    video.playsInline = true;
    buildCustomPlayer(playerArea, video);

    const shell = playerArea.querySelector('.yz-player');
    const vid   = playerArea.querySelector('#yz-video');
    if (!vid) return;

    if (typeof Hls === 'undefined') { console.error('[HLS] hls.js not loaded'); return; }

    if (Hls.isSupported()) {
        hlsInstance = new Hls({ enableWorker: true, lowLatencyMode: false });

        hlsInstance.on(Hls.Events.ERROR, function(_, d) {
            if (!d.fatal) return;
            if (d.type === Hls.ErrorTypes.MEDIA_ERROR) {
                hlsInstance.swapAudioCodec();
                hlsInstance.recoverMediaError();
            } else {
                if (isPlaybackHealthy()) { console.warn('[HLS] fatal but healthy, ignoring'); return; }
                console.warn('[HLS] fatal error:', d.type, d.details);
                onHlsFatal();
            }
        });

        hlsInstance.on(Hls.Events.MANIFEST_PARSED, function(_, data) {
            vid.play().catch(function(){});
            if (shell && shell._buildQuality && data.levels && data.levels.length > 1) {
                var seen = new Set();
                var levels = data.levels
                    .map(function(l, i) {
                        var url = Array.isArray(l.url) ? l.url[0] : l.url;
                        return { label: l.height ? l.height + 'p' : (l.name || String(i+1)), url: url };
                    })
                    .filter(function(l) { if (!l.url || seen.has(l.label)) return false; seen.add(l.label); return true; });
                if (levels.length > 1) shell._buildQuality(levels, levels[levels.length-1].label);
            }
        });

        hlsInstance.loadSource(rawUrl);
        hlsInstance.attachMedia(vid);

    } else if (vid.canPlayType('application/vnd.apple.mpegurl')) {
        vid.src = rawUrl;
        vid.play().catch(function(){});
    } else {
        playerArea.innerHTML = '<div style="color:#94a3b8;text-align:center;padding:40px;">HLS not supported in this browser.</div>';
    }
}

// ── playEmbed ─────────────────────────────────────────────────────
function playEmbed(url) {
    var playerArea = document.getElementById('player-area');
    if (!playerArea) return;
    if (hlsInstance) { hlsInstance.destroy(); hlsInstance = null; }
    var isAdHeavy = /megaplay\.buzz|vidwish/i.test(url);
    var sb = isAdHeavy
        ? 'sandbox="allow-scripts allow-same-origin allow-forms allow-presentation"'
        : 'sandbox="allow-scripts allow-same-origin allow-forms allow-presentation allow-pointer-lock"';
    playerArea.innerHTML =
        '<div style="position:relative;width:100%;height:100%;background:#000">'
        + '<iframe src="' + url + '" allowfullscreen allow="autoplay;fullscreen;picture-in-picture" '
        + 'referrerpolicy="origin" ' + sb + ' style="width:100%;height:100%;border:none;display:block"></iframe>'
        + '</div>';
    saveWatchHistory(0, 0);
}

// ── HLS fatal → trigger provider fallback ─────────────────────────
function onHlsFatal() {
    var cur = window._watchState && window._watchState.provider;
    if (!cur || _isFallbackInProgress) return;
    markProviderFailed(cur, 'hls');
    var next = getNextAvailableProvider(cur);
    if (next) {
        showFallbackToast(cur, next);
        window._watchState.provider = next;
        _isFallbackInProgress = true;
        fetchAndLoadSources(true);
    } else {
        showNoSourcesMessage();
    }
}

// ── Provider fallback system ──────────────────────────────────────
var _PROVIDER_PRIORITY = ['kiwi','ax-mimi','ax-wave','ax-shiro','ax-yuki','ax-zen','bee','zoro'];
var PROVIDER_DISPLAY_NAMES = {
    "kiwi":      "Miku",
    "ax-mimi":   "Shinra",
    "ax-wave":   "Nami",
    "ax-shiro":  "Shiro",
    "ax-yuki":   "Yuki",
    "ax-zen":    "Senku",
    "bee":       "Hachi",
    "zoro":      "Megaplay",
};

function applyServerDisplayNames() {
    document.querySelectorAll('.server-pill').forEach(function(pill) {
        var p = pill.dataset.provider;
        if (PROVIDER_DISPLAY_NAMES[p]) {
            // Keep the badge span
            var badge = pill.querySelector('.srv-badge');
            pill.childNodes[0].textContent = PROVIDER_DISPLAY_NAMES[p] + ' ';
            if (badge) pill.appendChild(badge);
        }
    });
}
// Run immediately
applyServerDisplayNames();

function resetFailedProviders() { _failedProviders.clear(); _isFallbackInProgress = false; }

function isProviderFullyFailed(p) {
    return _failedProviders.has(p) ||
        (_failedProviders.has(p+'::hls') && _failedProviders.has(p+'::embed'));
}
function isProviderFailedForType(p, t) {
    return _failedProviders.has(p) || (t && _failedProviders.has(p+'::'+t));
}
function getNextAvailableProvider(cur) {
    var list = (window._watchState && window._watchState.providers) || _PROVIDER_PRIORITY;
    var dt   = window._watchState && window._watchState._desiredStreamType;
    var idx  = list.indexOf(cur);
    for (var i = 1; i < list.length; i++) {
        var c = list[(idx + i) % list.length];
        if (isProviderFullyFailed(c)) continue;
        if (dt && isProviderFailedForType(c, dt)) continue;
        return c;
    }
    return null;
}
function markProviderFailed(p, t) {
    _failedProviders.add(t ? p + '::' + t : p);
    updateServerPillAvailability();
}
function updateServerPillAvailability() {
    document.querySelectorAll('.server-pill').forEach(function(pill) {
        var p = pill.dataset.provider, t = pill.dataset.streamType;
        var fail = isProviderFullyFailed(p) || isProviderFailedForType(p, t);
        pill.classList.toggle('unavailable', fail);
        pill.title = fail ? 'Source unavailable for this episode' : '';
    });
}
function showToast(msg, type) {
    var c = document.getElementById('toastContainer');
    if (!c) return;
    var t = document.createElement('div');
    t.style.cssText = 'pointer-events:auto;display:flex;align-items:center;gap:10px;padding:12px 18px;background:rgba(20,20,30,0.95);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.1);border-radius:12px;color:#fff;font-size:0.85rem;font-weight:500;box-shadow:0 8px 32px rgba(0,0,0,0.4);transform:translateX(120%);transition:transform 0.35s,opacity 0.3s;opacity:0;max-width:360px;';
    if (type === 'error') t.style.borderLeft = '4px solid #ef4444';
    else if (type === 'success') t.style.borderLeft = '4px solid #10b981';
    else if (type === 'info') t.style.borderLeft = '4px solid #3b82f6';
    
    t.innerHTML = '<span>' + msg + '</span>';
    c.appendChild(t);
    requestAnimationFrame(function() { t.style.transform = 'translateX(0)'; t.style.opacity = '1'; });
    setTimeout(function() {
        t.style.transform = 'translateX(120%)'; t.style.opacity = '0';
        setTimeout(function() { t.remove(); }, 400);
    }, 4000);
}

function showFallbackToast(oldP, newP) {
    var oldName = PROVIDER_DISPLAY_NAMES[oldP] || oldP;
    var newName = PROVIDER_DISPLAY_NAMES[newP] || newP;
    showToast('<strong>' + oldName + '</strong> unavailable — switching to <strong>' + newName + '</strong>', 'info');
}

function showNoSourcesMessage() {
    var pa = document.getElementById('player-area');
    if (pa) pa.innerHTML = '<div style="width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#0d0d0d;gap:12px"><span style="color:#ef4444;font-size:.95rem;font-weight:600">No streams available</span><span style="color:#64748b;font-size:.82rem">Try another server or check back later.</span></div>';
}

// ── Proxy Wrapping ────────────────────────────────────────────────
const WORKER_BASE = 'https:///p/';
function proxyUrl(url, referer) {
    if (!url || url.startsWith('blob:')) return url;
    if (url.startsWith(WORKER_BASE) || url.startsWith('https:///proxy')) return url;
    var ref = referer || '';
    var payload = url + '\0' + ref;
    var b64u = btoa(unescape(encodeURIComponent(payload))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    return WORKER_BASE + b64u;
}

// ── applyVideoSources (replaces old Vidstack version) ────────────
function applyVideoSources(data) {
    var hlsSources   = data.hls_sources   || [];
    var embedSources = data.embed_sources || [];
    var desired      = window._watchState && window._watchState._desiredStreamType;
    var useEmbed     = false;

    if      (desired === 'hls')                     useEmbed = false;
    else if (desired === 'embed' && embedSources.length) useEmbed = true;
    else if (hlsSources.length)                     useEmbed = false;
    else if (embedSources.length)                   useEmbed = true;

    var errEl = document.getElementById('errorFallbackContainer');
    if (errEl) errEl.style.display = 'none';

    if (!useEmbed && hlsSources.length) {
        var url = hlsSources[0].file || hlsSources[0].url;
        if (url) playHLS(proxyUrl(url, ''), hlsSources);
    } else if (useEmbed && embedSources.length) {
        playEmbed(embedSources[0].url);
    } else {
        showNoSourcesMessage();
    }
}
// ── fetchAndLoadSources ───────────────────────────────────────────
function fetchAndLoadSources(isAutoFallback) {
    var state   = window._watchState || {};
    var curProv = state.provider;
    var ss      = document.getElementById('serverSections');
    if (ss) ss.classList.add('loading');

    fetch('/api/watch/sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            anime_id:       state.animeId,
            episode_number: state.episodeNumber,
            language:       state.language,
            provider:       curProv
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        var hasHls   = (data.hls_sources   || []).length > 0;
        var hasEmbed = (data.embed_sources || []).length > 0;

        if (data.error || (!hasHls && !hasEmbed)) {
            markProviderFailed(curProv);
            var next = getNextAvailableProvider(curProv);
            if (next) { showFallbackToast(curProv, next); state.provider = next; _isFallbackInProgress = true; fetchAndLoadSources(true); return; }
            _isFallbackInProgress = false; showNoSourcesMessage();
            if (ss) ss.classList.remove('loading');
            return;
        }

        _isFallbackInProgress = false;
        if (data.intro !== undefined && window.WATCH_CONFIG) window.WATCH_CONFIG.intro = data.intro;
        if (data.outro !== undefined && window.WATCH_CONFIG) window.WATCH_CONFIG.outro = data.outro;
        resetWatchedFlag();
        applyVideoSources(data);

        if (ss) {
            ss.querySelectorAll('.server-pill').forEach(function(p) { p.classList.remove('active'); });
            var dt   = state._desiredStreamType;
            var type = dt || data.source_type || (hasHls ? 'hls' : 'embed');
            var act  = ss.querySelector('.server-pill[data-provider="' + curProv + '"][data-stream-type="' + type + '"]');
            if (act) act.classList.add('active');
        }
        delete state._desiredStreamType;
        if (ss) ss.classList.remove('loading');
    })
    .catch(function(err) {
        console.error('[Sources] fetch error:', err);
        markProviderFailed(curProv);
        var next = getNextAvailableProvider(curProv);
        if (next) { showFallbackToast(curProv, next); state.provider = next; _isFallbackInProgress = true; fetchAndLoadSources(true); return; }
        _isFallbackInProgress = false; showNoSourcesMessage();
        if (ss) ss.classList.remove('loading');
    });
}

// ── switchProvider / switchLanguage ───────────────────────────────
function switchProvider(provider) {
    window._watchState.provider = provider;
    _failedProviders.delete(provider);
    _isFallbackInProgress = false;
    fetchAndLoadSources();
}
window.switchProvider = switchProvider;

function switchLanguage(lang) {
    window._watchState.language = lang;
    resetFailedProviders();
    document.querySelectorAll('.lang-btn,[data-lang]').forEach(function(b) {
        var bl = b.dataset.lang || b.textContent.trim().toLowerCase();
        b.classList.toggle('active', bl === lang.toLowerCase());
    });
    document.querySelectorAll('.server-pill.unavailable').forEach(function(p) { p.classList.remove('unavailable'); });
    fetchAndLoadSources();
}

// ── Watchlist tracking ────────────────────────────────────────────
function resetWatchedFlag() { _watchedMarked = false; }

function saveWatchHistory(ct, dur) {
    var cfg = window.WATCH_CONFIG;
    if (!cfg || !cfg.animeId) return;
    var key = 'yumeHistory_' + cfg.animeId + '_ep' + cfg.episodeNumber;
    try {
        localStorage.setItem(key, JSON.stringify({
            animeId: cfg.animeId, epNum: cfg.episodeNumber,
            animeName: cfg.animeName || '', poster: cfg.poster || '',
            episodeTitle: cfg.episodeTitle || '',
            timestamp: ct, duration: dur, completed: dur > 0 && (ct/dur) >= 0.9,
            watchedAt: Date.now()
        }));
    } catch(e) {}
}

function markEpisodeWatched() {
    if (_watchedMarked || !(window.WATCH_CONFIG && window.WATCH_CONFIG.isLoggedIn)) return;
    var anilistId = window.WATCH_CONFIG.anilistId;
    var animeId   = anilistId || window.WATCH_CONFIG.animeId;
    var epNum     = window.WATCH_CONFIG.episodeNumber;
    var malId     = window.WATCH_CONFIG.malId;
    if (!animeId || !epNum) return;
    _watchedMarked = true;
    var payload = { anime_id: animeId, action: 'episodes', watched_episodes: epNum };
    if (malId) { payload.mal_id = malId; payload.sync_mal = true; }
    function doUpdate(attempt) {
        fetch('/api/watchlist/update', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload), keepalive: true })
        .then(function(r) { return r.json(); })
        .then(function(d) { if (!d.success && attempt < 2) setTimeout(function(){doUpdate(attempt+1);}, 2000); })
        .catch(function() { if (attempt < 2) setTimeout(function(){doUpdate(attempt+1);},3000); else _watchedMarked=false; });
    }
    doUpdate(1);
}

// ── Episode sidebar ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    var viewList = document.getElementById('view-list-btn');
    var viewGrid = document.getElementById('view-grid-btn');
    var list     = document.getElementById('episodeList');
    function setView(v) {
        if (list) list.setAttribute('data-view', v);
        try { localStorage.setItem('episodeView', v); } catch(e) {}
        if (viewList) viewList.classList.toggle('active', v==='list');
        if (viewGrid) viewGrid.classList.toggle('active', v==='grid');
    }
    try { setView(localStorage.getItem('episodeView') || 'grid'); } catch(e) {}
    if (viewList) viewList.addEventListener('click', function(){setView('list');});
    if (viewGrid) viewGrid.addEventListener('click', function(){setView('grid');});

    var search = document.getElementById('episodeSearch');
    if (search && list) {
        search.addEventListener('input', function(e) {
            var term = e.target.value.toLowerCase();
            list.querySelectorAll('.episode-sidebar-item').forEach(function(item) {
                item.style.display = (item.dataset.number.includes(term) || item.textContent.toLowerCase().includes(term)) ? '' : 'none';
            });
        });
    }
});

// ── Server pill clicks ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    var sections = document.getElementById('serverSections');
    if (!sections) return;
    sections.addEventListener('click', function(e) {
        var pill = e.target.closest('.server-pill');
        if (!pill || pill.disabled || pill.classList.contains('unavailable')) return;
        var streamType = pill.dataset.streamType, provider = pill.dataset.provider;
        if (!streamType || !provider) return;

        window._watchState._desiredStreamType = streamType;
        window._watchState.provider = provider;
        _isFallbackInProgress = false;
        _failedProviders.delete(provider+'::'+streamType);
        _failedProviders.delete(provider);
        try { localStorage.setItem('yumePreferredServer', provider); document.cookie='preferred_server='+provider+'; path=/; max-age=31536000'; } catch(e) {}

        sections.querySelectorAll('.server-pill').forEach(function(p){p.classList.remove('active');});
        pill.classList.add('active');
        fetchAndLoadSources();
    });
});

// ── Countdown timer ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    var countdownEl  = document.getElementById('countdown-text');
    var euContainer  = document.getElementById('eu-countdown-wrapper');
    var euDays       = document.getElementById('eu-days');
    var euHours      = document.getElementById('eu-hours');
    var euMins       = document.getElementById('eu-mins');
    var euSecs       = document.getElementById('eu-secs');
    var legacyTs     = null, euTs = null;

    if (document.getElementById('watch-countdown'))
        legacyTs = parseInt(document.getElementById('watch-countdown').getAttribute('data-timestamp'), 10);
    if (euContainer)
        euTs = parseInt(euContainer.getAttribute('data-timestamp'), 10);
    if (!legacyTs && !euTs) return;

    function pad(n) { return n < 10 ? '0'+n : n; }
    function tick() {
        var now = Date.now();
        if (countdownEl && legacyTs) {
            var jsTs = legacyTs > 9999999999 ? legacyTs : legacyTs*1000;
            var diff = jsTs - now;
            if (diff <= 0) { countdownEl.textContent = 'Aired'; }
            else {
                var d=Math.floor(diff/86400000), h=Math.floor((diff/3600000)%24),
                    m=Math.floor((diff/60000)%60), s=Math.floor((diff/1000)%60);
                countdownEl.textContent = (d?d+'d ':'')+( h||d?h+'h ':'')+m+'m '+s+'s';
            }
        }
        if (euTs && euDays && euHours && euMins && euSecs) {
            var jsTs2 = euTs > 9999999999 ? euTs : euTs*1000;
            var diff2 = jsTs2 - now;
            if (diff2 <= 0) { euDays.textContent=euHours.textContent=euMins.textContent=euSecs.textContent='00'; }
            else {
                euDays.textContent  = pad(Math.floor(diff2/86400000));
                euHours.textContent = pad(Math.floor((diff2/3600000)%24));
                euMins.textContent  = pad(Math.floor((diff2/60000)%60));
                euSecs.textContent  = pad(Math.floor((diff2/1000)%60));
            }
        }
    }
    tick(); setInterval(tick, 1000);
});

// ── DOMContentLoaded — init everything ───────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    // Init watch state
    var cfg = window.WATCH_CONFIG || {};
    window._watchState = {
        animeId:       cfg.animeId,
        episodeNumber: cfg.episodeNumber,
        language:      cfg.language,
        provider:      cfg.provider,
        providers:     cfg.providers || []
    };

    // Play initial stream from server-rendered WATCH_CONFIG
    if (cfg.videoLink && cfg.videoLink.length > 0) {
        if (cfg.sourceType === 'embed') {
            playEmbed(cfg.videoLink);
        } else {
            playHLS(cfg.videoLink, null);
        }
    } else {
        // No server-side source — try AJAX fallback immediately
        if (cfg.provider && cfg.providers && cfg.providers.length > 0) {
            markProviderFailed(cfg.provider);
            var next = getNextAvailableProvider(cfg.provider);
            if (next) {
                window._watchState.provider = next;
                _isFallbackInProgress = true;
                fetchAndLoadSources(true);
            }
        }
    }
});

// ── Report / Fix Issue Modal Logic ─────────────────────────────────────────────
window.openFixModal = function() {
    var modal = document.getElementById('fixIssueModal');
    if (!modal) return;
    
    modal.style.display = 'flex';
    // Trigger reflow for animation
    void modal.offsetWidth;
    modal.style.opacity = '1';
    var inner = modal.querySelector('div');
    if (inner) inner.style.transform = 'translateY(0)';
};

window.closeFixModal = function() {
    var modal = document.getElementById('fixIssueModal');
    if (!modal) return;
    
    modal.style.opacity = '0';
    var inner = modal.querySelector('div');
    if (inner) inner.style.transform = 'translateY(20px)';
    
    setTimeout(function() {
        modal.style.display = 'none';
    }, 200);
};

// Handle clicks for the modal
document.addEventListener('DOMContentLoaded', function() {
    var closeIcon = document.getElementById('closeFixModalIcon');
    var cancelBtn = document.getElementById('cancelFixBtn');
    var submitBtn = document.getElementById('submitFixBtn');
    var modal = document.getElementById('fixIssueModal');
    
    if (closeIcon) closeIcon.onclick = window.closeFixModal;
    if (cancelBtn) cancelBtn.onclick = window.closeFixModal;
    if (modal) {
        modal.onclick = function(e) {
            if (e.target === modal) window.closeFixModal();
        };
    }
    
    if (submitBtn) {
        submitBtn.onclick = function() {
            var state = window._watchState || {};
            
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin" style="margin-right: 5px;"></i> Fixing...';
            submitBtn.style.opacity = '0.8';
            submitBtn.style.cursor = 'not-allowed';
            
            fetch('/api/watch/clear-cache', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ anime_id: state.animeId })
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                showToast('Cache cleared! Fetching fresh stream...', 'success');
                setTimeout(function() { location.reload(); }, 800);
            })
            .catch(function() {
                showToast('Error clearing cache, please refresh manually.', 'error');
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Fix it';
                submitBtn.style.opacity = '1';
                submitBtn.style.cursor = 'pointer';
            });
        };
    }
});
