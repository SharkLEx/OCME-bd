/**
 * LMAS State Sync Hook — Document Sync to matrix_project_state
 *
 * Fires on PostToolUse for Edit/Write — collects changed docs
 * and syncs to Supabase via sync-state Edge Function.
 *
 * Features:
 * - Supports token cache v2 (AES-256-GCM) and v1 (plaintext)
 * - MERGE checkpoint refresh (preserves agent-written sections)
 * - Backup before checkpoint modification
 * - Rate limited to 1 sync per 5 minutes
 *
 * RULES:
 * - ZERO console.log — completely silent
 * - NEVER block — fire-and-forget, timeout 8s
 * - NEVER fail visibly — all errors → exit 0
 */

const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const https = require('https');
const http = require('http');
const os = require('os');

const API_BASE_URL = process.env.MATRIX_API_URL || 'https://qaomekspdjfbdeixxjky.supabase.co/functions/v1';
const SYNC_INTERVAL_MS = 5 * 60 * 1000; // 5 min

const FILE_PATTERNS = [
  { pattern: 'docs/PROJECT-CHECKPOINT.md', type: 'checkpoint' },
  { pattern: 'docs/stories', type: 'story', ext: '.md' },
  { pattern: 'docs', type: 'doc', ext: '.md', match: /^(prd|architecture|adr-|spec|requirements|planning|roadmap|design-system|MASTER|technical-debt)/i },
  { pattern: '.claude/projects', type: 'memory', ext: '.md' },
  { pattern: '.lmas-core/development/agents', type: 'memory', ext: '.md', match: /MEMORY\.md$/i },
];

/** Sections written by agents — NEVER overwrite */
const AGENT_SECTIONS = [
  'Contexto Ativo', 'Decisoes Tomadas', 'Ambiente Configurado',
  'Ultimo Trabalho Realizado', 'Proximos Passos', 'Decisoes Arquiteturais',
  'Documentos do Projeto', 'Totais', 'Resumo do Projeto',
];

function readTokenCache(tokenPath) {
  const raw = JSON.parse(fs.readFileSync(tokenPath, 'utf8'));
  if (raw.v === 2 && raw.data) {
    const key = crypto.createHash('sha256')
      .update(`matrix-ai:${os.hostname()}:${os.userInfo().username}`)
      .digest();
    const buf = Buffer.from(raw.data, 'base64');
    const iv = buf.subarray(0, 12);
    const tag = buf.subarray(12, 28);
    const ciphertext = buf.subarray(28);
    const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv);
    decipher.setAuthTag(tag);
    return JSON.parse(decipher.update(ciphertext, undefined, 'utf8') + decipher.final('utf8'));
  }
  return raw;
}

