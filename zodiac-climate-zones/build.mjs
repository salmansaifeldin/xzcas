// Draws the 12 zodiac signs on the Sun's yearly path between the Tropic of
// Cancer and the Tropic of Capricorn, each sign inside the zone of its season.
// Writes a self-contained SVG (fonts embedded) and a PNG rendered by Chromium.
//
//   npm install && npm run build

import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { geoCircle, geoGraticule, geoOrthographic, geoPath } from 'd3-geo';
import { chromium } from 'playwright';
import { feature } from 'topojson-client';

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const OUT = path.join(here, 'zodiac-tropics-map');

// ─── Content ────────────────────────────────────────────────────────────────
// Dates are the Sun's entry into each tropical sign in Egypt local time: the
// most frequent calendar day over 2020–2035 (it shifts by ±1 day between years).
const SEASONS = [
  { name: 'الربيع', from: '20 مارس', to: '20 يونيو', icon: 'spring', color: '#5fe08f', motion: 'تتجه الشمس شمالاً نحو مدار السرطان' },
  { name: 'الصيف', from: '21 يونيو', to: '22 سبتمبر', icon: 'summer', color: '#ffc94a', motion: 'تعود الشمس جنوباً نحو خط الاستواء' },
  { name: 'الخريف', from: '23 سبتمبر', to: '20 ديسمبر', icon: 'autumn', color: '#ff8a4c', motion: 'تتجه الشمس جنوباً نحو مدار الجدي' },
  { name: 'الشتاء', from: '21 ديسمبر', to: '19 مارس', icon: 'winter', color: '#62b4ff', motion: 'تعود الشمس شمالاً نحو خط الاستواء' },
];

const SIGNS = [
  { name: 'الحمل', glyph: '\u2648', from: '20 مارس', to: '19 أبريل' },
  { name: 'الثور', glyph: '\u2649', from: '20 أبريل', to: '20 مايو' },
  { name: 'الجوزاء', glyph: '\u264A', from: '21 مايو', to: '20 يونيو' },
  { name: 'السرطان', glyph: '\u264B', from: '21 يونيو', to: '21 يوليو' },
  { name: 'الأسد', glyph: '\u264C', from: '22 يوليو', to: '22 أغسطس' },
  { name: 'العذراء', glyph: '\u264D', from: '23 أغسطس', to: '22 سبتمبر' },
  { name: 'الميزان', glyph: '\u264E', from: '23 سبتمبر', to: '22 أكتوبر' },
  { name: 'العقرب', glyph: '\u264F', from: '23 أكتوبر', to: '21 نوفمبر' },
  { name: 'القوس', glyph: '\u2650', from: '22 نوفمبر', to: '20 ديسمبر' },
  { name: 'الجدي', glyph: '\u2651', from: '21 ديسمبر', to: '19 يناير' },
  { name: 'الدلو', glyph: '\u2652', from: '20 يناير', to: '17 فبراير' },
  { name: 'الحوت', glyph: '\u2653', from: '18 فبراير', to: '19 مارس' },
];

const NOTES = [
  '• الفصول المبيّنة هي فصول نصف الكرة الشمالي (مثل مصر)، وتنعكس في نصف الكرة الجنوبي: فحين يكون عندنا صيف يكون عندهم شتاء.',
  `• أقصى بُعد للشمس عن خط الاستواء ${ltr('23.44°')} بسبب ميل محور الأرض، لذلك لا تتعامد الشمس أبداً على أي مكان شمال مدار السرطان أو جنوب مدار الجدي.`,
  '• سُمّي المداران بهذين الاسمين لأن الشمس تدخل برج السرطان عند الانقلاب الصيفي، وتدخل برج الجدي عند الانقلاب الشتوي.',
  `• كل برج يشغل ${ltr('30°')} من دائرة البروج (مسار الشمس الظاهري بين النجوم)، والتواريخ تقريبية وقد تتغير يوماً واحداً من سنة لأخرى.`,
];

// Aswan is at 24.09°N, about 70 km north of the Tropic of Cancer.
const DID_YOU_KNOW = [
  'يمر مدار السرطان جنوب مدينة أسوان بنحو 70 كم، لذلك تكاد الشمس تتعامد فوقها ظهر يوم 21 يونيو،',
  'وهي الظاهرة التي استخدمها العالم إراتوستينس لقياس محيط الأرض قبل أكثر من 2200 عام.',
];

