# -*- coding: utf-8 -*-
"""
PC -> Phone Audio Bridge.
Lets you hear your PC on the Bluetooth earphones paired with your phone,
over the local Wi-Fi network. The PC captures its speaker output (loopback)
and streams it to the phone, which plays it on the Bluetooth earphones.
The PC needs no Bluetooth at all; the earphones stay paired with the phone.
"""
import argparse
import asyncio
import json
import math
import random
import secrets
import socket
import struct
import sys
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

WS_PORT_DEFAULT = 8001
HTTP_PORT_DEFAULT = 8000

# ---------- CLI options ----------
parser = argparse.ArgumentParser(description="PC to Phone audio bridge")
parser.add_argument("--http-port", type=int, default=HTTP_PORT_DEFAULT)
parser.add_argument("--ws-port", type=int, default=WS_PORT_DEFAULT)
parser.add_argument("--pin", type=str, default=None, help="Custom 6-digit PIN; generated randomly if omitted")
parser.add_argument("--mono", action="store_true", help="Mono audio to reduce stutter on weak networks")
parser.add_argument("--test", action="store_true", help="Network test mode without audio capture (test tone)")
args, _ = parser.parse_known_args()

HTTP_PORT = args.http_port
WS_PORT = args.ws_port
MONO = args.mono
TEST_MODE = args.test

if args.pin and args.pin.isdigit() and len(args.pin) == 6:
    PIN = args.pin
else:
    PIN = f"{random.randint(100000, 999999)}"

# ---------- Network addresses ----------
def get_lan_ips():
    ips = set()
    try:
        # Most accurate: the outbound interface address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips) or ["127.0.0.1"]

LAN_IPS = get_lan_ips()
PHONE_URLS = [f"http://{ip}:{HTTP_PORT}/?code={PIN}" for ip in LAN_IPS if not ip.startswith("127.")]

# ---------- Streaming state ----------
SAMPLE_RATE = 48000
CHANNELS = 1 if MONO else 2
clients_queues = set()
clients_queues_lock = threading.Lock()
connected_count = 0
connected_lock = threading.Lock()
main_loop = None
last_error = None

# ---------- Background control (for the desktop GUI) ----------
stop_flag = threading.Event()
http_server = None
_ws_server = None
_ws_stop_async = None

def new_session(pin=None):
    """Fresh PIN + URLs + QR code. Called on every start."""
    global PIN, PHONE_URLS
    if pin and str(pin).isdigit() and len(str(pin)) == 6:
        PIN = str(pin)
    else:
        PIN = f"{random.randint(100000, 999999)}"
    ips = get_lan_ips()
    PHONE_URLS = [f"http://{ip}:{HTTP_PORT}/?code={PIN}" for ip in ips if not ip.startswith("127.")]
    fail_count.clear()
    blocked_until.clear()
    build_qr()
    return PIN

# Simple brute-force protection
fail_count = defaultdict(int)
blocked_until = {}

def is_blocked(ip):
    return time.time() < blocked_until.get(ip, 0)

def register_fail(ip):
    fail_count[ip] += 1
    if fail_count[ip] >= 8:
        blocked_until[ip] = time.time() + 60
        fail_count[ip] = 0
        print(f"[security] Temporarily blocking {ip} for a minute after repeated wrong attempts.")

def check_code(code):
    return secrets.compare_digest(str(code or ""), PIN)

