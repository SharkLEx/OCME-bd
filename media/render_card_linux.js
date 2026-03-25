#!/usr/bin/env node
/**
 * render_card.js — Renderiza e envia um card específico ao Discord
 * Versão Linux/VPS — usa Playwright instalado globalmente (npm install -g playwright)
 *
 * Uso:
 *   node render_card.js token-bd          # grava + envia para o webhook do canal
 *   node render_card.js all               # todos os 8 cards
 *   node render_card.js token-bd --no-send  # só grava (bot Discord)
 *
 * Requer:
 *   - card_server.py rodando em localhost:8766
 *   - npm install -g playwright && npx playwright install chromium
 */

let chromium;
try {
  chromium = require('playwright').chromium;
} catch(e) {
  try {
    chromium = require('/usr/local/lib/node_modules/playwright').chromium;
  } catch(e2) {
    console.error('Playwright nao encontrado. Instale: npm install -g playwright && npx playwright install chromium');
    process.exit(1);
  }
}

const fs    = require('fs');
const https = require('https');
const path  = require('path');

const BASE_URL    = 'http://localhost:8766';
const OUTPUT_DIR  = path.join(__dirname, 'output', 'videos');
const ENV_PATH    = '/app/.env';
const RECORD_MS   = 5000;
const WAIT_BEFORE = 800;

// ── CARDS ─────────────────────────────────────────────────────────────────────

const CARDS = {
  'webdex-onchain':   { file: 'canal-webdex-onchain.html',   wh: 'DISCORD_WEBHOOK_ONCHAIN',    emoji: 'onchain',   canal: '#webdex-on-chain',   color: 0x00D4FF },
  'token-bd':         { file: 'canal-token-bd.html',         wh: 'DISCORD_WEBHOOK_TOKEN_BD',   emoji: 'token',     canal: '#token-bd',           color: 0x00FFB2 },
  'conquistas':       { file: 'canal-conquistas.html',       wh: 'DISCORD_WEBHOOK_CONQUISTAS', emoji: 'conquistas',canal: '#conquistas',         color: 0xfb0491 },
  'operacoes':        { file: 'canal-operacoes.html',        wh: 'DISCORD_WEBHOOK_OPERACOES',  emoji: 'ops',       canal: '#operacoes',          color: 0xd90048 },
  'swaps':            { file: 'canal-swaps.html',            wh: 'DISCORD_WEBHOOK_SWAPS',      emoji: 'swaps',     canal: '#swaps',              color: 0x00D4FF },
  'relatorio-diario': { file: 'canal-relatorio-diario.html', wh: 'DISCORD_WEBHOOK_RELATORIO',  emoji: 'relatorio', canal: '#relatorio-diario',   color: 0xfb0491 },
  'gm-wagmi':         { file: 'canal-gm-wagmi.html',         wh: 'DISCORD_WEBHOOK_GM',         emoji: 'gm',        canal: '#gm-wagmi',           color: 0xfb0491 },
  'bdzinho-ia':       { file: 'canal-bdzinho-ia.html',       wh: 'DISCORD_WEBHOOK_ONCHAIN',    emoji: 'ia',        canal: '#bdzinho-ia',         color: 0xfb0491 },
};

// ── ENV ───────────────────────────────────────────────────────────────────────

