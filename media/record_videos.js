#!/usr/bin/env node
/**
 * record_videos.js — Grava WebM animados dos 8 cards bdZinho e envia ao Discord
 *
 * Usa Chrome local (DPR=1, viewport 1080×1920) — sem zoom
 * CSS animations rodam normalmente e são capturadas no vídeo
 *
 * Uso:
 *   node record_videos.js           # grava + envia
 *   node record_videos.js --record  # só grava
 *   node record_videos.js --send    # só envia (arquivos já gravados)
 */

const { chromium } = require('C:\\Users\\Alex\\AppData\\Local\\npm-cache\\_npx\\9833c18b2d85bc59\\node_modules\\playwright');
const fs = require('fs');
const https = require('https');
const path = require('path');

// ── Config ────────────────────────────────────────────────────────────────────

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const BASE_URL = 'http://localhost:8766';
const OUTPUT_DIR = path.join(__dirname, 'output', 'videos');
const ENV_PATH = path.join(__dirname, '..', 'packages', 'monitor-engine', '.env');

const RECORD_DURATION_MS = 5000;  // 5 segundos de animação
const WAIT_BEFORE_RECORD_MS = 300; // aguardar animações iniciarem

// ── Webhooks ──────────────────────────────────────────────────────────────────

const envVars = {};
fs.readFileSync(ENV_PATH, 'utf8').split('\n').forEach(line => {
  const m = line.match(/^([A-Z_]+)=(.+)$/);
  if (m) envVars[m[1]] = m[2].trim();
});

