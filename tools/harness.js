// Minimal GenExpr -> JS transpiler for offline testing of the codebox.
// Usage: node harness.js dsp.genexpr in.f64 out.f64 sr '{"param":val,...}' [n_channels_in=2]
const fs = require('fs');
const [,, file, inF, outF, srS, paramsJson] = process.argv;
let src = fs.readFileSync(file, 'utf8');
src = src.replace(/\/\/.*$/gm, '');

const decls = [];
src = src.replace(/^\s*History\s+(\w+)\(([^)]*)\);/gm, (m, n, v) => { decls.push(`var ${n} = ${v || 0};`); return ''; });
const params = {};
src = src.replace(/^\s*Param\s+(\w+)\(([^,)]*)[^)]*\);/gm, (m, n, v) => { params[n] = parseFloat(v); return ''; });

// pull function definitions:  name(args) { ... }   at column 0
const funcs = [];
let body = '';
let i = 0;
const re = /^([A-Za-z_]\w*)\(([^)]*)\)\s*\{/gm;
let m, last = 0;
while ((m = re.exec(src)) !== null) {
  body += src.slice(last, m.index);
  let depth = 0, j = m.index + m[0].length - 1;
  for (; j < src.length; j++) { if (src[j] === '{') depth++; else if (src[j] === '}') { depth--; if (depth === 0) break; } }
  const fbody = src.slice(m.index + m[0].length, j);
  // declare locals inside function
  const locals = new Set();
  fbody.replace(/(^|[;{\s])([A-Za-z_]\w*)\s*=(?!=)/g, (mm, p, n) => locals.add(n));
  m[2].split(',').map(s => s.trim()).forEach(a => locals.delete(a));
  funcs.push(`function ${m[1]}(${m[2]}) { ${locals.size ? 'var ' + [...locals].join(',') + ';' : ''} ${fbody} }`);
  last = j + 1;
  re.lastIndex = j + 1;
}
body += src.slice(last);

const hist = new Set(decls.map(d => d.split(' ')[1]));
const bl = new Set();
body.replace(/(^|[;{\s(])([A-Za-z_]\w*)\s*=(?!=)/g, (mm, p, n) => { if (!hist.has(n) && !(n in params) && !/^out\d$/.test(n)) bl.add(n); });
const P = Object.assign({}, params, JSON.parse(paramsJson || '{}'));
const prelude = `
var abs=Math.abs, exp=Math.exp, log=Math.log, sqrt=Math.sqrt, tan=Math.tan, pow=Math.pow, floor=Math.floor;
var min=Math.min, max=Math.max; function clamp(x,a,b){return x<a?a:(x>b?b:x);}
var pi=Math.PI, twopi=2*Math.PI;
`;
const code = prelude + decls.join('\n') + '\n' +
  Object.entries(P).map(([k, v]) => `var ${k} = ${v};`).join('\n') + '\n' +
  funcs.join('\n') + `
function setter(setp){ ${Object.keys(P).map(k => `if ('${k}' in setp) ${k} = setp['${k}'];`).join(' ')} }
return function(in1, in2, samplerate, setp) { if (setp) setter(setp); var ${[...bl].join(',')};
${body}
return [out1, out2, out3]; };`;
fs.writeFileSync('/tmp/transpiled.js', code);
const proc = (new Function('var out1,out2,out3;' + code))();
const sr = parseFloat(srS);
const inp = new Float64Array(fs.readFileSync(inF).buffer.slice(0));
const n = inp.length / 2;
const out = new Float64Array(n * 3);
let automation = null;
if (fs.existsSync(inF + '.auto.json')) automation = JSON.parse(fs.readFileSync(inF + '.auto.json'));
const t0 = Date.now();
for (let s = 0; s < n; s++) {
  let setp = null;
  if (automation && automation[s]) setp = automation[s];
  const r = proc(inp[2 * s], inp[2 * s + 1], sr, setp);
  out[3 * s] = r[0]; out[3 * s + 1] = r[1]; out[3 * s + 2] = r[2];
}
fs.writeFileSync(outF, Buffer.from(out.buffer));
console.error(`processed ${n} samples in ${Date.now() - t0} ms (${(n / sr).toFixed(2)} s audio)`);
