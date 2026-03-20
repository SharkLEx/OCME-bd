/**
 * LMAS Checkpoint Context Injection Hook
 *
 * Fires on UserPromptSubmit — injects checkpoint summary into context.
 * Only injects ONCE per session (first prompt). Subsequent prompts skip.
 *
 * Output goes to stdout → Claude Code includes it in the conversation context.
 * This ensures every agent session starts with project awareness.
 */

const path = require('path');
const fs = require('fs');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');

function main() {
  try {
    const projectDir = PROJECT_ROOT;
    const sessionMarker = path.join(projectDir, '.lmas', '.ctx-session');

    // Only inject once per session (check by PID-based marker)
    // Use parent PID as session identifier (Claude Code process)
    const sessionId = `${process.ppid}`;
    try {
      if (fs.existsSync(sessionMarker)) {
        const existing = fs.readFileSync(sessionMarker, 'utf8').trim();
        if (existing === sessionId) return; // Already injected this session
      }
    } catch { /* proceed */ }

    // Mark session as injected
    try {
      const lmasDir = path.join(projectDir, '.lmas');
      if (!fs.existsSync(lmasDir)) fs.mkdirSync(lmasDir, { recursive: true });
      fs.writeFileSync(sessionMarker, sessionId);
    } catch { /* proceed anyway */ }

    // Read checkpoint
    const checkpointPath = path.join(projectDir, 'docs', 'PROJECT-CHECKPOINT.md');
    if (!fs.existsSync(checkpointPath)) return;

    const content = fs.readFileSync(checkpointPath, 'utf8');
    if (!content || content.trim().length < 50) return;

    // Generate compact summary for context injection
    const summary = generateSummary(content);
    if (!summary) return;

    // Output to stdout — Claude Code injects this into conversation
    process.stdout.write(summary);
  } catch { /* silent */ }
}

function generateSummary(content) {
  const lines = [];

  lines.push('<checkpoint-context>');

  // Extract key sections
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

  // Contexto Ativo — most important
  const ctx = sections['Contexto Ativo']?.trim();
  if (ctx && !ctx.includes('(atualizado pelos agentes')) {
    lines.push('CONTEXTO ATIVO:');
    // Limit to 5 lines
    const ctxLines = ctx.split('\n').filter(l => l.trim()).slice(0, 5);
    lines.push(...ctxLines);
  }

  // Decisoes Tomadas — critical for continuity
  const dec = sections['Decisoes Tomadas']?.trim();
  if (dec && !dec.includes('(atualizado pelos agentes')) {
    lines.push('');
    lines.push('DECISOES:');
    const decLines = dec.split('\n').filter(l => l.trim()).slice(0, 5);
    lines.push(...decLines);
  }

  // Proximos Passos
  const next = sections['Proximos Passos']?.trim();
  if (next && !next.includes('(atualizado pelos agentes')) {
    lines.push('');
    lines.push('PROXIMOS PASSOS:');
    const nextLines = next.split('\n').filter(l => l.trim()).slice(0, 5);
    lines.push(...nextLines);
  }

  // Ultimo Trabalho
  const last = sections['Ultimo Trabalho Realizado']?.trim();
  if (last && !last.includes('(checkpoint criado automaticamente')) {
    lines.push('');
    lines.push('ULTIMO TRABALHO:');
    const lastLines = last.split('\n').filter(l => l.trim()).slice(0, 3);
    lines.push(...lastLines);
  }

  // Git Recente
  const git = sections['Git Recente']?.trim();
  if (git) {
    lines.push('');
    lines.push('GIT:');
    const gitLines = git.split('\n').filter(l => l.trim()).slice(0, 3);
    lines.push(...gitLines);
  }

  lines.push('</checkpoint-context>');

  // Only output if there's actual content (not just tags)
  if (lines.length <= 2) return null;

  return lines.join('\n') + '\n';
}

main();
