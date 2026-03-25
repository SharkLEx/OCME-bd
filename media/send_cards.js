#!/usr/bin/env node
/**
 * send_cards.js — Envia 8 cards PNG para os webhooks do Discord
 * Uso: node send_cards.js
 * Requer: .env com DISCORD_WEBHOOK_* configurados
 */
const fs = require('fs');
const https = require('https');
const path = require('path');

// Carregar .env
const envPath = path.join(__dirname, '..', 'packages', 'monitor-engine', '.env');
const envVars = {};
fs.readFileSync(envPath, 'utf8').split('\n').forEach(line => {
  const m = line.match(/^([A-Z_]+)=(.+)$/);
  if (m) envVars[m[1]] = m[2].trim();
});

const SCREENSHOTS_DIR = path.join(__dirname, 'output', 'screenshots');

const CARDS = [
  {
    file: 'canal-webdex-onchain.png',
    webhook: envVars.DISCORD_WEBHOOK_ONCHAIN,
    emoji: '⛓️',
    canal: '#webdex-on-chain',
    desc: 'Eventos on-chain • Anomalias • Polygon Live',
    color: 0x00D4FF,
  },
  {
    file: 'canal-token-bd.png',
    webhook: envVars.DISCORD_WEBHOOK_TOKEN_BD,
    emoji: '💰',
    canal: '#token-bd',
    desc: 'Supply • Holders • Market Cap a cada 2h',
    color: 0x00FFB2,
  },
  {
    file: 'canal-conquistas.png',
    webhook: envVars.DISCORD_WEBHOOK_CONQUISTAS,
    emoji: '🏆',
    canal: '#conquistas',
    desc: 'Milestones • Novos holders • Recordes',
    color: 0xfb0491,
  },
  {
    file: 'canal-operacoes.png',
    webhook: envVars.DISCORD_WEBHOOK_OPERACOES,
    emoji: '⚙️',
    canal: '#operações',
    desc: 'Log de operações • Novas carteiras • Protocolo',
    color: 0xd90048,
  },
  {
    file: 'canal-swaps.png',
    webhook: envVars.DISCORD_WEBHOOK_SWAPS,
    emoji: '🔄',
    canal: '#swaps',
    desc: 'Create Swap • Swap Tokens • Volume ao vivo',
    color: 0x00D4FF,
  },
  {
    file: 'canal-relatorio-diario.png',
    webhook: envVars.DISCORD_WEBHOOK_RELATORIO,
    emoji: '📊',
    canal: '#relatório-diário',
    desc: 'Ciclo 21h • Performance • Tendência do dia',
    color: 0xfb0491,
  },
  {
    file: 'canal-gm-wagmi.png',
    webhook: envVars.DISCORD_WEBHOOK_GM,
    emoji: '☀️',
    canal: '#gm-wagmi',
    desc: 'Ritual 7h • Manchetes Web3 • Sentimento do mercado',
    color: 0xfb0491,
  },
  {
    file: 'canal-bdzinho-ia.png',
    webhook: envVars.DISCORD_WEBHOOK_ONCHAIN, // fallback para #webdex-on-chain
    emoji: '🤖',
    canal: '#bdzinho-ia',
    desc: 'Chat IA • DeFi • Memória persistente',
    color: 0xfb0491,
  },
];

function postJson(webhookUrl, payload) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload);
    const url = new URL(webhookUrl);
    const req = https.request({
      hostname: url.hostname,
      path: url.pathname + url.search,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
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

function postFile(webhookUrl, filePath, filename, embedJson) {
  return new Promise((resolve, reject) => {
    const fileData = fs.readFileSync(filePath);
    const boundary = '----FormBoundary' + Date.now().toString(16);
    const embedStr = JSON.stringify({ embeds: [embedJson], username: 'bdZinho 🤖' });

    const parts = [];
    // payload_json part
    parts.push(
      `--${boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\nContent-Type: application/json\r\n\r\n${embedStr}\r\n`
    );
    // file part header
    const fileHeader = `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${filename}"\r\nContent-Type: image/png\r\n\r\n`;
    const footer = `\r\n--${boundary}--\r\n`;

    const headerBuf = Buffer.from(parts.join('') + fileHeader);
    const footerBuf = Buffer.from(footer);
    const body = Buffer.concat([headerBuf, fileData, footerBuf]);

    const url = new URL(webhookUrl);
    const req = https.request({
      hostname: url.hostname,
      path: url.pathname + url.search,
      method: 'POST',
      headers: {
        'Content-Type': `multipart/form-data; boundary=${boundary}`,
        'Content-Length': body.length,
      },
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

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  console.log('🤖 bdZinho Card Sender v2 — Cards Corrigidos 1080×1920\n');

  let sent = 0, errors = 0;

  for (const card of CARDS) {
    if (!card.webhook) {
      console.log(`  ⚠️  Sem webhook para ${card.canal}, pulando`);
      continue;
    }

    const filePath = path.join(SCREENSHOTS_DIR, card.file);
    if (!fs.existsSync(filePath)) {
      console.log(`  ⚠️  ${card.file} não encontrado`);
      errors++;
      continue;
    }

    console.log(`  📤 ${card.canal}...`);

    try {
      const embed = {
        title: `${card.emoji} ${card.canal}`,
        description: card.desc,
        color: card.color,
        footer: { text: 'WEbdEX Protocol • Polygon • 1080×1920' },
      };

      const r = await postFile(card.webhook, filePath, card.file, embed);
      if (r.status >= 200 && r.status < 300) {
        console.log(`     ✅ Enviado (${r.status})`);
        sent++;
      } else {
        console.log(`     ❌ Erro HTTP ${r.status}: ${r.body.substring(0, 120)}`);
        errors++;
      }
    } catch (e) {
      console.log(`     ❌ ${e.message}`);
      errors++;
    }

    await sleep(1500); // rate limit Discord
  }

  console.log(`\n🎯 Entrega: ${sent} enviados, ${errors} erros`);
}

main().catch(console.error);
