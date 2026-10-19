const CACHE='commercial-brief-v2';
const ASSETS=['./','./index.html','./icon.svg','./manifest.webmanifest'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)));self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim()});
self.addEventListener('fetch',e=>{
 const u=new URL(e.request.url);
 if(u.origin!==self.location.origin)return;
 if(u.pathname.endsWith('/data/news.json')){
   e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));return;
 }
 if(e.request.mode==='navigate'||u.pathname.endsWith('/index.html')){
   e.respondWith(fetch(e.request).then(response=>{
     if(response.ok){const copy=response.clone();e.waitUntil(caches.open(CACHE).then(c=>c.put(e.request,copy)))}
     return response;
   }).catch(()=>caches.match(e.request)));return;
 }
 e.respondWith(caches.match(e.request).then(c=>c||fetch(e.request)));
});
