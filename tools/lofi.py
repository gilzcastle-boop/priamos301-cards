# Original lo-fi background bed (soft electric-piano chords, vinyl crackle, brushed beat): python3 lofi.py seconds out.wav
import sys, wave
import numpy as np

SR = 48000
dur = float(sys.argv[1]); out = sys.argv[2]
n = int(SR * dur); t = np.arange(n) / SR
rng = np.random.default_rng(11)
mix = np.zeros(n)

def note(f, start, length, amp):
    i0, i1 = int(start * SR), min(n, int((start + length) * SR))
    if i0 >= n: return
    tt = np.arange(i1 - i0) / SR
    env = np.minimum(1, tt / .03) * np.exp(-tt * 1.6)
    tone = np.sin(2 * np.pi * f * tt) + .35 * np.sin(2 * np.pi * 2 * f * tt) * np.exp(-tt * 4) + .12 * np.sin(2 * np.pi * 3 * f * tt) * np.exp(-tt * 6)
    mix[i0:i1] += amp * env * tone * (1 + .004 * np.sin(2 * np.pi * 5 * tt))

bpm = 76; beat = 60 / bpm; bar = 4 * beat
chords = [[57, 60, 64, 67], [55, 59, 62, 65], [53, 57, 60, 64], [52, 55, 59, 62]]  # Am7 G7 Fmaj7 Em7
hz = lambda m: 440 * 2 ** ((m - 69) / 12)
k = 0
while k * bar < dur:
    ch = chords[k % 4]
    for j, m in enumerate(ch):
        note(hz(m), k * bar + j * .025, bar * 1.1, .11)
    note(hz(ch[0] - 12), k * bar, bar, .16)
    note(hz(ch[2] + 12), k * bar + 2.5 * beat, beat * 1.5, .05)
    k += 1

# brushed kick and hat
for b in range(int(dur / beat) + 1):
    s = int(b * beat * SR)
    if s >= n: break
    if b % 4 in (0, 2):
        L = min(n - s, int(.25 * SR)); tt = np.arange(L) / SR
        mix[s:s + L] += .32 * np.sin(2 * np.pi * (55 + 60 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 14)
    h = int((b + .5) * beat * SR)
    if h < n:
        L = min(n - h, int(.06 * SR)); mix[h:h + L] += .03 * rng.standard_normal(L) * np.exp(-np.arange(L) / SR * 60)

# low-pass (simple one-pole) for a warm, muffled tone
y = np.zeros(n); a = .18
for i in range(1, n): y[i] = y[i - 1] + a * (mix[i] - y[i - 1])
# vinyl crackle and hiss
y += .004 * rng.standard_normal(n)
pops = rng.integers(0, n, int(dur * 6)); y[pops] += rng.uniform(-.15, .15, len(pops))
# fade in/out and normalise
fade = np.minimum(1, t / 1.0) * np.minimum(1, (dur - t) / 1.5)
y *= fade; y /= max(1e-6, np.abs(y).max()) / .6
st = np.stack([y, np.roll(y, 120)], axis=1)
with wave.open(out, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype('<i2').tobytes())
print('ok', out)
