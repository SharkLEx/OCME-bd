/**
 * Pipeline local OCME_bd — Ken Burns sem dependências externas
 * Usa FFmpeg instalado em node_modules (zero custo, offline, sem API keys)
 *
 * USAGE: node render_local.js
 * OUTPUT: media/projects/ocmc-apresentacao/renders/*.mp4
 */
'use strict';

const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const ffmpegPath = require('@ffmpeg-installer/ffmpeg').path;

const WORK_DIR   = path.join(__dirname, '..', '..', '..'); // raiz do projeto
const OUTPUT_DIR = path.join(__dirname, 'renders');

const CARDS = [
  { file: 'card_v01.png', label: 'V01 — O OCME_bd' },
  { file: 'card_v02.png', label: 'V02 — Monitoramento 24/7' },
  { file: 'card_v03.png', label: 'V03 — Seus Dados na Palma' },
  { file: 'card_v04.png', label: 'V04 — Dois Ambientes' },
  { file: 'card_v05.png', label: 'V05 — Ciclo 21h Resultados' },
];

// Ken Burns: zoom 100→106% em 10s (300 frames @ 30fps) + fade-in 1.2s (36 frames)
// zoompan: z='min(zoom+0.0002,1.06)' sobe de 1.0 a 1.06 em 300 frames
// fps=300/10=30; d=300 frames total
const VFILTER = [
  "zoompan=z='min(zoom+0.0002,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=300:s=1080x1920:fps=30",
  'fade=t=in:st=0:d=1.2',
].join(',');

if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });

const results = [];

for (const card of CARDS) {
  const inputPath  = path.join(WORK_DIR, card.file);
  const outputPath = path.join(OUTPUT_DIR, card.file.replace('.png', '.mp4'));

  if (!fs.existsSync(inputPath)) {
    console.log(`⚠️  ${card.file} não encontrado — pulando`);
    continue;
  }

  process.stdout.write(`🎬 Renderizando ${card.label}...`);
  const start = Date.now();

  try {
    execFileSync(ffmpegPath, [
      '-y',                    // sobrescrever sem perguntar
      '-loop', '1',            // loop imagem estática
      '-i', inputPath,         // input PNG
      '-vf', VFILTER,          // Ken Burns + fade-in
      '-t', '10',              // duração 10s
      '-r', '30',              // 30fps
      '-pix_fmt', 'yuv420p',   // compatível com todos os players
      '-movflags', '+faststart', // streaming-ready
      '-c:v', 'libx264',       // codec H.264
      '-crf', '18',            // qualidade alta (0=lossless, 51=pior)
      '-preset', 'fast',       // velocidade de encode
      outputPath,
    ], { stdio: 'pipe' });

    const elapsed = ((Date.now() - start) / 1000).toFixed(1);
    const kb = Math.round(fs.statSync(outputPath).size / 1024);
    console.log(` ✅ ${elapsed}s | ${kb}KB → ${path.basename(outputPath)}`);
    results.push({ label: card.label, file: path.basename(outputPath), path: outputPath, kb });
  } catch (err) {
    console.log(` ❌ ERRO: ${err.message.split('\n').slice(-3).join(' ')}`);
  }
}

console.log('\n═══════════════════════════════════════');
console.log('📋 RENDERS LOCAIS CONCLUÍDOS:');
for (const r of results) {
  console.log(`  ${r.label} → ${r.file} (${r.kb}KB)`);
}

// Salvar manifesto local
const manifestPath = path.join(__dirname, 'local_renders.json');
fs.writeFileSync(manifestPath, JSON.stringify(results, null, 2));
console.log(`\n💾 Manifesto: ${manifestPath}`);
console.log('✅ Zero APIs externas. Zero custo. Feito pelo Nabucodonosor.\n');
