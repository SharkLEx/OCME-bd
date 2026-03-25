#!/usr/bin/env node
/**
 * vps-to-obsidian.js — Sync VPS monitor data → Obsidian daily note
 *
 * Uso:
 *   node bin/vps-to-obsidian.js           # Append na daily note
 *   node bin/vps-to-obsidian.js --dry-run # Mostra sem escrever
 *
 * Agendamento Windows Task Scheduler (a cada 30min):
 *   Programa: node
 *   Args:     "C:\Users\Alex\ALex Gonzaga bd\bin\vps-to-obsidian.js"
 */

'use strict';

const http  = require('http');
const https = require('https');

const VPS_HEALTH   = process.env.VPS_MONITOR_URL ? `${process.env.VPS_MONITOR_URL}/health`   : 'http://76.13.100.67:9090/health';
const VPS_METRICS  = process.env.VPS_MONITOR_URL ? `${process.env.VPS_MONITOR_URL}/metrics`  : 'http://76.13.100.67:9090/metrics';
const VPS_DIGESTS  = process.env.VPS_MONITOR_URL ? `${process.env.VPS_MONITOR_URL}/digests?days=1` : 'http://76.13.100.67:9090/digests?days=1';
const OBS_BASE    = 'https://127.0.0.1:27124';
const OBS_KEY     = process.env.OBSIDIAN_API_KEY || 'b9ac93d39dcf02ad9cb7f550e7e2fabc45b48f275cf447f31a9408db624b8a5f';
const DRY_RUN     = process.argv.includes('--dry-run');
const TIMEOUT     = 5000;

// ── HTTP helpers ──────────────────────────────────────────────────────────────

function fetch(url, timeout = TIMEOUT) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? https : http;
    const req = mod.get(url, { timeout, rejectUnauthorized: false }, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => resolve(data));
    });
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    req.on('error', reject);
  });
}

async function fetchHealth() {
  try {
    return JSON.parse(await fetch(VPS_HEALTH));
  } catch (e) {
    console.warn('[WARN] health fetch:', e.message);
    return {};
  }
}

async function fetchLatestDigest() {
  try {
    const raw = await fetch(VPS_DIGESTS);
    const data = JSON.parse(raw);
    return (data.digests && data.digests.length > 0) ? data.digests[data.digests.length - 1] : null;
  } catch (e) {
    console.warn('[WARN] digest fetch:', e.message);
    return null;
  }
}

async function fetchMetrics() {
  try {
    const raw = await fetch(VPS_METRICS);
    const result = {};
    for (const line of raw.split('\n')) {
      if (line.startsWith('#') || !line.trim()) continue;
      const parts = line.trim().rsplit ? line.trim().split(/\s+/) : line.trim().split(' ');
      if (parts.length >= 2) {
        const val = parseFloat(parts[parts.length - 1]);
        const key = parts.slice(0, -1).join(' ');
        if (!isNaN(val)) result[key] = val;
      }
    }
    return result;
  } catch (e) {
    console.warn('[WARN] metrics fetch:', e.message);
    return {};
  }
}

function obsidianAppend(markdown) {
  return new Promise((resolve, reject) => {
    // GET daily note atual, concatenar e reescrever via POST (API v3.5)
    const getReq = https.request({
      hostname: '127.0.0.1', port: 27124,
      path: '/periodic/daily/',
      method: 'GET',
      rejectUnauthorized: false,
      headers: {
        'Authorization': `Bearer ${OBS_KEY}`,
        'Accept': 'text/markdown',
      },
    }, getRes => {
      let existing = '';
      getRes.on('data', c => existing += c);
      getRes.on('end', () => {
        if (getRes.statusCode === 404) existing = '';
        // Deduplicação: substituir seção WEbdEX Monitor se já existir na nota
        const MONITOR_RE = /\n## 🖥️ WEbdEX Monitor[\s\S]*?(?=\n## [^🖥]|\n---|\n# |$)/;
        const merged = MONITOR_RE.test(existing)
          ? existing.replace(MONITOR_RE, markdown)
          : existing + markdown;
        const combined = Buffer.from(merged, 'utf8');
        const req = https.request({
          hostname: '127.0.0.1', port: 27124,
          path: '/periodic/daily/',
          method: 'POST',
          rejectUnauthorized: false,
          headers: {
            'Authorization': `Bearer ${OBS_KEY}`,
            'Content-Type': 'text/markdown',
            'Content-Length': combined.length,
          },
        }, res => {
          let body = '';
          res.on('data', c => body += c);
          res.on('end', () => resolve(res.statusCode >= 200 && res.statusCode < 300));
        });
        req.on('error', reject);
        req.write(combined);
        req.end();
      });
    });
    getReq.on('error', reject);
    getReq.end();
  });
}

