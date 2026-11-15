import { defineConfig } from 'vite';
import { readFileSync } from 'node:fs';

// 构建期把 trip.json 的标题、副标题、语言写进 index.html，
// 这样分享链接的预览、搜索引擎和读屏软件在页面脚本运行之前就能拿到正确内容（运行时 shell.js 仍会再设置一遍）。
const escapeAttr = (v) => String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
function tripMeta() {
  return {
    name: 'trip-meta',
    transformIndexHtml(html) {
      let trip = {};
      try { trip = JSON.parse(readFileSync(new URL('./src/data/trip.json', import.meta.url), 'utf8')); } catch { /* 读不到就用 index.html 里的默认值 */ }
      const title = escapeAttr(trip.title || 'Paper roadbook');
      const subtitle = escapeAttr(trip.subtitle || '');
      const lang = trip.lang === 'en' ? 'en' : 'zh';
      return html
        .replace(/<html lang="[^"]*"/, `<html lang="${lang}"`)
        .replace('<title></title>', `<title>${title}</title>`)
        .replace('<meta name="description" content="">', `<meta name="description" content="${subtitle}">`)
        .replace('<meta property="og:title" content="">', `<meta property="og:title" content="${title}">`)
        .replace('<meta property="og:description" content="">', `<meta property="og:description" content="${subtitle}">`);
    },
  };
}

export default defineConfig({
  plugins: [tripMeta()],
  build: { rolldownOptions: { input: { main: 'index.html', gallery: 'gallery.html' }, output: { codeSplitting: { groups: [{ name: 'three', test: /node_modules\/three/ }] } } } },
});