const CARDS = [
  {
    file: 'canal-webdex-onchain.html',
    name: 'canal-webdex-onchain',
    webhook: envVars.DISCORD_WEBHOOK_ONCHAIN,
    emoji: '⛓️', canal: '#webdex-on-chain',
    desc: 'Eventos on-chain • Anomalias • Polygon Live',
    color: 0x00D4FF,
  },
  {
    file: 'canal-token-bd.html',
    name: 'canal-token-bd',
    webhook: envVars.DISCORD_WEBHOOK_TOKEN_BD,
    emoji: '💰', canal: '#token-bd',
    desc: 'Supply • Holders • Market Cap a cada 2h',
    color: 0x00FFB2,
  },
  {
    file: 'canal-conquistas.html',
    name: 'canal-conquistas',
    webhook: envVars.DISCORD_WEBHOOK_CONQUISTAS,
    emoji: '🏆', canal: '#conquistas',
    desc: 'Milestones • Novos holders • Recordes',
    color: 0xfb0491,
  },
  {
    file: 'canal-operacoes.html',
    name: 'canal-operacoes',
    webhook: envVars.DISCORD_WEBHOOK_OPERACOES,
    emoji: '⚙️', canal: '#operações',
    desc: 'Log de operações • Novas carteiras • Protocolo',
    color: 0xd90048,
  },
  {
    file: 'canal-swaps.html',
    name: 'canal-swaps',
    webhook: envVars.DISCORD_WEBHOOK_SWAPS,
    emoji: '🔄', canal: '#swaps',
    desc: 'Create Swap • Swap Tokens • Volume ao vivo',
    color: 0x00D4FF,
  },
  {
    file: 'canal-relatorio-diario.html',
    name: 'canal-relatorio-diario',
    webhook: envVars.DISCORD_WEBHOOK_RELATORIO,
    emoji: '📊', canal: '#relatório-diário',
    desc: 'Ciclo 21h • Performance • Tendência do dia',
    color: 0xfb0491,
  },
  {
    file: 'canal-gm-wagmi.html',
    name: 'canal-gm-wagmi',
    webhook: envVars.DISCORD_WEBHOOK_GM,
    emoji: '☀️', canal: '#gm-wagmi',
    desc: 'Ritual 7h • Manchetes Web3 • Sentimento do mercado',
    color: 0xfb0491,
  },
  {
    file: 'canal-bdzinho-ia.html',
    name: 'canal-bdzinho-ia',
    webhook: envVars.DISCORD_WEBHOOK_ONCHAIN,
    emoji: '🤖', canal: '#bdzinho-ia',
    desc: 'Chat IA • DeFi • Memória persistente',
    color: 0xfb0491,
  },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function postFile(webhookUrl, filePath, filename, embed) {
  return new Promise((resolve, reject) => {
    const fileData = fs.readFileSync(filePath);
    const boundary = '----Boundary' + Date.now().toString(16);
    const payloadJson = JSON.stringify({ embeds: [embed], username: 'bdZinho 🤖' });
    const header = `--${boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\nContent-Type: application/json\r\n\r\n${payloadJson}\r\n`;
    const fileHeader = `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${filename}"\r\nContent-Type: video/webm\r\n\r\n`;
    const footer = `\r\n--${boundary}--\r\n`;
    const body = Buffer.concat([Buffer.from(header + fileHeader), fileData, Buffer.from(footer)]);
    const url = new URL(webhookUrl);
    const req = https.request({
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

// ── Gravar ────────────────────────────────────────────────────────────────────

async function recordVideos() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--force-device-scale-factor=1'],
  });

  const results = [];
  console.log(`\n🎬 Gravando ${CARDS.length} vídeos (${RECORD_DURATION_MS / 1000}s cada)...\n`);

  for (const card of CARDS) {
    const videoDir = path.join(OUTPUT_DIR, 'tmp_' + card.name);
    fs.mkdirSync(videoDir, { recursive: true });

    const context = await browser.newContext({
      viewport: { width: 1080, height: 1920 },
      deviceScaleFactor: 1,
      recordVideo: { dir: videoDir, size: { width: 1080, height: 1920 } },
    });

    const page = await context.newPage();
    console.log(`  🎥 ${card.canal}...`);

    try {
      await page.goto(`${BASE_URL}/${card.file}`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(WAIT_BEFORE_RECORD_MS);
      await page.waitForTimeout(RECORD_DURATION_MS);

      const videoPath = await page.video().path();
      await context.close(); // salva o vídeo

      // Mover e renomear
      const finalPath = path.join(OUTPUT_DIR, `${card.name}.webm`);
      if (fs.existsSync(videoPath)) {
        fs.renameSync(videoPath, finalPath);
        // Limpar dir temporário
        fs.rmdirSync(videoDir, { recursive: true });
        results.push({ card, path: finalPath });
        console.log(`     ✅ ${card.name}.webm`);
      } else {
        console.log(`     ⚠️  Vídeo não encontrado`);
        await context.close();
      }
    } catch (e) {
      console.log(`     ❌ ${e.message}`);
      try { await context.close(); } catch {}
    }
  }

  await browser.close();
  return results;
}

// ── Enviar ────────────────────────────────────────────────────────────────────

async function sendVideos(results) {
  console.log(`\n📡 Enviando ${results.length} vídeos ao Discord...\n`);
  let sent = 0, errors = 0;

  for (const { card, path: filePath } of results) {
    if (!card.webhook) {
      console.log(`  ⚠️  Sem webhook para ${card.canal}`);
      continue;
    }
    if (!fs.existsSync(filePath)) {
      console.log(`  ⚠️  ${filePath} não encontrado`);
      errors++;
      continue;
    }

    const stat = fs.statSync(filePath);
    const sizeMb = (stat.size / 1024 / 1024).toFixed(1);
    console.log(`  📤 ${card.canal} (${sizeMb}MB)...`);

    // Discord limite: 8MB para servidores sem boost
    if (stat.size > 8 * 1024 * 1024) {
      console.log(`     ⚠️  Arquivo ${sizeMb}MB > 8MB — pulando (servidor sem boost)`);
      errors++;
      continue;
    }

    try {
      const embed = {
        title: `${card.emoji} ${card.canal}`,
        description: card.desc,
        color: card.color,
        footer: { text: 'WEbdEX Protocol • Polygon • 1080×1920 • Animado' },
      };
      const r = await postFile(card.webhook, filePath, `${card.name}.webm`, embed);
      if (r.status >= 200 && r.status < 300) {
        console.log(`     ✅ Enviado (${r.status})`);
        sent++;
      } else {
        console.log(`     ❌ HTTP ${r.status}: ${r.body.substring(0, 100)}`);
        errors++;
      }
    } catch (e) {
      console.log(`     ❌ ${e.message}`);
      errors++;
    }

    await sleep(2000); // rate limit Discord
  }

  console.log(`\n🎯 Entrega: ${sent} enviados, ${errors} erros`);
  return sent;
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const onlyRecord = args.includes('--record');
  const onlySend = args.includes('--send');

  console.log('🤖 bdZinho Video Recorder & Discord Sender');
  console.log(`   Viewport: 1080×1920 | DPR: 1 | Chrome: local`);
  console.log(`   Output: ${OUTPUT_DIR}`);

  let results = [];

  if (!onlySend) {
    results = await recordVideos();
  } else {
    // Carregar vídeos existentes
    for (const card of CARDS) {
      const filePath = path.join(OUTPUT_DIR, `${card.name}.webm`);
      if (fs.existsSync(filePath)) results.push({ card, path: filePath });
    }
    console.log(`\n📦 ${results.length} vídeos existentes encontrados`);
  }

  if (!onlyRecord && results.length > 0) {
    await sendVideos(results);
  } else if (results.length === 0) {
    console.log('\n⚠️  Nenhum vídeo para enviar.');
  } else {
    console.log(`\n✅ ${results.length} vídeos gravados em ${OUTPUT_DIR}`);
  }
}

main().catch(e => {
  console.error('❌ Erro fatal:', e.message);
  process.exit(1);
});
