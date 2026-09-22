import type { Settings, Frame } from "./types";
/** Original synthesized score and effects, all bounded nodes; no external audio downloads. */
export class CombatAudio {
  ctx: AudioContext | null = null;
  master: GainNode | null = null;
  music: GainNode | null = null;
  sfx: GainNode | null = null;
  timer: number | undefined;
  seen = new Set<number>();
  lastTick = 0;
  pan = 0;
  intensity = 0;
  settings: Settings;
  constructor(settings: Settings) {
    this.settings = settings;
  }
  async unlock() {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.master = this.ctx.createGain();
      this.music = this.ctx.createGain();
      this.sfx = this.ctx.createGain();
      this.music.connect(this.master);
      this.sfx.connect(this.master);
      this.master.connect(this.ctx.destination);
      this.configure(this.settings);
    }
    await this.ctx.resume();
  }
  configure(s: Settings) {
    this.settings = s;
    if (this.ctx) {
      this.master!.gain.setTargetAtTime(s.master, this.ctx.currentTime, 0.05);
      this.music!.gain.setTargetAtTime(s.music, this.ctx.currentTime, 0.05);
      this.sfx!.gain.setTargetAtTime(s.effects, this.ctx.currentTime, 0.05);
    }
  }
  tone(
    freq: number,
    duration: number,
    type: OscillatorType = "sine",
    gain = 0.15,
    end?: number,
    target?: GainNode,
  ) {
    if (!this.ctx) return;
    const c = this.ctx,
      o = c.createOscillator(),
      g = c.createGain();
    o.type = type;
    o.frequency.setValueAtTime(freq, c.currentTime);
    if (end)
      o.frequency.exponentialRampToValueAtTime(
        Math.max(20, end),
        c.currentTime + duration,
      );
    g.gain.setValueAtTime(0.001, c.currentTime);
    g.gain.exponentialRampToValueAtTime(gain, c.currentTime + 0.015);
    g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + duration);
    o.connect(g);
    const panner = c.createStereoPanner();
    panner.pan.value = target ? 0 : this.pan;
    g.connect(panner);
    panner.connect(target ?? this.sfx!);
    o.start();
    o.stop(c.currentTime + duration + 0.01);
    o.onended = () => {
      panner.disconnect();
      o.disconnect();
      g.disconnect();
    };
  }
  noise(duration = 0.18, gain = 0.2) {
    if (!this.ctx) return;
    const c = this.ctx,
      b = c.createBuffer(1, c.sampleRate * duration, c.sampleRate),
      d = b.getChannelData(0);
    for (let i = 0; i < d.length; i++)
      d[i] = (Math.random() * 2 - 1) * (1 - i / d.length) ** 2;
    const source = c.createBufferSource(),
      filter = c.createBiquadFilter(),
      g = c.createGain();
    source.buffer = b;
    filter.type = "lowpass";
    filter.frequency.value = 1400;
    g.gain.value = gain;
    source.connect(filter);
    filter.connect(g);
    const panner = c.createStereoPanner();
    panner.pan.value = this.pan;
    g.connect(panner);
    panner.connect(this.sfx!);
    source.start();
    source.onended = () => {
      panner.disconnect();
      source.disconnect();
      filter.disconnect();
      g.disconnect();
    };
  }
  startMusic() {
    if (this.timer !== undefined) return;
    let bar = 0;
    const play = () => {
      if (!this.ctx) return;
      const root = [110, 87.31, 130.81, 98][bar++ % 4];
      [1, 1.5, 2.378].forEach((r) =>
        this.tone(root * r, 3.8, "sine", 0.12, undefined, this.music!),
      );
    };
    play();
    this.timer = window.setInterval(play, 4000);
  }
  stopMusic() {
    if (this.timer !== undefined) clearInterval(this.timer);
    this.timer = undefined;
  }
  consume(frame: Frame) {
    if (frame.tick < this.lastTick) this.seen.clear();
    this.lastTick = frame.tick;
    const intensity =
      frame.phase === "clash" || frame.phase === "finisher"
        ? 1
        : Math.min(...frame.fighters.map((f) => f.health)) < 250
          ? 0.65
          : 0.2;
    if (this.ctx && intensity !== this.intensity) {
      this.intensity = intensity;
      this.music!.gain.setTargetAtTime(
        this.settings.music * (0.7 + 0.3 * intensity),
        this.ctx.currentTime,
        0.25,
      );
    }
    for (const e of frame.events) {
      if (this.seen.has(e.seq)) continue;
      this.seen.add(e.seq);
      this.pan = Math.max(
        -0.8,
        Math.min(
          0.8,
          (e.x ?? frame.fighters.find((f) => f.id === e.player_id)?.x ?? 0) /
            10,
        ),
      );
      if (e.kind === "hit") {
        this.noise(0.13, 0.35);
        this.tone(130, 0.12, "triangle", 0.2, 45);
      }
      if (e.kind === "block") this.tone(260, 0.1, "triangle", 0.13, 100);
      if (e.kind === "parry") {
        this.tone(880, 0.3, "sine", 0.16, 1760);
      }
      if (
        e.kind === "move_start" &&
        ["beam", "bolt", "ultimate"].includes(e.move)
      ) {
        this.tone(
          e.move === "ultimate" ? 80 : 180,
          0.65,
          "sawtooth",
          0.05,
          700,
        );
      }
      if (e.kind === "clash_start" || e.kind === "clash_pulse") {
        this.noise(0.35, 0.18);
        this.tone(80, 0.5, "sawtooth", 0.05, 240);
      }
      if (e.kind === "round_end" || e.kind === "match_end")
        this.tone(330, 0.8, "triangle", 0.12, 165);
    }
    if (this.seen.size > 500)
      this.seen = new Set(frame.events.map((e) => e.seq));
  }
  close() {
    this.stopMusic();
    void this.ctx?.close();
    this.ctx = null;
  }
}
