"""Generates the GenExpr (gen~ codebox) DSP for the pedal, straight from the schematic values."""
import re
import numpy as np
from scipy import signal

import os
OS = int(os.environ.get('OS', '8'))
SOS = signal.ellip(10, 0.05, 100, 0.9 / OS, output='sos')

HEADER = r"""// =====================================================================
//  THE DOOM BOX  —  component-level model of the schematic
//  Octave-up (Q3/Q4 splitter + D2/D3) > LM308 RAT stage > J201 buffer
//  > BS170 MOSFET boost.  8x oversampled, mono like the pedal
//  (L+R summed in, same signal out both sides).  1.0 = 1 volt.
// =====================================================================

Param octave(0.5, min=0, max=1);     // OCTAVE 50KB
Param distortion(0.5, min=0, max=1); // DIST 100KA
Param filter(0.3, min=0, max=1);     // FILTER 100KA
Param amps(0.6, min=0, max=1);       // AMPS 100KA
Param boost(0.5, min=0, max=1);      // BOOST 100KA
Param clipmode(0, min=0, max=2);     // SW1: 0 = D4/D6 LED + D5, 1 = off, 2 = D7/D8
Param dist_on(1, min=0, max=1);      // footswitch 1
Param boost_on(0, min=0, max=1);     // footswitch 2

// ---------- pot tapers ----------
taperA(t) {
    return (exp(4.394 * t) - 1) / (exp(4.394) - 1);
}

// smooth limiter used for transistor saturation / op-amp rails
sclip(v, L) {
    q = v / L;
    q2 = q * q;
    return v / sqrt(sqrt(1 + q2 * q2));
}

// tan() series, accurate to <0.1% for the arguments used inside the loop
ftan(x) {
    x2 = x * x;
    return x * (1 + x2 * (0.33333333 + x2 * (0.13333333 + x2 * 0.05396825)));
}

// J201 source follower, gate referenced to 0 V via 1M, Rs = 10k
// Idss 0.6 mA, Vp -0.8 V (square law). Returns source voltage.
jfet(vg) {
    k = 6.0;
    vp = -0.8;
    vs = 0;
    if (vg > vp) {
        w = (vp + sqrt(vp * vp - 4 * k * (vp - vg))) / (2 * k);
        vs = k * w * w;
    }
    return min(vs, 8.5);
}

// BS170 drain current, Rd 10k / Rs 470R, 9 V. Level-1 model, K 0.05, Vth 2.1
mosid(vg) {
    K = 0.05;
    RS = 470;
    RT = 10470;
    a = vg - 2.1;
    idr = 0;
    if (a > 0) {
        y = (sqrt(1 + 4 * RS * K * a) - 1) / (2 * RS * K);
        idr = K * y * y;
        vds = 9 - RT * idr;
        if (vds < y) {
            p0 = 9;
            p1 = -RT;
            q0 = 2 * a - 9;
            q1 = RT - 2 * RS;
            qa = K * p1 * q1;
            qb = K * (p0 * q1 + p1 * q0) - 1;
            qc = K * p0 * q0;
            dd = sqrt(max(qb * qb - 4 * qa * qc, 0));
            r1 = (-qb - dd) / (2 * qa);
            r2 = (-qb + dd) / (2 * qa);
            lim = 9 / RT;
            idr = lim;
            if (r2 >= 0 && r2 <= lim) { idr = r2; }
            if (r1 >= 0 && r1 <= lim) { idr = min(idr, r1); }
        }
    }
    return idr;
}

mosvd(vg) {
    return 9 - 10000 * mosid(vg);
}

// one-pole TPT coefficient
tptg(fc, sr) {
    return tan(pi * min(fc, 0.45 * sr) / sr);
}
"""

STATE_INIT = {
    'c2': 0, 'c3': 0, 'c10': 0, 'c9': 0, 'c7': 0, 'c5': 0, 'h1': 0, 'h2': 0,
    'lf': 0, 'gbw': 0, 'yprev': 0, 'flt': 0, 'c19': 0, 'c20': 0, 'c22': 0,
    'vg': 2.3901877, 'c23': 4.7803755,
}