const envVars = {};
try {
  fs.readFileSync(ENV_PATH, 'utf8').split('\n').forEach(line => {
    const m = line.match(/^([A-Z_]+)=(.+)$/);
    if (m) envVars[m[1]] = m[2].trim();
  });
} catch (e) {
  // .env nao encontrado — webhooks nao funcionarao
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function postFile(webhookUrl, filePath, filename, embed) {
  return new Promise((resolve, reject) => {
    const fileData   = fs.readFileSync(filePath);
    const boundary   = '----Boundary' + Date.now().toString(16);
    const payload    = JSON.stringify({ embeds: [embed], username: 'bdZinho' });
    const nl         = '\r\n';
    const header     = '--' + boundary + nl + 'Content-Disposition: form-data; name="payload_json"' + nl + 'Content-Type: application/json' + nl + nl + payload + nl;
    const fileHeader = '--' + boundary + nl + 'Content-Disposition: form-data; name="file"; filename="' + filename + '"' + nl + 'Content-Type: video/webm' + nl + nl;
    const footer     = nl + '--' + boundary + '--' + nl;
    const body       = Buffer.concat([Buffer.from(header + fileHeader), fileData, Buffer.from(footer)]);
    const url        = new URL(webhookUrl);
    const req        = https.request({
      hostname: url.hostname, path: url.pathname + url.search, method: 'POST',
      headers: { 'Content-Type': 'multipart/form-data; boundary=' + boundary, 'Content-Length': body.length },
    }, res => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => resolve({ status: res.statusCode, body: data }));
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

async function recordCard(name, card) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const videoDir = path.join(OUTPUT_DIR, 'tmp_' + name);
  fs.mkdirSync(videoDir, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--force-device-scale-factor=1'],
  });

  const context = await browser.newContext({
    viewport: { width: 1080, height: 1920 },
    deviceScaleFactor: 1,
    recordVideo: { dir: videoDir, size: { width: 1080, height: 1920 } },
  });

  const page = await context.newPage();
  console.log('  [REC] Gravando ' + card.canal + '...');

  try {
    await page.goto(BASE_URL + '/' + card.file, { waitUntil: 'networkidle' });
    await sleep(WAIT_BEFORE);
    await sleep(RECORD_MS);

    const videoPath = await page.video().path();
    await context.close();

    const finalPath = path.join(OUTPUT_DIR, name + '.webm');
    if (fs.existsSync(videoPath)) {
      fs.renameSync(videoPath, finalPath);
      try { fs.rmdirSync(videoDir, { recursive: true }); } catch {}
      console.log('     OK: ' + name + '.webm');
      await browser.close();
      return finalPath;
    }
  } catch (e) {
    console.log('     ERR: ' + e.message);
    try { await context.close(); } catch {}
  }

  await browser.close();
  return null;
}

async function sendCard(name, card, filePath) {
  const webhookUrl = envVars[card.wh];
  if (!webhookUrl) { console.log('  WARN: Sem webhook para ' + card.canal); return false; }

  const stat   = fs.statSync(filePath);
  const sizeMb = (stat.size / 1024 / 1024).toFixed(1);
  if (stat.size > 8 * 1024 * 1024) { console.log('  WARN: ' + sizeMb + 'MB > 8MB — pulando'); return false; }

  console.log('  [SEND] Enviando ' + card.canal + ' (' + sizeMb + 'MB)...');
  const embed = {
    title: card.canal,
    color: card.color,
    footer: { text: 'WEbdEX Protocol - Polygon - Dados ao vivo' },
    timestamp: new Date().toISOString(),
  };
  const r = await postFile(webhookUrl, filePath, name + '.webm', embed);
  if (r.status >= 200 && r.status < 300) {
    console.log('     OK: Enviado (' + r.status + ')');
    return true;
  }
  console.log('     ERR: HTTP ' + r.status);
  return false;
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const args   = process.argv.slice(2);
  const target = args.find(a => !a.startsWith('--'));
  const noSend = args.includes('--no-send');

  if (!target) {
    console.log('Uso: node render_card.js <card-name|all> [--no-send]');
    console.log('Cards: ' + Object.keys(CARDS).join(', '));
    process.exit(1);
  }

  const names = target === 'all' ? Object.keys(CARDS) : [target];

  for (const name of names) {
    const card = CARDS[name];
    if (!card) { console.log('ERR: Card "' + name + '" nao encontrado.'); continue; }

    const filePath = await recordCard(name, card);
    if (filePath && !noSend) {
      await sendCard(name, card, filePath);
      await sleep(1500);
    }
  }
}

main().catch(e => {
  console.error('ERR:', e.message);
  process.exit(1);
});
