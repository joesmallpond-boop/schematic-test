import numpy as np, subprocess, json, sys
SR = 48000

def run(x, params, sr=SR, auto=None):
    st = np.stack([x, x], 1).astype(np.float64).ravel()
    st.tofile('/tmp/in.f64')
    import os
    if os.path.exists('/tmp/in.f64.auto.json'):
        os.remove('/tmp/in.f64.auto.json')
    if auto:
        json.dump(auto, open('/tmp/in.f64.auto.json', 'w'))
    r = subprocess.run(['node', 'harness.js', 'dsp.genexpr', '/tmp/in.f64', '/tmp/out.f64', str(sr), json.dumps(params)],
                       capture_output=True, text=True)
    if r.returncode:
        print(r.stderr); sys.exit(1)
    o = np.fromfile('/tmp/out.f64').reshape(-1, 3)
    return o

def db(v): return 20 * np.log10(max(v, 1e-12))

def harmonics(y, f0, sr=SR, n=8):
    y = y[len(y)//2:]
    w = np.hanning(len(y)); Y = np.abs(np.fft.rfft(y * w)); fr = np.fft.rfftfreq(len(y), 1/sr)
    hs = []
    for k in range(1, n+1):
        i = np.argmin(abs(fr - k*f0)); hs.append(Y[max(i-3,0):i+4].max())
    hs = np.array(hs); return 20*np.log10(hs/hs.max()+1e-12)

if __name__ == '__main__':
    t = np.arange(int(SR*1.0))/SR
    sine = 0.3*np.sin(2*np.pi*110*t)
    for name, p in [
        ('bypass all', dict(dist_on=0, boost_on=0)),
        ('dist min gain, no oct, LED', dict(distortion=0, octave=0, clipmode=0, filter=0, amps=1)),
        ('dist max, no oct, Si', dict(distortion=1, octave=0, clipmode=2, filter=0.3, amps=0.6)),
        ('dist max, no oct, OFF', dict(distortion=1, octave=0, clipmode=1, filter=0.3, amps=0.6)),
        ('dist max, no oct, LED', dict(distortion=1, octave=0, clipmode=0, filter=0.3, amps=0.6)),
        ('full octave, mid dist', dict(distortion=0.5, octave=1, clipmode=2, filter=0.3)),
        ('boost only', dict(dist_on=0, boost_on=1, boost=0.5)),
        ('boost only max', dict(dist_on=0, boost_on=1, boost=1)),
        ('everything max', dict(dist_on=1, boost_on=1, boost=1, distortion=1, octave=1, amps=1, clipmode=0)),
    ]:
        o = run(sine, p)
        y = o[:, 0]
        ok = np.all(np.isfinite(o))
        h = harmonics(y, 110)
        print(f'{name:30s} finite={ok} peak={y[SR//2:].max():+.3f}/{y[SR//2:].min():+.3f} rms={db(np.sqrt(np.mean(y[SR//2:]**2))):6.1f}dB  '
              f'LR-diff={np.abs(o[:,0]-o[:,1]).max():.1e} led={o[:,2].max():.2f} H1..6=' + ' '.join(f'{v:5.0f}' for v in h[:6]))