// ─── Geometry ───────────────────────────────────────────────────────────────
const W = 1920;
const H = 1240;
const XR = 1620; // λ = 0° (March equinox); the year runs right-to-left
const XL = 60; // λ = 360°
const COL = (XR - XL) / 12;
const YEQ = 630;
const TROP = 270; // px between the equator and each tropic
const MARGIN = 78; // temperate strip shown beyond each tropic
const YCAN = YEQ - TROP;
const YCAP = YEQ + TROP;
const YTOP = YCAN - MARGIN;
const YBOT = YCAP + MARGIN;
const LABEL_X = 1880; // right edge of the latitude labels
const EPS = 23.44; // obliquity of the ecliptic, degrees
const RAD = Math.PI / 180;
const BADGE_R = 44;

const xOf = (lam) => XR - (lam / 360) * (XR - XL);
const declination = (lam) => Math.asin(Math.sin(EPS * RAD) * Math.sin(lam * RAD)) / RAD;
const yOf = (dec) => YEQ - (dec / EPS) * TROP;
const r1 = (v) => Math.round(v * 10) / 10;

// ─── Helpers ────────────────────────────────────────────────────────────────
// Keeps numbers such as 23.44° left-to-right inside Arabic text.
function ltr(s) {
  return `\u2066${s}\u2069`;
}

function text(x, y, content, { size = 16, weight = 400, fill = '#fff', anchor = 'middle', dir = 'rtl', opacity, cls } = {}) {
  const attrs = [
    `x="${r1(x)}"`,
    `y="${r1(y)}"`,
    `font-size="${size}"`,
    `font-weight="${weight}"`,
    `fill="${fill}"`,
    `text-anchor="${anchor}"`,
    `direction="${dir}"`,
    opacity == null ? '' : `fill-opacity="${opacity}"`,
    cls ? `class="${cls}"` : '',
  ].filter(Boolean);
  return `<text ${attrs.join(' ')}>${content}</text>`;
}

function glyph(g) {
  return `<tspan class="sym">${g}\uFE0E</tspan>`;
}

function embedFonts(pkg, cssFiles) {
  const dir = path.dirname(require.resolve(`${pkg}/package.json`));
  return cssFiles
    .map((file) =>
      readFileSync(path.join(dir, file), 'utf8').replace(
        /url\(\.\/files\/([\w.-]+\.woff2)\) format\('woff2'\), url\(\.\/files\/[\w.-]+\.woff\) format\('woff'\)/g,
        (_, font) => `url(data:font/woff2;base64,${readFileSync(path.join(dir, 'files', font)).toString('base64')}) format('woff2')`,
      ),
    )
    .join('\n');
}

