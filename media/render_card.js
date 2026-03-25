#!/usr/bin/env node
/**
 * render_card.js — Renderiza e envia um card específico ao Discord
 *
 * Uso:
 *   node render_card.js token-bd          # grava + envia para o webhook do canal
 *   node render_card.js relatorio-diario  # idem
 *   node render_card.js all               # renderiza todos os 8 cards
 *
 * Requer:
 *   - Servidor card_server.py rodando em localhost:8766
 *   - Chrome instalado
 *   - FFmpeg do Playwright: npx playwright install ffmpeg
 */

const { chromium } = require('C:\\Users\\Alex\\AppData\\Local\\npm-cache\\_npx\\9833c18b2d85bc59\\node_modules\\playwright');
const fs   = require('fs');
const https = require('https');
const path  = require('path');

const CHROME_PATH   = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const BASE_URL      = 'http://localhost:8766';
const OUTPUT_DIR    = path.join(__dirname, 'output', 'videos');
const ENV_PATH      = path.join(__dirname, '..', 'packages', 'monitor-engine', '.env');
const RECORD_MS     = 5000;
const WAIT_BEFORE   = 800;  // espera dados carregarem via fetch

// ── CARDS ─────────────────────────────────────────────────────────────────────

const CARDS = {
  'webdex-onchain':   { file: 'canal-webdex-onchain.html',  wh: 'DISCORD_WEBHOOK_ONCHAIN',    emoji: '⛓️',  canal: '#webdex-on-chain',   color: 0x00D4FF },
  'token-bd':         { file: 'canal-token-bd.html',        wh: 'DISCORD_WEBHOOK_TOKEN_BD',   emoji: '💰',  canal: '#token-bd',           color: 0x00FFB2 },
  'conquistas':       { file: 'canal-conquistas.html',      wh: 'DISCORD_WEBHOOK_CONQUISTAS', emoji: '🏆',  canal: '#conquistas',         color: 0xfb0491 },
  'operacoes':        { file: 'canal-operacoes.html',       wh: 'DISCORD_WEBHOOK_OPERACOES',  emoji: '⚙️',  canal: '#operações',          color: 0xd90048 },
  'swaps':            { file: 'canal-swaps.html',           wh: 'DISCORD_WEBHOOK_SWAPS',      emoji: '🔄',  canal: '#swaps',              color: 0x00D4FF },
  'relatorio-diario': { file: 'canal-relatorio-diario.html',wh: 'DISCORD_WEBHOOK_RELATORIO',  emoji: '📊',  canal: '#relatório-diário',   color: 0xfb0491 },
  'gm-wagmi':         { file: 'canal-gm-wagmi.html',        wh: 'DISCORD_WEBHOOK_GM',         emoji: '☀️',  canal: '#gm-wagmi',           color: 0xfb0491 },
  'bdzinho-ia':       { file: 'canal-bdzinho-ia.html',      wh: 'DISCORD_WEBHOOK_ONCHAIN',    emoji: '🤖',  canal: '#bdzinho-ia',         color: 0xfb0491 },
};

// ── ENV ───────────────────────────────────────────────────────────────────────

const envVars = {};
try {
  fs.readFileSync(ENV_PATH, 'utf8').split('\n').forEach(line => {
    const m = line.match(/^([A-Z_]+)=(.+)$/);
    if (m) envVars[m[1]] = m[2].trim();
  });
} catch {}

// ── Helpers ───────────────────────────────────────────────────────────────────

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function postFile(webhookUrl, filePath, filename, embed) {
  return new Promise((resolve, reject) => {
    const fileData   = fs.readFileSync(filePath);
    const boundary   = '----Boundary' + Date.now().toString(16);
    const payload    = JSON.stringify({ embeds: [embed], username: 'bdZinho 🤖' });
    const header     = `--${boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\nContent-Type: application/json\r\n\r\n${payload}\r\n`;
    const fileHeader = `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${filename}"\r\nContent-Type: video/webm\r\n\r\n`;
    const footer     = `\r\n--${boundary}--\r\n`;
    const body       = Buffer.concat([Buffer.from(header + fileHeader), fileData, Buffer.from(footer)]);
    const url        = new URL(webhookUrl);
    const req        = https.request({
      hostname: url.hostname, path: url.pathname + url.search, method: 'POST',
      headers: { 'Content-Type': `multipart/form-data; boundary=${boundary}`, 'Content-Length': body.length },
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
  const videoDir  = path.join(OUTPUT_DIR, 'tmp_' + name);
  fs.mkdirSync(videoDir, { recursive: true });

  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--force-device-scale-factor=1'],
  });

  const context = await browser.newContext({
    viewport: { width: 1080, height: 1920 },
    deviceScaleFactor: 1,
    recordVideo: { dir: videoDir, size: { width: 1080, height: 1920 } },
  });

  const page = await context.newPage();
  console.log(`  🎥 Gravando ${card.canal}...`);

  try {
    await page.goto(`${BASE_URL}/${card.file}`, { waitUntil: 'networkidle' });
    await sleep(WAIT_BEFORE);   // aguarda fetch de dados ao vivo
    await sleep(RECORD_MS);

    const videoPath = await page.video().path();
    await context.close();

    const finalPath = path.join(OUTPUT_DIR, `${name}.webm`);
    if (fs.existsSync(videoPath)) {
      fs.renameSync(videoPath, finalPath);
      try { fs.rmdirSync(videoDir, { recursive: true }); } catch {}
      console.log(`     ✅ ${name}.webm`);
      await browser.close();
      return finalPath;
    }
  } catch (e) {
    console.log(`     ❌ ${e.message}`);
    try { await context.close(); } catch {}
  }

  await browser.close();
  return null;
}

async function sendCard(name, card, filePath) {
  const webhookUrl = envVars[card.wh];
  if (!webhookUrl) { console.log(`  ⚠️  Sem webhook para ${card.canal}`); return false; }

  const stat   = fs.statSync(filePath);
  const sizeMb = (stat.size / 1024 / 1024).toFixed(1);
  if (stat.size > 8 * 1024 * 1024) { console.log(`  ⚠️  ${sizeMb}MB > 8MB — pulando`); return false; }

  console.log(`  📤 Enviando ${card.canal} (${sizeMb}MB)...`);
  const embed = {
    title:       `${card.emoji} ${card.canal}`,
    color:       card.color,
    footer:      { text: 'WEbdEX Protocol • Polygon • Dados ao vivo' },
    timestamp:   new Date().toISOString(),
  };
  const r = await postFile(webhookUrl, filePath, `${name}.webm`, embed);
  if (r.status >= 200 && r.status < 300) {
    console.log(`     ✅ Enviado (${r.status})`);
    return true;
  }
  console.log(`     ❌ HTTP ${r.status}`);
  return false;
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const args   = process.argv.slice(2);
  const target = args.find(a => !a.startsWith('--'));
  const noSend = args.includes('--no-send');

  if (!target) {
    console.log('Uso: node render_card.js <card-name|all> [--no-send]');
    console.log('Cards:', Object.keys(CARDS).join(', '));
    process.exit(1);
  }

  const names = target === 'all' ? Object.keys(CARDS) : [target];

  for (const name of names) {
    const card = CARDS[name];
    if (!card) { console.log(`❌ Card "${name}" não encontrado.`); continue; }

    const filePath = await recordCard(name, card);
    if (filePath && !noSend) {
      await sendCard(name, card, filePath);
      await sleep(1500);
    }
  }
}

main().catch(e => {
  console.error('❌ Erro:', e.message);
  process.exit(1);
});