def channel_states(c):
    names = [f'{k}_{c}' for k in STATE_INIT]
    for d in ('up', 'dn'):
        for i in range(len(SOS)):
            names += [f'{d}{i}a_{c}', f'{d}{i}b_{c}']
    return names


def biquads(c, d, xin, xout):
    lines = [f'        bq = {xin};']
    for i, row in enumerate(SOS):
        b0, b1, b2, a0, a1, a2 = [float(v) for v in row]
        za, zb = f'l{d}{i}a_{c}', f'l{d}{i}b_{c}'
        lines += [
            f'        by = {b0!r} * bq + {za};',
            f'        {za} = {b1!r} * bq - ({a1!r}) * by + {zb};',
            f'        {zb} = {b2!r} * bq - ({a2!r}) * by;',
            f'        bq = by;',
        ]
    lines.append(f'        {xout} = bq;')
    return '\n'.join(lines)


def hpf(state, x, g, out):
    # TPT one-pole high-pass; state is the low-pass integrator
    return (f'        tv = ({x} - {state}) * ({g} / (1 + {g}));\n'
            f'        tl = tv + {state};\n'
            f'        {state} = tl + tv;\n'
            f'        {out} = {x} - tl;')


def lpf(state, x, g, out):
    return (f'        tv = ({x} - {state}) * ({g} / (1 + {g}));\n'
            f'        tl = tv + {state};\n'
            f'        {state} = tl + tv;\n'
            f'        {out} = tl;')