function parseCheckpointSections(content) {
  const sections = {};
  let currentSection = '_header';
  for (const line of content.split('\n')) {
    const match = line.match(/^## (.+)$/);
    if (match) {
      currentSection = match[1].trim();
      sections[currentSection] = '';
    } else {
      sections[currentSection] = (sections[currentSection] || '') + line + '\n';
    }
  }
  return sections;
}

function main() {
  try {
    const projectDir = process.cwd();
    const cacheDir = path.join(projectDir, '.lmas');
    const tokenPath = path.join(cacheDir, 'token-cache.json');
    const syncPath = path.join(cacheDir, '.sc');

    if (!fs.existsSync(tokenPath)) return;

    let cached;
    try { cached = readTokenCache(tokenPath); } catch { return; }
    if (!cached || !cached.token) return;

    // Rate limit
    let syncCache = {};
    try { syncCache = JSON.parse(fs.readFileSync(syncPath, 'utf8')); } catch { /* first run */ }
    const lastSync = syncCache.t ? new Date(syncCache.t).getTime() : 0;
    if (Date.now() - lastSync < SYNC_INTERVAL_MS) return;

    // Ensure + refresh checkpoint (MERGE mode)
    ensureCheckpoint(projectDir, cached);
    refreshCheckpoint(projectDir);

    const files = collectFiles(projectDir, syncCache.h || {});
    if (files.length === 0) {
      syncCache.t = new Date().toISOString();
      try { fs.writeFileSync(syncPath, JSON.stringify(syncCache)); } catch { /* skip */ }
      return;
    }

    const body = JSON.stringify({
      token: cached.token,
      project_name: cached.project_name || path.basename(projectDir),
      files: files.map(f => ({
        file_type: f.type,
        file_path: f.rel,
        file_name: path.basename(f.rel),
        content: f.content,
        content_hash: f.hash,
        metadata: f.metadata,
      })),
    });

    post(`${API_BASE_URL}/sync-state`, body, () => {
      const hashes = syncCache.h || {};
      for (const f of files) hashes[f.rel] = f.hash;
      syncCache.h = hashes;
      syncCache.t = new Date().toISOString();
      try { fs.writeFileSync(syncPath, JSON.stringify(syncCache)); } catch { /* skip */ }
    });
  } catch { /* silent */ }
}

function ensureCheckpoint(projectDir, cached) {
  try {
    const checkpointPath = path.join(projectDir, 'docs', 'PROJECT-CHECKPOINT.md');
    if (fs.existsSync(checkpointPath)) return;
    const docsDir = path.join(projectDir, 'docs');
    if (!fs.existsSync(docsDir)) fs.mkdirSync(docsDir, { recursive: true });
    const projectName = cached.project_name || path.basename(projectDir);
    const date = new Date().toISOString().split('T')[0];
    fs.writeFileSync(checkpointPath, [
      '# Project Checkpoint', '',
      `> Ultima atualizacao: ${date}`, '',
      '## Contexto Ativo', '', '(atualizado pelos agentes durante o trabalho)', '',
      '## Status das Stories', '', '(nenhuma story criada ainda)', '',
      '## Decisoes Tomadas', '', '(atualizado pelos agentes durante o trabalho)', '',
      '## Ultimo Trabalho Realizado', '', '(checkpoint criado automaticamente)', '',
      '## Proximos Passos', '', '- [ ] Criar primeira story', '',
    ].join('\n'));
  } catch { /* silent */ }
}

function refreshCheckpoint(projectDir) {
  try {
    const checkpointPath = path.join(projectDir, 'docs', 'PROJECT-CHECKPOINT.md');
    if (!fs.existsSync(checkpointPath)) return;

    const { execSync } = require('child_process');
    const date = new Date().toISOString().split('T')[0];

    // Backup before modifying
    try {
      const backupDir = path.join(projectDir, '.lmas');
      if (!fs.existsSync(backupDir)) fs.mkdirSync(backupDir, { recursive: true });
      fs.copyFileSync(checkpointPath, path.join(backupDir, '.checkpoint-backup'));
    } catch { /* skip */ }

    const existing = fs.readFileSync(checkpointPath, 'utf8');
    const existingSections = parseCheckpointSections(existing);

    // Check if agents wrote rich content
    const hasAgentContent = AGENT_SECTIONS.some(s =>
      existingSections[s] && existingSections[s].trim().length > 0
      && !existingSections[s].includes('(nenhum')
      && !existingSections[s].includes('(atualizado pelos agentes')
      && !existingSections[s].includes('(checkpoint criado automaticamente')
    );

    // Collect auto data
    let recentCommits = '(nenhum commit encontrado)';
    let branch = '';
    let storiesTable = '(nenhuma story encontrada)';
    let envKeys = '';
    let modifiedCount = 0;

    try {
      const log = execSync('git log --oneline -5 2>/dev/null', { cwd: projectDir, encoding: 'utf8', timeout: 3000 }).trim();
      if (log) recentCommits = log.split('\n').map(l => `- \`${l}\``).join('\n');
    } catch { /* skip */ }
    try { branch = execSync('git branch --show-current 2>/dev/null', { cwd: projectDir, encoding: 'utf8', timeout: 3000 }).trim(); } catch { /* skip */ }
    try {
      const storyFiles = collectStories(projectDir);
      if (storyFiles.length > 0) {
        storiesTable = '| Story | Status |\n|-------|--------|\n' + storyFiles.map(s => `| ${s.name} | ${s.status} |`).join('\n');
      }
    } catch { /* skip */ }
    try {
      const envPath = path.join(projectDir, '.env');
      if (fs.existsSync(envPath)) {
        const keys = fs.readFileSync(envPath, 'utf8').split('\n')
          .filter(l => l.includes('=') && !l.startsWith('#'))
          .map(l => l.split('=')[0].trim()).filter(k => k.length > 0);
        if (keys.length > 0) envKeys = keys.join(', ');
      }
    } catch { /* skip */ }
    try {
      const status = execSync('git diff --name-only 2>/dev/null', { cwd: projectDir, encoding: 'utf8', timeout: 3000 }).trim();
      modifiedCount = status ? status.split('\n').length : 0;
    } catch { /* skip */ }

    if (hasAgentContent) {
      // MERGE mode — only update auto sections, preserve agent content
      let updated = existing;
      updated = updated.replace(/^> Ultima atualizacao:.*$/m, `> Ultima atualizacao: ${date} (auto-refresh)`);

      // Update stories table if section exists
      if (existingSections['Status das Stories']) {
        const old = existingSections['Status das Stories'];
        if (old.includes('(nenhuma story') || old.includes('| Story |')) {
          updated = updated.replace(old, '\n' + storiesTable + '\n\n');
        }
      }

      // Update or append auto sections
      const autoBlock = [
        '\n## Git Recente\n',
        recentCommits + '\n',
        branch ? `Branch: \`${branch}\`\n` : '',
        `Arquivos modificados: ${modifiedCount}\n`,
        envKeys ? `\n## Ambiente Detectado\n\nKeys: ${envKeys}\n` : '',
      ].join('');

      if (updated.includes('## Git Recente')) {
        // Replace from ## Git Recente to next ## or end
        updated = updated.replace(/## Git Recente[\s\S]*?(?=\n## (?!Ambiente Detectado)|$)/, '');
        updated = updated.replace(/## Ambiente Detectado[\s\S]*?(?=\n## |$)/, '');
        updated = updated.trimEnd() + '\n' + autoBlock;
      } else {
        updated = updated.trimEnd() + '\n' + autoBlock;
      }

      fs.writeFileSync(checkpointPath, updated);
    } else {
      // FULL mode — generic checkpoint
      const checkpoint = [
        '# Project Checkpoint', '',
        `> Ultima atualizacao: ${date} (auto-refresh)`, '',
        '## Contexto Ativo', '', '(atualizado pelos agentes durante o trabalho)', '',
        '## Status das Stories', '', storiesTable, '',
        '## Decisoes Tomadas', '', '(atualizado pelos agentes durante o trabalho)', '',
        '## Ultimo Trabalho Realizado', '', recentCommits, '',
        `Arquivos modificados (nao commitados): ${modifiedCount}`, '',
        '## Proximos Passos', '', '(atualizado pelos agentes durante o trabalho)', '',
        '## Git Recente', '', recentCommits,
        branch ? `Branch: \`${branch}\`` : '', '',
        envKeys ? `## Ambiente Detectado\n\nKeys: ${envKeys}\n` : '',
      ].filter(l => l !== undefined).join('\n');
      fs.writeFileSync(checkpointPath, checkpoint);
    }
  } catch { /* silent */ }
}

function collectStories(projectDir) {
  const result = [];
  const dir = path.join(projectDir, 'docs', 'stories');
  const scan = (d) => {
    if (!fs.existsSync(d)) return;
    for (const entry of fs.readdirSync(d)) {
      const full = path.join(d, entry);
      const stat = fs.statSync(full);
      if (stat.isDirectory()) scan(full);
      else if (entry.endsWith('.md')) {
        const c = fs.readFileSync(full, 'utf8');
        const s = c.match(/status:\s*(\w+)/i);
        const t = c.match(/title:\s*(.+)/i) || c.match(/^#\s+(.+)/m);
        result.push({ name: entry.replace('.md', ''), status: s ? s[1] : 'Unknown', title: t ? t[1].trim().slice(0, 50) : entry });
      }
    }
  };
  scan(dir);
  return result;
}

function collectFiles(projectDir, prevHashes) {
  const result = [];
  for (const pattern of FILE_PATTERNS) {
    const fullPath = path.join(projectDir, pattern.pattern);
    if (pattern.pattern.includes('.')) {
      if (fs.existsSync(fullPath)) {
        const f = processFile(fullPath, projectDir, pattern.type, prevHashes);
        if (f) result.push(f);
      }
    } else {
      if (fs.existsSync(fullPath) && fs.statSync(fullPath).isDirectory()) {
        scanDir(fullPath, projectDir, pattern, prevHashes, result);
      }
    }
  }
  return result;
}

function scanDir(dir, projectDir, pattern, prevHashes, result) {
  try {
    for (const entry of fs.readdirSync(dir)) {
      const full = path.join(dir, entry);
      const stat = fs.statSync(full);
      if (stat.isDirectory()) scanDir(full, projectDir, pattern, prevHashes, result);
      else if (stat.isFile() && entry.endsWith(pattern.ext || '.md')) {
        if (pattern.match && !pattern.match.test(entry)) continue;
        const f = processFile(full, projectDir, pattern.type, prevHashes);
        if (f) result.push(f);
      }
    }
  } catch { /* skip */ }
}

function processFile(fullPath, projectDir, type, prevHashes) {
  try {
    const content = fs.readFileSync(fullPath, 'utf8');
    const hash = crypto.createHash('sha256').update(content).digest('hex').slice(0, 16);
    const rel = path.relative(projectDir, fullPath).replace(/\\/g, '/');
    if (prevHashes[rel] === hash) return null;
    const metadata = {};
    if (type === 'story') {
      const s = content.match(/status:\s*(\w+)/i);
      if (s) metadata.status = s[1];
      const t = content.match(/title:\s*(.+)/i) || content.match(/^#\s+(.+)/m);
      if (t) metadata.title = t[1].trim();
      const checked = (content.match(/\[x\]/gi) || []).length;
      const unchecked = (content.match(/\[ \]/g) || []).length;
      if (checked + unchecked > 0) metadata.progress = Math.round((checked / (checked + unchecked)) * 100);
    }
    if (type === 'doc') {
      const t = content.match(/^#\s+(.+)/m);
      if (t) metadata.title = t[1].trim();
    }
    return { type, rel, content, hash, metadata };
  } catch { return null; }
}

function post(url, body, onSuccess) {
  try {
    const parsed = new URL(url);
    const lib = parsed.protocol === 'https:' ? https : http;
    const req = lib.request({
      hostname: parsed.hostname,
      port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
      path: parsed.pathname,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
      timeout: 8000,
    }, (res) => {
      let data = '';
      res.on('data', (c) => data += c);
      res.on('end', () => { try { if (JSON.parse(data).ok) onSuccess(); } catch { /* skip */ } });
    });
    req.on('error', () => {});
    req.on('timeout', () => req.destroy());
    req.write(body);
    req.end();
  } catch { /* silent */ }
}

main();
