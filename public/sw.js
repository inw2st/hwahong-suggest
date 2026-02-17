// Service Worker for Push API notifications
const CACHE_NAME = 'suggestions-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

// Push 구독
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || '새 답변이 도착했어요';
  const body = data.body || '건의사항에 새로운 답변이 등록되었습니다.';
  
  event.waitUntil(
    self.registration.showNotification(title, {
      body: body,
      icon: '/assets/icon.png',
      badge: '/assets/icon.png',
      tag: 'suggestion',
      requireInteraction: true,
      vibrate: [200, 100, 200]
    })
  );
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow('/me.html')
  );
});
