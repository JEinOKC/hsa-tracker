/**
 * Generates PWA and Apple touch icons from favicon.svg.
 *
 * Output files:
 *   public/icons/pwa-192.png          — 192×192, full bleed (purpose: any)
 *   public/icons/pwa-512.png          — 512×512, full bleed (purpose: any)
 *   public/icons/pwa-512-maskable.png — 512×512, safe-zone padded (purpose: maskable)
 *   public/icons/apple-touch-icon.png — 180×180, full bleed (iOS home screen)
 *
 * Usage:
 *   node scripts/generate-icons.mjs
 */

import sharp from 'sharp'
import { readFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

const svgPath = resolve(root, 'public/favicon.svg')
const svgBuffer = readFileSync(svgPath)

// Brand background color (matches theme_color in manifest)
const BG = { r: 14, g: 165, b: 233 } // #0ea5e9

async function makeFullBleed(size, outPath) {
  // Render SVG at the target size, then composite on a solid background
  // so transparent corners are filled instead of appearing black on iOS.
  const iconBuffer = await sharp(svgBuffer)
    .resize(size, size)
    .png()
    .toBuffer()

  await sharp({
    create: { width: size, height: size, channels: 4, background: { ...BG, alpha: 255 } },
  })
    .composite([{ input: iconBuffer, blend: 'over' }])
    .png()
    .toFile(outPath)

  console.log(`  ✓  ${outPath.replace(root + '/', '')}  (${size}×${size})`)
}

async function makeMaskable(size, outPath) {
  // For maskable icons, content must fit within the inner 80% "safe zone".
  // Padding = 10% on each side.
  const padding = Math.round(size * 0.1)
  const innerSize = size - padding * 2

  const iconBuffer = await sharp(svgBuffer)
    .resize(innerSize, innerSize)
    .png()
    .toBuffer()

  await sharp({
    create: { width: size, height: size, channels: 4, background: { ...BG, alpha: 255 } },
  })
    .composite([{ input: iconBuffer, top: padding, left: padding, blend: 'over' }])
    .png()
    .toFile(outPath)

  console.log(`  ✓  ${outPath.replace(root + '/', '')}  (${size}×${size}, maskable)`)
}

console.log('Generating PWA icons from favicon.svg…')
await makeFullBleed(192, resolve(root, 'public/icons/pwa-192.png'))
await makeFullBleed(512, resolve(root, 'public/icons/pwa-512.png'))
await makeMaskable(512, resolve(root, 'public/icons/pwa-512-maskable.png'))
await makeFullBleed(180, resolve(root, 'public/icons/apple-touch-icon.png'))
console.log('Done.')