def channel_block(c, inp, outv):
    L = lambda n: f'l{n}_{c}'
    s = []
    s.append(f'    // ================= channel {c} =================')
    for n in channel_states(c):
        s.append(f'    l{n} = {n};')
    s.append(f'    xin_{c} = {inp};')
    s.append(f'    yo_{c} = 0;')
    s.append(f'    for (i = 0; i < {OS}; i += 1) {{')
    s.append(f'        xu = (i == 0) ? {OS} * xin_{c} : 0;')
    s.append(biquads(c, 'up', 'xu', 'x'))
    s.append(f"""
        // ---- Q1 J201 input buffer (C2/R3 coupling, gate at 0 V) ----
{hpf(L('c2'), 'x', 'g_c2', 'xg')}
        q1 = jfet(xg) - VS0;

        // clean leg: C3 into OCTAVE pot
{hpf(L('c3'), 'q1', 'g_c3', 'clean')}

        // ---- octave leg: C10 > Q4 (gain -R16/(R17+re)) > Q3 splitter ----
{hpf(L('c10'), 'q1', 'g_c10', 'xb')}
        sv = -8.67 * xb;
        sv = (sv > 0) ? sclip(sv, 1.05) : sclip(sv, 6.9);
        // C9 / C8 into 100k, emitter (+0.96) and collector (-0.95) outputs
{hpf(L('c9'), 'sv', 'g_c9', 'sh')}
        ea = 0.96 * sh;
        eb = -0.95 * sh;
        // D3 / D2 diode-OR (full wave) into Q2 follower
        dab = abs(ea - eb);
        rect = max(ea, eb) - 0.031399;
        if (dab < 0.5) {{ rect = rect + 0.0453 * log(1 + exp(-dab / 0.0453)); }}
        rect = sclip(rect, 5.0);
{hpf(L('c7'), 'rect', 'g_c7', 'oct')}

        // OCTAVE 50KB blend (wiper between C3 and C7)
        bl = clean + (oct - clean) * p_oct;

        // ---- LM308 non-inverting stage ----
{hpf(L('c5'), 'bl', 'g_c5', 'vp')}
{hpf(L('h1'), 'vp', 'g_h1', 'hp1')}
{hpf(L('h2'), 'vp', 'g_h2', 'hp2')}
        inner = rd / 560 * hp1 + rd / 47 * hp2;
{lpf(L('lf'), 'inner', 'g_lf', 'lfo')}
        yi = vp + lfo;
        // finite gain-bandwidth (30p compensation)
{lpf(L('gbw'), 'yi', 'g_gbw', 'yg')}
        yg = sclip(yg, 3.5);
        // slew rate 0.3 V/us
        yop = {L('yprev')} + clamp(yg - {L('yprev')}, -slew, slew);
        {L('yprev')} = yop;

        // ---- R23 1k into SW1 diode network ----
        vd = yop;
        gd = 0;
        if (cmode != 1) {{
            ux = yop;
            vd = 0;
            if (ux > 0) {{ vd = min(ux, vtp * log(ux / (1000 * isp) + 1)); }}
            if (ux < 0) {{ vd = max(ux, -vtn * log(-ux / (1000 * isn) + 1)); }}
            for (k = 0; k < 5; k += 1) {{
                if (vd >= 0) {{
                    e1 = exp(vd / vtp);
                    idd = isp * (e1 - 1);
                    gd = isp / vtp * e1;
                }} else {{
                    e1 = exp(-vd / vtn);
                    idd = -isn * (e1 - 1);
                    gd = isn / vtn * e1;
                }}
                vd = vd - (vd + 1000 * idd - ux) / (1 + 1000 * gd);
            }}
            e2 = 1;
            if (vd >= 0) {{
                gd = isp / vtp * exp(vd / vtp);
            }} else {{
                e2 = exp(-vd / vtn);
                gd = isn / vtn * e2;
            }}
            if (cmode == 0) {{ ledi = max(ledi, isn * (e2 - 1)); }}
        }}

        // ---- FILTER: (R_src + FILTER + R24 1k5) into C18 3n3 ----
        rtot = 1000 / (1 + 1000 * gd) + rf + 1500;
        gfl = ftan(pi / (twopi * rtot * 3.3e-9 * sr4));
{lpf(L('flt'), 'vd', 'gfl', 'fo')}

        // ---- C19 > Q5 J201 output buffer > C20 > AMPS ----
{hpf(L('c19'), 'fo', 'g_c19', 'q5g')}
        q5 = jfet(q5g) - VS0;
{hpf(L('c20'), 'q5', 'g_c20', 'dout')}
        dout = dout * a_amps;

        // footswitch 1 (true bypass)
        bin = x + (dout - x) * dm;

        // ---- BS170 boost: R28 1k + C22 1u, R29 470k drain->gate, R30 470k ----
        rsrc = 1000 + dm * 100000 * a_amps * (1 - a_amps);
{hpf(L('c22'), 'bin', 'g_c22', 'bu')}
        bo = 0;
        if (bm > 0.00001) {{
            ug = VG0 + bu;
            vg = {L('vg')};
            for (k = 0; k < 3; k += 1) {{
                f0 = (ug - vg) / rsrc + (mosvd(vg) - vg) / 470000 - vg / 470000;
                f1 = (ug - vg - 0.0001) / rsrc + (mosvd(vg + 0.0001) - vg - 0.0001) / 470000 - (vg + 0.0001) / 470000;
                dfd = (f1 - f0) / 0.0001;
                vg = clamp(vg - f0 / dfd, -9, 18);
            }}
            {L('vg')} = vg;
            vdr = mosvd(vg);
{hpf(L('c23'), 'vdr', 'g_c23', 'bo')}
        }}
        bo = bo * a_boost;

        // footswitch 2
        yy = bin + (bo - bin) * bm;
""")
    s.append(biquads(c, 'dn', 'yy', f'yo_{c}'))
    s.append('    }')
    for n in channel_states(c):
        s.append(f'    {n} = l{n};')
    s.append(f'    {outv} = yo_{c};')
    return '\n'.join(s)


