# Original mood beds for news reels, synthesised from scratch (no samples, no licensed audio):
#   python3 bgm.py <mood> seconds out.wav [hit,hit,...]
# moods: tense (사건·사고), somber (희생·참사), mystery (정치·국제·북한), upbeat (스포츠·좋은 소식).
# The warm lo-fi bed stays in lofi.py. Optional hit times add a low thud where the hook text lands.
import sys, wave
import numpy as np

SR = 48000
mood, dur, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
hits = [float(h) for h in sys.argv[4].split(',') if h] if len(sys.argv) > 4 else []
n = int(SR * dur); t = np.arange(n) / SR
rng = np.random.default_rng(7)
mix = np.zeros(n)
hz = lambda m: 440 * 2 ** ((m - 69) / 12)


def add(sig, start):
    i0 = int(start * SR)
    if i0 >= n: return
    L = min(len(sig), n - i0); mix[i0:i0 + L] += sig[:L]


def tone(f, length, amp, kind='piano', attack=.01, decay=2.0):
    tt = np.arange(int(length * SR)) / SR
    env = np.minimum(1, tt / attack) * np.exp(-tt * decay)
    if kind == 'piano':
        s = np.sin(2*np.pi*f*tt) + .4*np.sin(4*np.pi*f*tt)*np.exp(-tt*3) + .15*np.sin(6*np.pi*f*tt)*np.exp(-tt*5)
    elif kind == 'string':  # soft saw: first eight harmonics
        s = sum(np.sin(2*np.pi*f*k*tt) / k for k in range(1, 9)) * .6
    elif kind == 'pad':     # two detuned sines
        s = np.sin(2*np.pi*f*tt) + np.sin(2*np.pi*f*1.006*tt) + .3*np.sin(4*np.pi*f*tt)
        s *= .5
    elif kind == 'bell':    # inharmonic partials
        s = np.sin(2*np.pi*f*tt) + .5*np.sin(2*np.pi*f*2.76*tt)*np.exp(-tt*4) + .25*np.sin(2*np.pi*f*5.4*tt)*np.exp(-tt*8)
    else:                   # pluck
        s = np.sin(2*np.pi*f*tt) + .5*np.sin(4*np.pi*f*tt)*np.exp(-tt*12)
    return amp * env * s


def kick(amp, decay=16):
    tt = np.arange(int(.3 * SR)) / SR
    return amp * np.sin(2*np.pi*(48 + 70*np.exp(-tt*28))*tt) * np.exp(-tt*decay)


def noise(length, amp, decay):
    L = int(length * SR); return amp * rng.standard_normal(L) * np.exp(-np.arange(L) / SR * decay)


def lowpass(x, a):
    y = np.zeros_like(x)
    for i in range(1, len(x)): y[i] = y[i-1] + a * (x[i] - y[i-1])
    return y


def reverb(x, seconds=1.4, wet=.25):
    L = int(seconds * SR); ir = rng.standard_normal(L) * np.exp(-np.arange(L) / SR * 4.5); ir[0] = 0
    N = 1 << int(np.ceil(np.log2(len(x) + L)))
    r = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:len(x)]
    return x + wet * r / max(1e-9, np.abs(r).max()) * np.abs(x).max()


if mood == 'tense':        # D minor, 96 bpm: low drone, string ostinato, heartbeat kick, swell every 4 bars
    beat = 60 / 96; bar = 4 * beat
    add(tone(hz(38), dur + 1, .22, 'pad', attack=1.5, decay=.02) * (1 + .3*np.sin(2*np.pi*.5*np.arange(int((dur+1)*SR))/SR)), 0)
    ost = [62, 62, 65, 62, 69, 62, 65, 64]
    for k in range(int(dur / (beat / 2)) + 1):
        add(tone(hz(ost[k % 8] - 12), beat * .45, .07, 'string', attack=.005, decay=9), k * beat / 2)
    for b in range(int(dur / bar) + 1):
        add(kick(.55), b * bar); add(kick(.35), b * bar + .28)
        if b % 4 == 3: add(noise(bar, .05, -1.2)[::-1] * np.linspace(0, 1, int(bar * SR)), b * bar)
    y = reverb(lowpass(mix, .2), 1.0, .2)
elif mood == 'somber':     # A minor, 62 bpm: slow piano arpeggios over a soft pad
    beat = 60 / 62; bar = 4 * beat
    prog = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]   # Am F C G
    k = 0
    while k * bar < dur:
        ch = prog[k % 4]
        add(tone(hz(ch[0] - 12), bar * 1.2, .12, 'pad', attack=.6, decay=.6), k * bar)
        for j, m in enumerate(ch + [ch[1] + 12]):
            add(tone(hz(m), bar, .14, 'piano', decay=1.2), k * bar + j * beat)
        k += 1
    y = reverb(lowpass(mix, .25), 2.2, .45)
elif mood == 'mystery':    # E minor, 84 bpm: dark pad, sparse bell motif, soft kick on one
    beat = 60 / 84; bar = 4 * beat
    prog = [[52, 55, 59, 62, 66], [48, 52, 55, 59, 64]]               # Em9  Cmaj7
    bells = [76, 74, 71, 79]
    k = 0
    while k * bar < dur:
        for m in prog[k % 2]: add(tone(hz(m - 12), bar * 1.3, .05, 'pad', attack=.8, decay=.4), k * bar)
        add(tone(hz(bells[k % 4]), bar * .8, .08, 'bell', decay=1.8), k * bar + 1.5 * beat)
        add(kick(.3, 12), k * bar)
        add(noise(.05, .02, 70), k * bar + 2 * beat)
        k += 1
    y = reverb(lowpass(mix, .3), 1.8, .35)
elif mood == 'upbeat':     # C major, 112 bpm: bass on the beat, off-beat plucks, claps on 2 and 4
    beat = 60 / 112; bar = 4 * beat
    prog = [[60, 64, 67], [57, 60, 64], [53, 57, 60], [55, 59, 62]]   # C Am F G
    for b in range(int(dur / beat) + 1):
        ch = prog[(b // 4) % 4]
        add(tone(hz(ch[0] - 24), beat * .9, .2, 'pluck', decay=5), b * beat)
        for m in ch: add(tone(hz(m), beat * .4, .06, 'pluck', decay=10), b * beat + beat / 2)
        add(kick(.4), b * beat) if b % 2 == 0 else add(noise(.12, .12, 30), b * beat)
        add(noise(.03, .03, 90), b * beat + beat / 2)
    y = reverb(lowpass(mix, .35), .8, .15)
else:
    raise SystemExit(f"unknown mood {mood!r}: tense, somber, mystery or upbeat")

y += .003 * rng.standard_normal(n)
fade = np.minimum(1, t / .8) * np.minimum(1, (dur - t) / 1.5)
y *= fade; y /= max(1e-6, np.abs(y).max()) / .6
for h in hits:             # same thud recipe as lofi.py
    s0 = int(h * SR)
    if s0 >= n: continue
    L = min(n - s0, int(.6 * SR)); tt = np.arange(L) / SR
    y[s0:s0 + L] += .55 * np.sin(2*np.pi*np.cumsum(40 + 110*np.exp(-tt*12)) / SR) * np.exp(-tt*7) + .12 * rng.standard_normal(L) * np.exp(-tt*45)
y = np.clip(y, -.98, .98)
st = np.stack([y, np.roll(y, 160)], axis=1)
with wave.open(out, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype('<i2').tobytes())
print('ok', mood, out)