# ---------- Phone page (self-contained, no internet needed) ----------
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ar" dir="rtl" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark light">
<title>PC Audio to Phone</title>
<script>try{document.documentElement.dataset.theme=localStorage.getItem('pa_theme')||'dark';var L='';try{L=localStorage.getItem('pa_lang')||'';}catch(e){}if(!L){var n=((navigator.language||'en')+'').slice(0,2).toLowerCase();L=(n==='ar'||n==='fr'||n==='es')?n:'en';}if(!{ar:1,en:1,fr:1,es:1}[L])L='en';document.documentElement.lang=L;document.documentElement.dir=L==='ar'?'rtl':'ltr';}catch(e){}</script>
<style>
*{box-sizing:border-box}
:root{--bg:#0a0a0a;--surface:#141414;--raised:#1e1e1e;--border:#2a2a2a;--text:#ededed;--muted:#a3a3a3;--ok:#22c55e;--err:#ef4444}
[data-theme="light"]{--bg:#fafafa;--surface:#ffffff;--raised:#f0f0f0;--border:#e3e3e3;--text:#111111;--muted:#5b5b5b;--ok:#15803d;--err:#dc2626}
html{-webkit-text-size-adjust:100%}
body{margin:0;font-family:system-ui,'Segoe UI',Tahoma,Arial,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:16px;line-height:1.6}
.topbar{width:100%;max-width:420px;display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:12px}
.icon{width:40px;height:40px;border-radius:10px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-size:18px;cursor:pointer}
.seg{display:flex;background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:3px;gap:2px}
.seg button{border:0;background:transparent;color:var(--muted);font-size:12px;font-weight:700;border-radius:999px;padding:7px 10px;cursor:pointer;font-family:inherit}
.seg button.on{background:var(--text);color:var(--bg)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:24px;width:100%;max-width:420px}
h1{font-size:21px;margin:0 0 4px;text-wrap:balance}
.sub{color:var(--muted);font-size:13.5px;margin:0 0 12px}
.steps{list-style:none;margin:0 0 10px;padding:0;display:flex;flex-direction:column;gap:10px}
.steps li{display:flex;gap:10px;align-items:flex-start;background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:9px 12px;font-size:13px}
.steps b{font-family:ui-monospace,Consolas,monospace;background:var(--raised);border:1px solid var(--border);border-radius:6px;min-width:24px;height:24px;display:inline-flex;align-items:center;justify-content:center;font-size:12px}
.steps span{color:var(--muted);display:block;font-size:12px}
.status{border-radius:10px;padding:12px;margin:14px 0;font-size:14px;font-weight:700;border:1px solid var(--border);background:var(--raised)}
.status.ok{color:var(--ok);border-color:var(--ok)}
.status.err{color:var(--err);border-color:var(--err)}
#code{font-size:24px;text-align:center;letter-spacing:8px;text-indent:8px;border-radius:10px;border:1px solid var(--border);background:var(--bg);color:var(--text);padding:12px;width:100%;margin:4px 0 8px;font-family:ui-monospace,Consolas,monospace}
.modes{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:10px 0}
.mode{border:1px solid var(--border);background:var(--bg);color:var(--text);border-radius:10px;padding:12px;min-height:72px;cursor:pointer;text-align:start;font-family:inherit}
.mode b{display:block;font-size:14px}
.mode span{font-size:12px;color:var(--muted)}
.mode.sel{border-color:var(--text);background:var(--raised)}
.mode.sel b::after{content:" ✓"}
#btnStart,#btnStop{font-size:18px;font-weight:700;border-radius:10px;padding:16px;width:100%;cursor:pointer;margin:8px 0;border:1px solid var(--border);font-family:inherit}
#btnStart{background:var(--text);color:var(--bg)}
#btnStart:disabled{opacity:.45;cursor:default}
#btnStop{background:transparent;color:var(--text)}
#bgAudio{width:100%;display:none;margin:8px 0}
.lbl{font-size:13px;color:var(--muted);display:block;margin-top:6px}
input[type=range]{width:100%;accent-color:var(--text);margin:6px 0}
.row{display:flex;align-items:center;justify-content:space-between;background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:9px 13px;margin:6px 0;font-size:13.5px}
.tips{margin-top:12px;font-size:12.5px;color:var(--muted);display:flex;flex-direction:column;gap:6px}
#pcBox{display:none}
.qr{width:200px;height:200px;background:#fff;border-radius:10px;margin:10px auto;display:block;padding:8px}
.big{font-size:38px;font-weight:800;letter-spacing:8px;text-indent:8px;text-align:center;font-family:ui-monospace,Consolas,monospace;margin:4px 0}
.cap{font-size:13px;color:var(--muted);text-align:center}
button:focus-visible,input:focus-visible{outline:2px solid var(--text);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>
</head>
<body>
<div class="topbar">
<div class="seg" id="langSeg"><button data-lang="ar">ع</button><button data-lang="en">EN</button><button data-lang="fr">FR</button><button data-lang="es">ES</button></div>
<button id="themeB" class="icon" aria-label="theme">&#9790;</button>
</div>
<div class="card" id="playerBox">
<h1 data-i="title"></h1>
<p class="sub" data-i="subtitle"></p>
<ol class="steps">
<li><b>1</b><div><div data-i="step1t"></div><span data-i="step1d"></span></div></li>
<li><b>2</b><div><div data-i="step2t"></div><span data-i="step2d"></span></div></li>
<li><b>3</b><div><div data-i="step3t"></div><span data-i="step3d"></span></div></li>
</ol>
<div class="status" id="status"></div>
<input id="code" inputmode="numeric" maxlength="6" placeholder="••••••" aria-label="code">
<div class="modes">
<button id="mFast" class="mode" onclick="setMode('fast')"><b data-i="mode_fast"></b><span data-i="mode_fast_d"></span></button>
<button id="mBg" class="mode" onclick="setMode('bg')"><b data-i="mode_bg"></b><span data-i="mode_bg_d"></span></button>
</div>
<button id="btnStart"></button>
<button id="btnStop"></button>
<audio id="bgAudio" controls preload="none"></audio>
<label class="lbl" data-i="volume"></label>
<input type="range" id="vol" min="0" max="100" value="100">
<div class="row"><span data-i="latency"></span><b id="lat">—</b></div>
<div class="row"><span data-i="state"></span><b id="st"></b></div>
<div class="tips"><div data-i="tip_bt"></div><div data-i="tip_vol"></div></div>
</div>

<div class="card" id="pcBox">
<h1 data-i="pctitle"></h1>
<p class="sub" data-i="pcsub"></p>
<div class="cap" data-i="pin_cap"></div>
<div class="big" id="pcPin">••••••</div>
<img class="qr" id="pcQr" alt="QR">
<div id="pcUrls" class="cap" style="line-height:2"></div>
<div class="row"><span data-i="clients"></span><b id="pcClients">0</b></div>
<div class="tips"><div data-i="tip_fw"></div></div>
</div>

<script>
const $=id=>document.getElementById(id);
const S={
ar:{title:"صوت الحاسوب إلى الهاتف",subtitle:"استمع لصوت حاسوبك من سماعات البلوتوث المربوطة بهاتفك.",step1t:"نفس الواي فاي",step1d:"الهاتف والحاسوب على نفس الشبكة",step2t:"اربط السماعات",step2d:"البلوتوث مربوط بالهاتف",step3t:"أدخل الرمز وشغّل",step3d:"امسح QR ثم اضغط تشغيل",waiting:"○ بانتظار التشغيل…",connecting:"…جارٍ الاتصال",connected_wait:"متصل — بانتظار الصوت",running:"● يعمل الآن — الصوت في سماعاتك",stopped_hint:"متوقف. اضغط تشغيل للعودة.",locked_hint:"! الشاشة مقفلة؟ بدّل إلى وضع الخلفية",back_hint:"عُدت — إن توقف الصوت أعد التشغيل",conn_lost:"! انقطع الاتصال — تحقق من الواي فاي والرمز",err_conn:"! تعذر الاتصال — تأكد من نفس شبكة الواي فاي",err_code:"أدخل الرمز المكوّن من 6 أرقام",err_retry:"تعذر التشغيل — حاول مجدداً",bg_now:"● الخلفية تعمل — يمكنك قفل الشاشة",fast_ready:"تم الاتصال — شغّل أي صوت في الحاسوب",mode_fast:"مباشر",mode_fast_d:"تأخير ~0.1 ثانية",mode_bg:"خلفية",mode_bg_d:"يعمل مع قفل الشاشة",start:"▶ تشغيل الصوت",stop:"■ إيقاف",volume:"مستوى الصوت",latency:"التأخير",state:"الحالة",connected:"يعمل",disconnected:"غير متصل",bg_tag:"خلفية",connecting2:"يتصل…",sec:" ث",tip_bt:"لا حاجة لصلاحية بلوتوث في المتصفح.",tip_vol:"ارفع صوت الحاسوب والهاتف والصفحة معاً.",pctitle:"لوحة الحاسوب",pcsub:"امسح الرمز من الهاتف — نفس شبكة الواي فاي",pin_cap:"رمز الدخول (يتغير كل تشغيل)",clients:"هواتف متصلة الآن",tip_fw:"عند طلب الجدار الناري اختر الشبكات الخاصة فقط.",appoff:"شغّل التطبيق أولاً"},
en:{title:"PC Audio to Phone",subtitle:"Hear your PC on the Bluetooth earphones paired with your phone.",step1t:"Same Wi-Fi",step1d:"Phone and PC on the same network",step2t:"Pair the buds",step2d:"Bluetooth paired with the phone",step3t:"Enter code & play",step3d:"Scan the QR, then press play",waiting:"○ Waiting to start…",connecting:"Connecting…",connected_wait:"Connected — waiting for audio",running:"● Playing — audio on your earphones",stopped_hint:"Stopped. Press play to resume.",locked_hint:"! Screen locked? Switch to Background mode",back_hint:"Welcome back — replay if silent",conn_lost:"! Disconnected — check Wi-Fi and code",err_conn:"! Can't connect — same Wi-Fi required",err_code:"Enter the 6-digit code",err_retry:"Couldn't start — try again",bg_now:"● Background on — you can lock the screen",fast_ready:"Connected — play anything on the PC",mode_fast:"Instant",mode_fast_d:"~0.1s delay",mode_bg:"Background",mode_bg_d:"Works with locked screen",start:"▶ Play audio",stop:"■ Stop",volume:"Volume",latency:"Delay",state:"Status",connected:"Playing",disconnected:"Offline",bg_tag:"Background",connecting2:"Connecting…",sec:" s",tip_bt:"No Bluetooth permission needed in the browser.",tip_vol:"Turn up PC, phone and page volume together.",pctitle:"Computer panel",pcsub:"Scan the code from your phone — same Wi-Fi",pin_cap:"Access code (new each run)",clients:"Phones connected",tip_fw:"If the firewall asks, allow private networks only.",appoff:"Start the app first"},
fr:{title:"Audio du PC",subtitle:"Écoutez votre PC sur les écouteurs associés à votre téléphone.",step1t:"Même Wi-Fi",step1d:"Téléphone et PC sur le même réseau",step2t:"Associez les écouteurs",step2d:"Bluetooth associé au téléphone",step3t:"Code et lecture",step3d:"Scannez le QR, puis lecture",waiting:"○ En attente…",connecting:"Connexion…",connected_wait:"Connecté — en attente d'audio",running:"● Lecture — audio sur vos écouteurs",stopped_hint:"Arrêté. Appuyez sur lecture.",locked_hint:"! Écran verrouillé ? Passez en Arrière-plan",back_hint:"Bon retour — relancez si silencieux",conn_lost:"! Déconnecté — vérifiez Wi-Fi et code",err_conn:"! Connexion impossible — même Wi-Fi requis",err_code:"Saisissez le code à 6 chiffres",err_retry:"Échec — réessayez",bg_now:"● Arrière-plan actif — verrouillez l'écran",fast_ready:"Connecté — lancez un son sur le PC",mode_fast:"Direct",mode_fast_d:"Retard ~0,1 s",mode_bg:"Arrière-plan",mode_bg_d:"Écran verrouillé OK",start:"▶ Lecture",stop:"■ Arrêter",volume:"Volume",latency:"Retard",state:"État",connected:"Lecture",disconnected:"Hors ligne",bg_tag:"Arrière-plan",connecting2:"Connexion…",sec:" s",tip_bt:"Aucune autorisation Bluetooth requise.",tip_vol:"Montez PC, téléphone et page ensemble.",pctitle:"Panneau de l'ordinateur",pcsub:"Scannez depuis le téléphone — même Wi-Fi",pin_cap:"Code d'accès (nouveau à chaque fois)",clients:"Téléphones connectés",tip_fw:"Si le pare-feu demande, autorisez les réseaux privés.",appoff:"Démarrez d'abord l'application"},
es:{title:"Audio del PC",subtitle:"Escucha tu PC en los auriculares vinculados a tu teléfono.",step1t:"Mismo Wi-Fi",step1d:"Teléfono y PC en la misma red",step2t:"Vincula los auriculares",step2d:"Bluetooth vinculado al teléfono",step3t:"Código y reproducir",step3d:"Escanea el QR y reproduce",waiting:"○ Esperando iniciar…",connecting:"Conectando…",connected_wait:"Conectado — esperando audio",running:"● Sonando — audio en tus auriculares",stopped_hint:"Detenido. Pulsa reproducir.",locked_hint:"! ¿Pantalla bloqueada? Cambia a Fondo",back_hint:"Bienvenido — repite si no hay sonido",conn_lost:"! Desconectado — revisa Wi-Fi y código",err_conn:"! Sin conexión — se requiere el mismo Wi-Fi",err_code:"Introduce el código de 6 dígitos",err_retry:"No se pudo iniciar — reintenta",bg_now:"● Fondo activo — puedes bloquear la pantalla",fast_ready:"Conectado — reproduce algo en el PC",mode_fast:"Directo",mode_fast_d:"Retardo ~0,1 s",mode_bg:"Fondo",mode_bg_d:"Funciona bloqueado",start:"▶ Reproducir",stop:"■ Detener",volume:"Volumen",latency:"Retardo",state:"Estado",connected:"Sonando",disconnected:"Desconectado",bg_tag:"Fondo",connecting2:"Conectando…",sec:" s",tip_bt:"No se necesita permiso de Bluetooth.",tip_vol:"Sube el volumen del PC, teléfono y página.",pctitle:"Panel del equipo",pcsub:"Escanea desde el teléfono — mismo Wi-Fi",pin_cap:"Código (nuevo cada vez)",clients:"Teléfonos conectados",tip_fw:"Si el firewall pregunta, permite solo redes privadas.",appoff:"Inicia primero la aplicación"}
};
let lang=document.documentElement.lang||'en';
if(!S[lang])lang='en';
function t(k){return (S[lang]&&S[lang][k])||S.en[k]||k;}
function applyLang(){
 document.documentElement.lang=lang;
 document.documentElement.dir=lang==='ar'?'rtl':'ltr';
 document.querySelectorAll('[data-i]').forEach(e=>{e.textContent=t(e.getAttribute('data-i'));});
 document.querySelectorAll('#langSeg button').forEach(b=>{b.classList.toggle('on',b.dataset.lang===lang);});
 try{localStorage.setItem('pa_lang',lang);}catch(e){}
 if(!running)setStatus(t('waiting'),'');
 $('st').textContent=t('disconnected');
 $('btnStart').textContent=t('start');
 $('btnStop').textContent=t('stop');
}
function setLang(l){lang=l;applyLang();}
function setTheme(th){document.documentElement.dataset.theme=th;try{localStorage.setItem('pa_theme',th);}catch(e){}$('themeB').innerHTML=th==='dark'?'&#9790;':'&#9788;';}
const params=new URLSearchParams(location.search);
if(params.get('code')){$('code').value=params.get('code');}
const isPC=['localhost','127.0.0.1'].includes(location.hostname);
if(isPC){$('playerBox').style.display='none';$('pcBox').style.display='block';loadPC();}
const WS_PORT=__WS_PORT__;
let ws=null,ctx=null,gain=null,nextTime=0,running=false,helloRate=48000,helloCh=2,chunkCount=0,lastRx=0,mode='fast',wl=null;
function setMode(m){mode=m;stopAll();
 $('mFast').classList.toggle('sel',m==='fast');
 $('mBg').classList.toggle('sel',m==='bg');
 $('bgAudio').style.display=m==='bg'?'block':'none';
}
async function keepAwake(){try{if('wakeLock' in navigator){wl=await navigator.wakeLock.request('screen');}}catch(e){}}
function startBg(code){
 stopAll();
 const a=$('bgAudio');a.src='http://'+location.host+'/stream.mp3?code='+code;
 a.play().then(()=>{running=true;$('btnStart').disabled=true;$('st').textContent=t('connected')+' ('+t('bg_tag')+')';
  setStatus(t('bg_now'),'ok');keepAwake();
  try{if('mediaSession' in navigator){navigator.mediaSession.metadata=new MediaMetadata({title:t('title'),artist:'PC-Phone-Audio',album:'live'});}}catch(e){}
 }).catch(e=>{setStatus(t('err_retry'),'err');});
}
function setStatus(x,c){const s=$('status');s.textContent=x;s.className='status '+c;}
async function loadPC(){
 try{const r=await fetch('/info');const j=await r.json();
 $('pcPin').textContent=j.pin;
 $('pcQr').src=j.qr;
 $('pcUrls').innerHTML=j.urls.map(u=>'<div dir="ltr"><a href="'+u+'">'+u+'</a></div>').join('');
 const tick=async()=>{try{const r2=await fetch('/info');const j2=await r2.json();$('pcClients').textContent=j2.clients;}catch(e){}setTimeout(tick,2000);};tick();
 }catch(e){$('pcPin').textContent=t('appoff');}
}
$('vol').oninput=()=>{if(gain&&ctx)gain.gain.value=$('vol').value/100;};
$('themeB').onclick=()=>{setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');};
document.querySelectorAll('#langSeg button').forEach(b=>{b.onclick=()=>setLang(b.dataset.lang);});
$('btnStart').onclick=async()=>{
 let code=$('code').value.trim();
 if(!/^[0-9]{6}$/.test(code)){setStatus(t('err_code'),'err');return;}
 if(mode==='bg'){startBg(code);return;}
 try{
  setStatus(t('connecting'),'');$('st').textContent=t('connecting2');
  ws=new WebSocket('ws://'+location.hostname+':'+WS_PORT+'/ws?code='+code);
  ws.binaryType='arraybuffer';
  ws.onopen=()=>{$('st').textContent=t('connected_wait');};
  ws.onclose=()=>{if(running){setStatus(t('conn_lost'),'err');$('st').textContent=t('disconnected');}running=false;};
  ws.onerror=()=>{setStatus(t('err_conn'),'err');};
  ws.onmessage=(ev)=>{
   if(typeof ev.data==='string'){
    try{const m=JSON.parse(ev.data);if(m.type==='hello'){helloRate=m.sampleRate;helloCh=m.channels;startCtx();}}catch(e){}
    return;
   }
   if(!ctx||!running)return;
   lastRx=performance.now();
   const bytes=new Int16Array(ev.data);
   const frames=bytes.length/helloCh;
   const buf=ctx.createBuffer(helloCh,frames,ctx.sampleRate);
   for(let c=0;c<helloCh;c++){
    const d=buf.getChannelData(c);
    for(let i=0;i<frames;i++){d[i]=bytes[i*helloCh+c]/32768;}
   }
   const src=ctx.createBufferSource();src.buffer=buf;src.connect(gain);
   if(nextTime<ctx.currentTime)nextTime=ctx.currentTime+0.03;
   src.start(nextTime);nextTime+=buf.duration;
   chunkCount++;
   const lat=((nextTime-ctx.currentTime)*1000)|0;
   $('lat').textContent=(lat/1000).toFixed(2)+t('sec');
   if(chunkCount===5){setStatus(t('running'),'ok');$('st').textContent=t('connected');}
  };
 }catch(e){setStatus(t('err_retry'),'err');}
};
function startCtx(){
 if(ctx)try{ctx.close()}catch(e){}
 ctx=new (window.AudioContext||window.webkitAudioContext)({sampleRate:helloRate,latencyHint:'interactive'});
 gain=ctx.createGain();gain.gain.value=$('vol').value/100;gain.connect(ctx.destination);
 ctx.resume();nextTime=ctx.currentTime+0.06;running=true;chunkCount=0;keepAwake();
 $('btnStart').disabled=true;setStatus(t('fast_ready'),'ok');
}
function stopAll(){running=false;try{ws&&ws.close()}catch(e){}ws=null;try{ctx&&ctx.close()}catch(e){}ctx=null;
 try{const a=$('bgAudio');a.pause();a.removeAttribute('src');a.load();}catch(e){}
 $('btnStart').disabled=false;$('st').textContent=t('disconnected');$('lat').textContent='—';}
$('btnStop').onclick=()=>{stopAll();setStatus(t('stopped_hint'),'');};
setTheme(document.documentElement.dataset.theme||'dark');
applyLang();
setMode('fast');
document.addEventListener('visibilitychange',async()=>{
 if(document.visibilityState==='visible'){
  keepAwake();
  if(running&&mode==='fast'){
   if(ctx&&ctx.state==='suspended'){try{await ctx.resume();}catch(e){}}
   if(performance.now()-lastRx<3000){setStatus(t('running'),'ok');}
   else{setStatus(t('back_hint'),'');}
  }
 }else{
  if(running&&mode==='fast'){setStatus(t('locked_hint'),'err');}
 }
});
</script>
</body>
</html>
""".replace("__WS_PORT__", str(WS_PORT))

# ---------- HTTP server ----------
qr_data_url = ""
qr_png_bytes = b""

def build_qr():
    global qr_data_url, qr_png_bytes
    if not PHONE_URLS:
        return
    import base64, io
    try:
        import qrcode
        img = qrcode.make(PHONE_URLS[0])
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_png_bytes = buf.getvalue()
        qr_data_url = "data:image/png;base64," + base64.b64encode(qr_png_bytes).decode()
    except Exception as e:
        print(f"[warn] QR generation failed (pip install qrcode pillow): {e}")

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def _send(self, data: bytes, ctype="text/html; charset=utf-8", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        u = urlparse(self.path)
        client = self.client_address[0]
        if u.path == "/stream.mp3":
            return self._serve_mp3(u)
        if u.path in ("/qr.png", "/qr"):
            if qr_png_bytes:
                return self._send(qr_png_bytes, "image/png")
            return self._send(b"no qr", "text/plain", 404)
        if u.path == "/info":
            # Sensitive info (the PIN) — local PC dashboard only
            if client not in ("127.0.0.1", "::1"):
                return self._send(b"forbidden", "text/plain", 403)
            import base64
            with connected_lock:
                n = connected_count
            info = {"pin": PIN, "urls": PHONE_URLS, "qr": qr_data_url,
                    "http_port": HTTP_PORT, "ws_port": WS_PORT, "clients": n,
                    "sample_rate": SAMPLE_RATE, "channels": CHANNELS}
            return self._send(json.dumps(info).encode(), "application/json")
        if u.path == "/health":
            return self._send(b"ok", "text/plain")
        return self._send(HTML_TEMPLATE.encode("utf-8"))

    def _serve_mp3(self, u):
        import queue as _q
        code = (parse_qs(u.query).get("code", [""])[0])
        if not check_code(code):
            return self._send(b"bad code", "text/plain", 403)
        if not MP3_AVAILABLE:
            return self._send(b"mp3 encoder missing", "text/plain", 501)
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("icy-name", "PC Audio")
        self.end_headers()
        q = _q.Queue(maxsize=50)
        with mp3_queues_lock:
            mp3_queues.add(q)
        try:
            pending = b""
            first = True
            while not stop_flag.is_set():
                try:
                    data = pending + q.get(timeout=3)
                    pending = b""
                except Exception:
                    continue
                if first:
                    # Drop any header bytes before the first MP3 frame (some players are picky)
                    idx = data.find(b"\xff\xfb")
                    if idx < 0:
                        pending = data[-1:]
                        continue
                    data = data[idx:]
                    first = False
                try:
                    self.wfile.write(data)
                    self.wfile.flush()
                except Exception:
                    break
        finally:
            with mp3_queues_lock:
                mp3_queues.discard(q)

def _is_busy(e):
    """True when an OSError means 'address already in use' on any platform."""
    if getattr(e, "errno", None) in (98, 10048):
        return True
    if getattr(e, "winerror", None) == 10048:
        return True
    msg = str(e).lower()
    return "in use" in msg or "only one usage" in msg


def run_http():
    global http_server, last_error
    try:
        http_server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    except OSError as e:
        last_error = "busy" if _is_busy(e) else str(e)
        print(f"[error] HTTP server failed: {e}")
        return
    print(f"[http] Listening on port {HTTP_PORT}")
    try:
        http_server.serve_forever()
    finally:
        try:
            http_server.server_close()
        except Exception:
            pass

# ---------- System audio capture (loopback) ----------
audio_conf = {"rate": 48000, "channels": CHANNELS, "ok": False}

# ---------- MP3 stream for background mode (survives screen lock) ----------
try:
    import lameenc
    MP3_AVAILABLE = True
except ImportError:
    MP3_AVAILABLE = False
mp3_queues = set()
mp3_queues_lock = threading.Lock()
mp3_encoder = None
mp3_enc_params = (None, None)

def mp3_push(pcm: bytes, rate: int, ch: int):
    """Encode a PCM chunk to MP3 and broadcast it to background-mode listeners."""
    global mp3_encoder, mp3_enc_params
    if not MP3_AVAILABLE or not pcm:
        return
    try:
        if mp3_encoder is None or mp3_enc_params != (rate, ch):
            enc = lameenc.Encoder()
            enc.set_bit_rate(128)
            enc.set_in_sample_rate(rate)
            enc.set_channels(ch)
            enc.set_quality(2)
            mp3_encoder = enc
            mp3_enc_params = (rate, ch)
        data = mp3_encoder.encode(pcm)
        if not data:
            return
        with mp3_queues_lock:
            targets = list(mp3_queues)
        for q in targets:
            try:
                q.put_nowait(data)
            except Exception:
                pass
            try:
                while q.qsize() > 40:
                    try:
                        q.get_nowait()
                    except Exception:
                        break
            except Exception:
                pass
    except Exception:
        pass

def capture_loop():
    """Capture whatever is playing on the PC and send it to all connected phones."""
    global SAMPLE_RATE
    if TEST_MODE:
        print("[audio] Test mode: test tone instead of system sound.")
        audio_conf["rate"] = 48000; audio_conf["ok"] = True
        t = 0
        while not stop_flag.is_set():
            frames = 480
            buf = bytearray()
            for i in range(frames):
                v = int(12000 * math.sin(2 * math.pi * 440 * (t + i) / 48000))
                if CHANNELS == 2:
                    buf += struct.pack("<hh", v, v)
                else:
                    buf += struct.pack("<h", v)
            t += frames
            data = bytes(buf)
            push_to_clients(data)
            mp3_push(data, 48000, CHANNELS)
            time.sleep(frames / 48000)
        return
    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        print("[error] pyaudiowpatch is not installed. Run: pip install pyaudiowpatch")
        print("[hint] Meanwhile try: python server.py --test to test the network with a tone.")
        return
    try:
        p = pyaudio.PyAudio()
    except Exception as e:
        print(f"[error] Could not open the audio system: {e}")
        return
    try:
        try:
            wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            print("[error] WASAPI is unavailable. This app targets Windows 10/11.")
            return
        dev = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
        if not dev.get("isLoopbackDevice"):
            for lb in p.get_loopback_device_info_generator():
                if dev["name"] in lb["name"]:
                    dev = lb
                    break
        rate = int(dev["defaultSampleRate"])
        ch = min(2, int(dev["maxInputChannels"])) if not MONO else 1
        out_ch = 1 if (MONO and ch == 2) else ch
        audio_conf["rate"] = rate; audio_conf["channels"] = out_ch; audio_conf["ok"] = True
        SAMPLE_RATE = rate
        print(f"[audio] Capturing from: {dev['name']} | {rate}Hz | {'stereo' if ch==2 else 'mono'}")
        print("[audio] Play anything on the PC — after pressing play on the phone you will hear it.")
        stream = p.open(format=pyaudio.paInt16, channels=ch, rate=rate,
                        input=True, input_device_index=dev["index"],
                        frames_per_buffer=480)
        try:
            while not stop_flag.is_set():
                try:
                    data = stream.read(480, exception_on_overflow=False)
                except Exception:
                    continue
                if MONO and ch == 2:
                    # Fast stereo-to-mono downmix
                    n = len(data) // 4
                    raw = struct.unpack(f"<{n*2}h", data)
                    mono = [(raw[i*2]//2 + raw[i*2+1]//2) for i in range(n)]
                    data = struct.pack(f"<{n}h", *mono)
                push_to_clients(data)
                mp3_push(data, rate, out_ch)
        finally:
            try:
                stream.stop_stream()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
            try:
                p.terminate()
            except Exception:
                pass
    except Exception as e:
        print(f"[error] Capture failed: {e}")
        print("Make sure the default PC playback device works, then restart.")

def push_to_clients(data: bytes):
    if main_loop is None:
        return
    with clients_queues_lock:
        targets = list(clients_queues)
    for q in targets:
        try:
            main_loop.call_soon_threadsafe(q.put_nowait, data)
        except Exception:
            pass
    # Drop stale chunks on congestion (prevents delay buildup)
    for q in targets:
        try:
            while q.qsize() > 4:
                try:
                    q.get_nowait()
                except Exception:
                    break
        except Exception:
            pass

# ---------- WebSocket server ----------
async def ws_handler(ws, path=None):
    global connected_count
    # Compatible with old and new websockets versions
    try:
        req_path = getattr(getattr(ws, "request", None), "path", None) or (path or "")
    except Exception:
        req_path = path or ""
    qs = parse_qs(urlparse(req_path).query)
    code = (qs.get("code", [""])[0])
    try:
        ip = ws.remote_address[0] if ws.remote_address else "?"
    except Exception:
        ip = "?"
    if is_blocked(ip):
        try:
            await ws.close(1008, "temporarily blocked")
        except Exception:
            pass
        return
    if not check_code(code):
        register_fail(ip)
        try:
            await ws.send(json.dumps({"type": "error", "msg": "wrong code"}))
            await ws.close(1008, "wrong code")
        except Exception:
            pass
        print(f"[security] Wrong-code attempt from {ip}")
        return
    q: asyncio.Queue = asyncio.Queue(maxsize=6)
    with clients_queues_lock:
        clients_queues.add(q)
    with connected_lock:
        connected_count += 1
    print(f"[ws] Phone connected from {ip} (total: {connected_count})")
    try:
        rate = audio_conf.get("rate", 48000)
        ch = audio_conf.get("channels", CHANNELS)
        await ws.send(json.dumps({"type": "hello", "sampleRate": rate, "channels": ch}))
        while True:
            data = await q.get()
            try:
                await ws.send(data)
            except Exception:
                break
    except Exception:
        pass
    finally:
        with clients_queues_lock:
            clients_queues.discard(q)
        with connected_lock:
            connected_count -= 1
        print(f"[ws] Phone disconnected {ip} (total: {connected_count})")

async def run_ws():
    global _ws_server, _ws_stop_async
    import websockets
    print(f"[ws] Audio on port {WS_PORT}")
    # LAN only — never forward this port on the router
    async with websockets.serve(ws_handler, "0.0.0.0", WS_PORT, max_size=2**22, ping_interval=15, ping_timeout=10) as srv:
        _ws_server = srv
        _ws_stop_async = asyncio.Event()
        await _ws_stop_async.wait()

def _ws_thread_fn():
    global main_loop, last_error
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main_loop = loop
    try:
        loop.run_until_complete(run_ws())
    except OSError as e:
        last_error = "busy" if _is_busy(e) else str(e)
        print(f"[error] WS server failed: {e}")
    except Exception:
        pass
    finally:
        try:
            loop.close()
        except Exception:
            pass

def start_background(open_browser=False):
    """Run the server on background threads (for the GUI or the CLI)."""
    global last_error
    last_error = None
    stop_flag.clear()
    build_qr()
    threading.Thread(target=run_http, daemon=True).start()
    threading.Thread(target=capture_loop, daemon=True).start()
    if open_browser:
        try:
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{HTTP_PORT}/")
        except Exception:
            pass
    threading.Thread(target=_ws_thread_fn, daemon=True).start()

def stop_background():
    """Stop the background server."""
    global main_loop, http_server
    stop_flag.set()
    try:
        if http_server is not None:
            http_server.shutdown()
            http_server = None
    except Exception:
        pass
    try:
        if main_loop is not None and _ws_stop_async is not None:
            main_loop.call_soon_threadsafe(_ws_stop_async.set)
    except Exception:
        pass
    main_loop = None

def main():
    build_qr()
    print("=" * 55)
    print("  PC audio -> Phone -> Bluetooth earphones")
    print("=" * 55)
    print(f"  PIN (6 digits, fresh every run): {PIN}")
    print(f"  PC dashboard: http://127.0.0.1:{HTTP_PORT}/")
    if PHONE_URLS:
        print("  Open on the phone (same Wi-Fi):")
        for u in PHONE_URLS:
            print(f"    {u}")
    else:
        print("  No local IP found! Check the Wi-Fi connection.")
    print("  Steps: pair buds to phone > open link > enter PIN > play")
    print("  Stop: Ctrl+C")
    print("=" * 55)
    start_background(open_browser=True)
    try:
        while not stop_flag.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped.")
        stop_background()

if __name__ == "__main__":
    main()