// ── Note builder ──────────────────────────────────────────────────────────────

function buildDigestSection(digest) {
  if (!digest) return '';
  const wr   = (digest.wr_pct || 0).toFixed(1);
  const pnl  = (digest.pnl_usd || 0);
  const pnlTxt = pnl >= 0 ? `✅ +$${pnl.toFixed(4)}` : `⚠️ -$${Math.abs(pnl).toFixed(4)}`;
  const tvl  = Math.round(digest.tvl_usd || 0).toLocaleString('pt-BR');
  const traders = digest.traders || 0;
  const trades  = (digest.trades || 0).toLocaleString('pt-BR');

  let section = `
## 🧠 Último Ciclo 21h — ${digest.date}

| Métrica | Valor |
|---------|-------|
| Traders ativos | ${traders} |
| Total de trades | ${trades} |
| WinRate | ${wr}% |
| P&L bruto | ${pnlTxt} |
| TVL | $${tvl} |
`;
  if (digest.analysis) {
    section += `\n> 🤖 **Análise IA:** ${digest.analysis}\n`;
  }
  return section;
}

function buildNote(health, metrics, digest) {
  const ts = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', timeZone: 'America/Sao_Paulo' });

  const icon = v => v ? '✅' : '⚠️';

  const ok      = health.status === 'ok';
  const vigia   = health.vigia  === 'ok';
  const db      = health.db     === 'ok';
  const rpc     = health.rpc    === 'configured';

  const uptime  = Math.floor((metrics['vigia_uptime_seconds'] || 0) / 3600);
  const blocks  = Math.round(metrics['vigia_blocks_processed_total'] || 0).toLocaleString('pt-BR');
  const ops     = Math.round(metrics['vigia_ops_total'] || 0).toLocaleString('pt-BR');
  const lag     = Math.round(metrics['vigia_lag_blocks'] || 0);
  const capture = (metrics['vigia_capture_rate'] || 0).toFixed(1);
  const rpcErrs = Math.round(metrics['vigia_rpc_errors_total'] || 0);
  const alerts  = Math.round(metrics['sentinela_alerts_total'] || 0);

  const lagTxt     = lag === 0 ? '✅ 0' : `⚠️ ${lag} blocos`;
  const captureTxt = parseFloat(capture) >= 99.0 ? `✅ ${capture}%` : `⚠️ ${capture}%`;

  const digestSection = buildDigestSection(digest);

  return `
## 🖥️ WEbdEX Monitor — ${ts} BRT

| Componente | Status |
|-----------|--------|
| Monitor geral | ${icon(ok)} |
| Vigia (on-chain) | ${icon(vigia)} |
| Database | ${icon(db)} |
| RPC Pool | ${icon(rpc)} |

| Métrica | Valor |
|---------|-------|
| Uptime | ${uptime}h |
| Blocos processados | ${blocks} |
| Operações detectadas | ${ops} |
| Lag da chain | ${lagTxt} |
| Taxa de captura | ${captureTxt} |
| Erros RPC | ${rpcErrs} |
| Alertas sentinela | ${alerts} |
${digestSection}
`;
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  console.log('[vps-to-obsidian] Buscando dados do VPS...');
  const [health, metrics, digest] = await Promise.all([fetchHealth(), fetchMetrics(), fetchLatestDigest()]);

  if (!Object.keys(health).length && !Object.keys(metrics).length) {
    console.error('[ERROR] Sem dados do VPS. Abortando.');
    process.exit(1);
  }

  const note = buildNote(health, metrics, digest);

  if (DRY_RUN) {
    console.log('── DRY RUN ─────────────────────────────────────────');
    console.log(note);
    return;
  }

  console.log('[vps-to-obsidian] Escrevendo na daily note do Obsidian...');
  try {
    const ok = await obsidianAppend(note);
    if (ok) {
      console.log('[vps-to-obsidian] ✅ Daily note atualizada.');
    } else {
      console.error('[vps-to-obsidian] ❌ Falha. Obsidian está aberto com REST API ativa?');
      process.exit(1);
    }
  } catch (e) {
    console.error('[vps-to-obsidian] ❌ Erro:', e.message);
    process.exit(1);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
