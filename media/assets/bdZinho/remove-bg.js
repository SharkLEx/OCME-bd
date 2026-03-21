const sharp = require('sharp');
const path = require('path');

const INPUT = 'C:\\Users\\Alex\\Documents\\Imagens_bdZinho\\baixados.png';
const OUTPUT = path.join(__dirname, 'bdzinho-transparente.png');

async function removeBg() {
  const { data, info } = await sharp(INPUT)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const { width, height, channels } = info;
  const pixels = new Uint8Array(data);

  // Threshold: pixels próximos ao branco viram transparentes
  const THRESHOLD = 30;

  for (let i = 0; i < pixels.length; i += channels) {
    const r = pixels[i];
    const g = pixels[i + 1];
    const b = pixels[i + 2];

    const isNearWhite = r > (255 - THRESHOLD) && g > (255 - THRESHOLD) && b > (255 - THRESHOLD);

    if (isNearWhite) {
      pixels[i + 3] = 0; // alpha = transparente
    }
  }

  await sharp(Buffer.from(pixels), {
    raw: { width, height, channels }
  })
    .png()
    .toFile(OUTPUT);

  console.log(`✅ Fundo removido: ${OUTPUT}`);
  console.log(`   Dimensões: ${width}x${height}px`);
}

removeBg().catch(console.error);