function mulberry32(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ─── Pieces ─────────────────────────────────────────────────────────────────
const ICONS = {
  spring: (c) =>
    [0, 72, 144, 216, 288].map((a) => `<ellipse cy="-9.5" rx="6.5" ry="10" fill="${c}" transform="rotate(${a})"/>`).join('') +
    '<circle r="5.5" fill="#fff0a8"/>',
  summer: (c) =>
    `<g stroke="${c}" stroke-width="3.2" stroke-linecap="round">` +
    [0, 45, 90, 135, 180, 225, 270, 315].map((a) => `<line y1="-14" y2="-20" transform="rotate(${a})"/>`).join('') +
    `</g><circle r="10" fill="${c}"/>`,
  autumn: (c) =>
    `<g transform="rotate(35)"><path d="M0,-20 C13,-11 13,9 0,16 C-13,9 -13,-11 0,-20 Z" fill="${c}"/>` +
    '<path d="M0,-14 V22 M0,-4 L6,-10 M0,-4 L-6,-10 M0,5 L6,-1 M0,5 L-6,-1" stroke="#5a250c" stroke-width="1.6" stroke-linecap="round" fill="none"/></g>',
  winter: (c) =>
    `<g stroke="${c}" stroke-width="3" stroke-linecap="round" fill="none">` +
    [0, 60, 120, 180, 240, 300].map((a) => `<path d="M0,0 V-19 M0,-12 L-5.5,-17 M0,-12 L5.5,-17" transform="rotate(${a})"/>`).join('') +
    '</g>',
};

function sun(x, y, { scale = 1, opacity = 1 } = {}) {
  const rays = Array.from({ length: 12 }, (_, i) => `<line y1="-16" y2="-23" transform="rotate(${i * 30})"/>`).join('');
  return `<g transform="translate(${r1(x)},${r1(y)}) scale(${scale})" opacity="${opacity}">
    <circle r="34" fill="url(#sunHalo)"/>
    <g stroke="#ffd45a" stroke-width="3" stroke-linecap="round">${rays}</g>
    <circle r="12.5" fill="url(#sunCore)" stroke="#fff6cf" stroke-width="1.2"/>
  </g>`;
}

// Small Earth centred on Egypt's longitude, seen from slightly north of the
// equator, with the tropical belt tinted and the three reference parallels.
function globe(cx, cy, R) {
  const projection = geoOrthographic().rotate([-30, -14]).scale(R).translate([cx, cy]).clipAngle(90).precision(0.2);
  const draw = geoPath(projection).digits(1);
  const topo = JSON.parse(readFileSync(require.resolve('world-atlas/land-110m.json'), 'utf8'));
  const sphere = draw({ type: 'Sphere' });
  const land = draw(feature(topo, topo.objects.land));
  const parallel = (lat) => draw({ type: 'LineString', coordinates: Array.from({ length: 181 }, (_, i) => [-180 + 2 * i, lat]) });
  const polarCap = (lat) => draw(geoCircle().center([0, lat]).radius(90 - EPS).precision(2)());

  // A translucent warm tint turns grey over blue water, so the belt gets its
  // own colours instead: lighter tropical sea and sandy land.
  return `<g>
    <mask id="tropicalBelt"><path d="${sphere}" fill="#fff"/><path d="${polarCap(90)}" fill="#000"/><path d="${polarCap(-90)}" fill="#000"/></mask>
    <circle cx="${cx}" cy="${cy}" r="${R + 10}" fill="url(#globeHalo)"/>
    <path d="${sphere}" fill="url(#ocean)"/>
    <path d="${land}" fill="#58b883"/>
    <g mask="url(#tropicalBelt)">
      <path d="${sphere}" fill="url(#oceanTropical)"/>
      <path d="${land}" fill="#e6c66c"/>
    </g>
    <path d="${draw(geoGraticule().step([30, 30])())}" fill="none" stroke="#ffffff" stroke-opacity=".16"/>
    <path d="${parallel(EPS)}" fill="none" stroke="#fff1bf" stroke-width="1.6" stroke-dasharray="3.5 2.5"/>
    <path d="${parallel(-EPS)}" fill="none" stroke="#fff1bf" stroke-width="1.6" stroke-dasharray="3.5 2.5"/>
    <path d="${parallel(0)}" fill="none" stroke="#ffffff" stroke-width="1.7"/>
    <circle cx="${cx}" cy="${cy}" r="${R}" fill="url(#globeShine)"/>
    <circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="#8fb8ff" stroke-opacity=".55" stroke-width="1.2"/>
  </g>`;
}

// ─── Assemble ───────────────────────────────────────────────────────────────
function buildSvg() {
  const parts = [];
  const push = (s) => parts.push(s);

  const fonts =
    embedFonts('@fontsource/cairo', ['arabic-500.css', 'latin-500.css', 'arabic-700.css', 'latin-700.css', 'arabic-800.css', 'latin-800.css']) +
    embedFonts('@fontsource/noto-sans-symbols', ['symbols-600.css']);

  push(`<svg xmlns="http://www.w3.org/2000/svg" xml:lang="ar" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`);
  push(`<title>البروج الاثنا عشر ومسار الشمس بين مداري السرطان والجدي</title>`);
  push(`<defs>
  <style>
${fonts}
    text { font-family: 'Cairo', sans-serif; }
    .sym { font-family: 'Noto Sans Symbols', 'DejaVu Sans', sans-serif; font-weight: 600; }
  </style>
  <radialGradient id="bg" cx="50%" cy="48%" r="75%">
    <stop offset="0" stop-color="#15275a"/><stop offset=".6" stop-color="#0b1636"/><stop offset="1" stop-color="#060c20"/>
  </radialGradient>
  <linearGradient id="gold" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fff3c9"/><stop offset="1" stop-color="#ffc24a"/>
  </linearGradient>
  <linearGradient id="card" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#0c1736"/><stop offset=".5" stop-color="#13234f"/><stop offset="1" stop-color="#0c1736"/>
  </linearGradient>
  <linearGradient id="tropicGlow" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#ffb347" stop-opacity="0"/><stop offset=".5" stop-color="#ffb347" stop-opacity=".07"/><stop offset="1" stop-color="#ffb347" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="sunHalo">
    <stop offset="0" stop-color="#ffcf4a" stop-opacity=".6"/><stop offset="1" stop-color="#ffcf4a" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="sunCore" cx=".4" cy=".35" r=".75">
    <stop offset="0" stop-color="#fffbe6"/><stop offset=".55" stop-color="#ffd84d"/><stop offset="1" stop-color="#ff9f1c"/>
  </radialGradient>
  <radialGradient id="ocean" cx=".38" cy=".32" r=".8">
    <stop offset="0" stop-color="#3f8fe0"/><stop offset=".7" stop-color="#1b4c96"/><stop offset="1" stop-color="#0d2a5c"/>
  </radialGradient>
  <radialGradient id="oceanTropical" cx=".38" cy=".32" r=".8">
    <stop offset="0" stop-color="#7fe0f2"/><stop offset=".7" stop-color="#2fa4cf"/><stop offset="1" stop-color="#176a96"/>
  </radialGradient>
  <radialGradient id="globeShine" cx=".32" cy=".26" r=".7">
    <stop offset="0" stop-color="#ffffff" stop-opacity=".28"/><stop offset=".5" stop-color="#ffffff" stop-opacity="0"/><stop offset="1" stop-color="#000000" stop-opacity=".25"/>
  </radialGradient>
  <radialGradient id="globeHalo">
    <stop offset=".75" stop-color="#5aa0ff" stop-opacity=".35"/><stop offset="1" stop-color="#5aa0ff" stop-opacity="0"/>
  </radialGradient>
  ${SEASONS.map((s, i) => `<radialGradient id="glow${i}"><stop offset=".62" stop-color="${s.color}" stop-opacity=".4"/><stop offset="1" stop-color="${s.color}" stop-opacity="0"/></radialGradient>`).join('\n  ')}
  <filter id="soft" x="-5%" y="-20%" width="110%" height="140%"><feGaussianBlur stdDeviation="6"/></filter>
  <clipPath id="cardClip"><rect x="${XL}" y="${YTOP}" width="${XR - XL}" height="${YBOT - YTOP}" rx="22"/></clipPath>
</defs>`);

  // Background and stars. Stars stay clear of text: a stray dot next to an
  // Arabic letter reads as one of its dots.
  push(`<rect width="${W}" height="${H}" fill="url(#bg)"/>`);
  const textAreas = [
    [240, 18, 1680, 140], // title
    [50, 144, 1694, 268], // season headers
    [50, 276, 1915, 1232], // chart, labels, date strip and notes
  ];
  const rand = mulberry32(20260321);
  const stars = [];
  for (let i = 0; i < 700; i++) {
    const [x, y, r, o] = [rand() * W, rand() * H, 0.5 + rand() * 1.3, 0.15 + rand() * 0.6];
    if (textAreas.some(([x0, y0, x1, y1]) => x > x0 && x < x1 && y > y0 && y < y1)) continue;
    stars.push(`<circle cx="${r1(x)}" cy="${r1(y)}" r="${r1(r)}" fill-opacity="${r1(o)}"/>`);
  }
  push(`<g fill="#ffffff">${stars.join('')}</g>`);

  // Title
  push(text(W / 2, 76, 'البروج الاثنا عشر ومسار الشمس بين مداري السرطان والجدي', { size: 50, weight: 800, fill: 'url(#gold)' }));
  push(text(W / 2, 122, 'موضع تعامد الشمس على الأرض خلال السنة، وتوزيع البروج على فصول السنة الأربعة', { size: 22, weight: 500, fill: '#b8c5e8' }));

  // Season headers, three sign-columns wide each
  SEASONS.forEach((s, i) => {
    const xr = XR - i * 3 * COL - 6;
    const xl = XR - (i + 1) * 3 * COL + 6;
    const y0 = 150;
    push(`<rect x="${xl}" y="${y0}" width="${xr - xl}" height="110" rx="16" fill="${s.color}" fill-opacity=".12" stroke="${s.color}" stroke-opacity=".55" stroke-width="1.5"/>`);
    push(`<g transform="translate(${xr - 40},${y0 + 38})">${ICONS[s.icon](s.color)}</g>`);
    push(text(xr - 74, y0 + 50, s.name, { size: 32, weight: 800, fill: s.color, anchor: 'start' }));
    push(`<rect x="${xl + 14}" y="${y0 + 20}" width="184" height="34" rx="17" fill="${s.color}" fill-opacity=".16" stroke="${s.color}" stroke-opacity=".45"/>`);
    push(text(xl + 14 + 92, y0 + 43, `${s.from} – ${s.to}`, { size: 17, weight: 700, fill: '#f1f4ff' }));
    push(text(xr - 22, y0 + 91, s.motion, { size: 17, weight: 500, fill: '#d3dcf3', anchor: 'start' }));
  });

  push(globe(1768, 205, 56));

  // Chart card
  push(`<rect x="${XL}" y="${YTOP}" width="${XR - XL}" height="${YBOT - YTOP}" rx="22" fill="url(#card)" fill-opacity=".92"/>`);
  push(`<g clip-path="url(#cardClip)">`);
  push(`<rect x="${XL}" y="${YTOP}" width="${XR - XL}" height="${MARGIN}" fill="#020617" fill-opacity=".38"/>`);
  push(`<rect x="${XL}" y="${YCAP}" width="${XR - XL}" height="${MARGIN}" fill="#020617" fill-opacity=".38"/>`);
  push(`<rect x="${XL}" y="${YCAN}" width="${XR - XL}" height="${2 * TROP}" fill="url(#tropicGlow)"/>`);
  // Season zones: spring/summer north of the equator, autumn/winter south of it
  SEASONS.forEach((s, i) => {
    const y = i < 2 ? YCAN : YEQ;
    push(`<rect x="${XR - (i + 1) * 3 * COL}" y="${y}" width="${3 * COL}" height="${TROP}" fill="${s.color}" fill-opacity=".15"/>`);
  });
  push(`</g>`);
  push(`<rect x="${XL}" y="${YTOP}" width="${XR - XL}" height="${YBOT - YTOP}" rx="22" fill="none" stroke="#2c3f78" stroke-width="1.5"/>`);

  // Grid: sign boundaries and the declinations where the Sun changes sign
  for (let k = 1; k < 12; k++) {
    const x = XR - k * COL;
    const season = k % 3 === 0;
    push(`<line x1="${x}" y1="${YCAN}" x2="${x}" y2="${YCAP}" stroke="#ffffff" stroke-opacity="${season ? 0.26 : 0.08}" stroke-width="${season ? 1.5 : 1}"${season ? ' stroke-dasharray="4 6"' : ''}/>`);
  }
  const minor = [declination(30), declination(60)];
  for (const d of [...minor, ...minor.map((v) => -v)]) {
    const y = yOf(d);
    push(`<line x1="${XL}" y1="${r1(y)}" x2="${XR}" y2="${r1(y)}" stroke="#ffffff" stroke-opacity=".09" stroke-dasharray="2 6"/>`);
    push(text(XR + 10, y + 5, `${Math.abs(d).toFixed(1)}°`, { size: 13, weight: 600, fill: '#8d9cc4', anchor: 'start', dir: 'ltr' }));
  }

  // Hemisphere and climate-zone labels
  push(text(xOf(270), YEQ - TROP / 2 + 16, 'نصف الكرة الشمالي', { size: 48, weight: 800, fill: '#ffffff', opacity: 0.075 }));
  push(text(xOf(90), YEQ + TROP / 2 + 16, 'نصف الكرة الجنوبي', { size: 48, weight: 800, fill: '#ffffff', opacity: 0.075 }));
  push(text(xOf(270), YTOP + 40, 'المنطقة المعتدلة الشمالية (لا تتعامد عليها الشمس)', { size: 16, weight: 600, fill: '#93a4cf' }));
  push(text(xOf(90), YCAP + 50, 'المنطقة المعتدلة الجنوبية (لا تتعامد عليها الشمس)', { size: 16, weight: 600, fill: '#93a4cf' }));

  // Reference latitudes, extended into the label column
  const LINES = [
    { y: YCAN, name: 'مدار السرطان', lat: `${ltr('23.44°')} شمالاً`, sub: 'الحد الشمالي للمنطقة المدارية', stroke: '#f3e3a6', width: 2.6, dash: '14 9', latFill: '#ffd98a' },
    { y: YEQ, name: 'خط الاستواء', lat: ltr('0°'), sub: 'يقسم الأرض إلى شمال وجنوب', stroke: '#ffffff', width: 3.2, dash: '', latFill: '#ffffff' },
    { y: YCAP, name: 'مدار الجدي', lat: `${ltr('23.44°')} جنوباً`, sub: 'الحد الجنوبي للمنطقة المدارية', stroke: '#f3e3a6', width: 2.6, dash: '14 9', latFill: '#ffd98a' },
  ];
  for (const l of LINES) {
    push(`<line x1="${XL}" y1="${l.y}" x2="${LABEL_X}" y2="${l.y}" stroke="${l.stroke}" stroke-width="${l.width}"${l.dash ? ` stroke-dasharray="${l.dash}"` : ''}/>`);
    push(text(LABEL_X, l.y - 12, l.name, { size: 23, weight: 800, anchor: 'start' }));
    push(text(LABEL_X, l.y + 27, l.lat, { size: 18, weight: 700, fill: l.latFill, anchor: 'start' }));
    push(text(LABEL_X, l.y + 51, l.sub, { size: 14.5, weight: 500, fill: '#9fb0d8', anchor: 'start' }));
  }

  // The Sun's path: latitude of the overhead Sun against ecliptic longitude
  const pathD = Array.from({ length: 361 }, (_, lam) => `${lam ? 'L' : 'M'}${r1(xOf(lam))},${r1(yOf(declination(lam)))}`).join(' ');
  push(`<path d="${pathD}" fill="none" stroke="#ffb52e" stroke-width="12" stroke-opacity=".45" filter="url(#soft)"/>`);
  push(`<path d="${pathD}" fill="none" stroke="#ffe39a" stroke-width="4" stroke-linecap="round"/>`);
  // Direction of travel, at the sign boundaries inside each season
  for (const lam of [30, 60, 120, 150, 210, 240, 300, 330]) {
    const dx = -(XR - XL) / 360;
    const dDec = (Math.sin(EPS * RAD) * Math.cos(lam * RAD)) / Math.cos(declination(lam) * RAD);
    const dy = -(TROP / EPS) * dDec;
    const angle = Math.atan2(dy, dx) / RAD;
    push(`<path d="M8,0 L-6,-7 L-3,0 L-6,7 Z" fill="#fff4cc" transform="translate(${r1(xOf(lam))},${r1(yOf(declination(lam)))}) rotate(${r1(angle)})"/>`);
  }

  // Equinoxes and solstices
  push(sun(xOf(0), YEQ));
  push(sun(xOf(90), YCAN));
  push(sun(xOf(180), YEQ));
  push(sun(xOf(270), YCAP));
  push(sun(xOf(360), YEQ, { scale: 0.8, opacity: 0.65 }));
  const event = (x, y, title, color, body, anchor) => {
    push(text(x, y, title, { size: 18, weight: 800, fill: color, anchor }));
    push(text(x, y + 25, body, { size: 15.5, weight: 500, fill: '#c9d4ef', anchor }));
  };
  event(xOf(0) - 22, YEQ + 52, 'الاعتدال الربيعي – 20 مارس', SEASONS[0].color, 'الشمس عمودية على خط الاستواء', 'start');
  event(xOf(180) - 22, YEQ - 67, 'الاعتدال الخريفي – 23 سبتمبر', SEASONS[2].color, 'الشمس عمودية على خط الاستواء', 'start');
  event(xOf(360) + 24, YEQ - 67, '20 مارس: تعود الشمس إلى خط الاستواء', SEASONS[0].color, 'ويبدأ الربيع من جديد', 'end');
  push(
    text(
      xOf(90),
      YTOP + 40,
      `<tspan font-weight="800" fill="${SEASONS[1].color}">الانقلاب الصيفي – 21 يونيو:</tspan> الشمس عمودية على مدار السرطان`,
      { size: 16.5, weight: 600, fill: '#e3e9f8' },
    ),
  );
  push(
    text(
      xOf(270),
      YCAP + 50,
      `<tspan font-weight="800" fill="${SEASONS[3].color}">الانقلاب الشتوي – 21 ديسمبر:</tspan> الشمس عمودية على مدار الجدي`,
      { size: 16.5, weight: 600, fill: '#e3e9f8' },
    ),
  );

  // Sign badges on the Sun's path, kept inside the tropics
  const maxOffset = TROP - BADGE_R - 10;
  SIGNS.forEach((s, i) => {
    const season = SEASONS[Math.floor(i / 3)];
    const lam = 15 + 30 * i;
    const offset = Math.max(-maxOffset, Math.min(maxOffset, YEQ - yOf(declination(lam))));
    const x = xOf(lam);
    const y = YEQ - offset;
    push(`<g transform="translate(${r1(x)},${r1(y)})">
    <circle r="${BADGE_R + 12}" fill="url(#glow${Math.floor(i / 3)})"/>
    <circle r="${BADGE_R}" fill="#0b1533" stroke="${season.color}" stroke-width="3"/>
    <circle r="${BADGE_R - 6}" fill="none" stroke="${season.color}" stroke-opacity=".25"/>
    ${text(0, 1, glyph(s.glyph), { size: 30, weight: 600, fill: season.color })}
    ${text(0, 28, s.name, { size: 17, weight: 800, fill: '#ffffff' })}
  </g>`);
  });

  // Date strip, one cell per sign column
  const y0 = YBOT + 14;
  SIGNS.forEach((s, i) => {
    const season = SEASONS[Math.floor(i / 3)];
    const xl = XR - (i + 1) * COL + 5;
    const cx = XR - (i + 0.5) * COL;
    push(`<rect x="${xl}" y="${y0}" width="${COL - 10}" height="92" rx="12" fill="#101d42" fill-opacity=".92" stroke="${season.color}" stroke-opacity=".35"/>`);
    push(`<line x1="${xl + 14}" y1="${y0 + 1.5}" x2="${xl + COL - 24}" y2="${y0 + 1.5}" stroke="${season.color}" stroke-width="3" stroke-linecap="round"/>`);
    push(text(cx, y0 + 31, `<tspan fill="${season.color}" class="sym">${s.glyph}\uFE0E</tspan> ${s.name}`, { size: 18, weight: 800 }));
    push(text(cx, y0 + 58, `من ${s.from}`, { size: 15, weight: 500, fill: '#c5d0ee' }));
    push(text(cx, y0 + 81, `إلى ${s.to}`, { size: 15, weight: 500, fill: '#c5d0ee' }));
  });

  // Legend, under the latitude labels
  const lx = LABEL_X;
  push(`<path d="M${lx - 48},${y0 + 22} q12,-10 24,0 t24,0" fill="none" stroke="#ffe39a" stroke-width="3.5" stroke-linecap="round"/>`);
  push(text(lx - 60, y0 + 27, 'خط تعامد الشمس', { size: 15, weight: 600, fill: '#d3dcf3', anchor: 'start' }));
  push(sun(lx - 24, y0 + 52, { scale: 0.5 }));
  push(text(lx - 60, y0 + 57, 'اعتدال أو انقلاب', { size: 15, weight: 600, fill: '#d3dcf3', anchor: 'start' }));
  push(`<path d="M8,0 L-6,-7 L-3,0 L-6,7 Z" fill="#fff4cc" transform="translate(${lx - 24},${y0 + 82}) rotate(180)"/>`);
  push(text(lx - 60, y0 + 87, 'اتجاه حركة الشمس', { size: 15, weight: 600, fill: '#d3dcf3', anchor: 'start' }));

  // Notes, and a local fact in the corner they leave free
  NOTES.forEach((n, i) => push(text(LABEL_X, 1124 + i * 29, n, { size: 16, weight: 500, fill: '#a3b2d9', anchor: 'start' })));
  const gold = SEASONS[1].color;
  const boxW = 780;
  push(`<rect x="${XL}" y="1102" width="${boxW}" height="122" rx="14" fill="${gold}" fill-opacity=".07" stroke="${gold}" stroke-opacity=".4"/>`);
  push(`<rect x="${XL + boxW - 5}" y="1116" width="5" height="94" rx="2.5" fill="${gold}"/>`);
  push(text(XL + boxW - 22, 1134, 'هل تعلم؟', { size: 19, weight: 800, fill: gold, anchor: 'start' }));
  DID_YOU_KNOW.forEach((line, i) => push(text(XL + boxW - 22, 1164 + i * 28, line, { size: 16, weight: 500, fill: '#d9e1f5', anchor: 'start' })));

  push('</svg>');
  return parts.join('\n');
}

const svg = buildSvg();
writeFileSync(`${OUT}.svg`, svg);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 2 });
await page.goto(pathToFileURL(`${OUT}.svg`).href);
await page.evaluate(() => document.fonts.ready);
await page.screenshot({ path: `${OUT}.png` });
await browser.close();
console.log(`wrote ${path.relative(process.cwd(), OUT)}.svg and .png`);