def build():
    out = [HEADER]
    out.append('// ---------- state ----------')
    out += ['History sm_oct(0.5);', 'History sm_dist(0.5);', 'History sm_flt(0.3);',
            'History sm_amps(0.6);', 'History sm_boost(0.5);', 'History sm_dm(1);',
            'History sm_bm(0);', 'History last_rd(-1);', 'History fc_gbw(1000);',
            'History ledpk(0);']
    for c in ('L',):
        for n in channel_states(c):
            base = n.rsplit('_', 1)[0]
            init = STATE_INIT.get(base, 0)
            out.append(f'History {n}({init});')
    out.append(f'OSF = {OS};')
    out.append(r"""
// ---------- per-sample control (base rate) ----------
VS0 = 0.5563859006490657;
VG0 = 2.3901877380900185;
sr4 = samplerate * OSF;
sk = 1 - exp(-1 / (0.02 * samplerate));
fk = 1 - exp(-1 / (0.004 * samplerate));
p_oct = sm_oct + (octave - sm_oct) * sk;
p_dist = sm_dist + (distortion - sm_dist) * sk;
p_flt = sm_flt + (filter - sm_flt) * sk;
p_amps = sm_amps + (amps - sm_amps) * sk;
p_boost = sm_boost + (boost - sm_boost) * sk;
dm = sm_dm + ((dist_on > 0.5) - sm_dm) * fk;
bm = sm_bm + ((boost_on > 0.5) - sm_bm) * fk;
sm_oct = p_oct;
sm_dist = p_dist;
sm_flt = p_flt;
sm_amps = p_amps;
sm_boost = p_boost;
sm_dm = dm;
sm_bm = bm;

rd = 100000 * taperA(p_dist) + 1;
rf = 100000 * taperA(p_flt);
a_amps = taperA(p_amps);
a_boost = taperA(p_boost);
cmode = floor(clamp(clipmode, 0, 2) + 0.5);

// closed-loop bandwidth of the LM308 (GBW 1 MHz with 30p) for this DIST setting
fg = fc_gbw;
f = 0;
j = 0;
w = 0; zd = 0; zr = 0; zi = 0; t1 = 0; t2 = 0; yr = 0; yim = 0; gr = 0; gi = 0;
if (abs(rd - last_rd) > 0.5) {
    f = max(fg, 10);
    for (j = 0; j < 24; j += 1) {
        w = twopi * f;
        zd = 1 + (w * rd * 1e-10) * (w * rd * 1e-10);
        zr = rd / zd;
        zi = -w * rd * rd * 1e-10 / zd;
        t1 = w * 560 * 4.7e-6;
        t2 = w * 47 * 2.2e-6;
        yr = (w * 4.7e-6 * t1) / (1 + t1 * t1) + (w * 2.2e-6 * t2) / (1 + t2 * t2);
        yim = (w * 4.7e-6) / (1 + t1 * t1) + (w * 2.2e-6) / (1 + t2 * t2);
        gr = 1 + zr * yr - zi * yim;
        gi = zr * yim + zi * yr;
        f = sqrt(f * 1000000 / sqrt(gr * gr + gi * gi));
    }
    fg = f;
    last_rd = rd;
    fc_gbw = fg;
}

g_c2 = tptg(1.5915, sr4);
g_c3 = tptg(3.1831, sr4);
g_c10 = tptg(37.273, sr4);
g_c9 = tptg(15.915, sr4);
g_c7 = tptg(3.1831, sr4);
g_c5 = tptg(7.2343, sr4);
g_h1 = tptg(60.469, sr4);
g_h2 = tptg(1539.2, sr4);
g_lf = tptg(1 / (twopi * rd * 1e-10), sr4);
g_gbw = tptg(fg, sr4);
g_c19 = tptg(7.2343, sr4);
g_c20 = tptg(1.5915, sr4);
g_c22 = tptg(6.0, sr4);
g_c23 = tptg(0.15915, sr4);
slew = 300000 / sr4;

// SW1 diode sets: (Is, n*Vt) for + and - current directions
isp = 2.52e-9;
vtp = 0.0452892;
isn = 2.52e-9;
vtn = 0.0452892;
if (cmode == 0) {
    isn = 7.286786306625592e-14;
    vtn = 0.0969892;
}
ledi = 0;
""")
    chans = channel_block('L', '0.5 * (in1 + in2)', 'oL')
    temps = sorted(set(re.findall(r'^\s+([A-Za-z_]\w*)\s*=(?!=)', chans, re.M)))
    out.append('// temporaries')
    hist = set(channel_states('L'))
    temps = [t for t in temps if t not in hist and not (t.startswith('l') and t[1:] in hist)]
    out.append('\n'.join(f'{t} = 0;' for t in temps + ['i', 'k']))
    out.append(chans)
    out.append(r"""
// D6 glow (peak hold with ~60 ms release)
lb = clamp(ledi / 0.002, 0, 1);
lp = max(lb, ledpk * exp(-1 / (0.06 * samplerate)));
ledpk = lp;

out1 = oL;
out2 = oL;
out3 = lp * dm;
""")
    return '\n'.join(out)


if __name__ == '__main__':
    open('dsp.genexpr', 'w').write(build())
    print('ok', len(build()))
