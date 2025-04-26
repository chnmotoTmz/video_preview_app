#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const gpmfExtract = require('gpmf-extract');
const goproTelemetry = require('./gopro-telemetry');

async function main() {
  if (process.argv.length < 3) {
    console.error('Usage: node parse_telemetry.js <video_file.mp4>');
    process.exit(1);
  }

  const videoPath = process.argv[2];
  if (!fs.existsSync(videoPath)) {
    console.error(`File not found: ${videoPath}`);
    process.exit(1);
  }

  console.log(`Extracting GPMF from: ${videoPath}`);
  const buffer = fs.readFileSync(videoPath);
  let extracted;
  try {
    extracted = await gpmfExtract(buffer);
  } catch (err) {
    console.error('gpmf-extract error:', err);
    process.exit(1);
  }

  console.log('Parsing telemetry with gopro-telemetry...');
  let telemetry;
  try {
    telemetry = await goproTelemetry(extracted, { stream: ['GPS'] });
  } catch (err) {
    console.error('gopro-telemetry error:', err);
    process.exit(1);
  }

  const outName = `${path.parse(videoPath).name}_telemetry.json`;
  fs.writeFileSync(outName, JSON.stringify(telemetry, null, 2));
  console.log(`Telemetry saved to: ${outName}`);
}

main(); 