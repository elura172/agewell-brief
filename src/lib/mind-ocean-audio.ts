// Native Web Audio API Ambient Synthesizer for Mind Ocean (432 Hz & 528 Hz Cellular Light Frequencies)
export class MindOceanAudio {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private isMuted: boolean = true;
  private drone432: OscillatorNode | null = null;
  private drone528: OscillatorNode | null = null;
  private subDrone: OscillatorNode | null = null;
  private lfo: OscillatorNode | null = null;
  private isInitialized: boolean = false;

  public init() {
    if (this.isInitialized) return;
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;

    this.ctx = new AudioCtx();
    this.masterGain = this.ctx.createGain();
    this.masterGain.gain.value = 0; // Starts muted by default
    this.masterGain.connect(this.ctx.destination);

    // 1. Sub-Harmonic Foundation (108 Hz)
    this.subDrone = this.ctx.createOscillator();
    this.subDrone.type = "sine";
    this.subDrone.frequency.value = 108;

    // 2. 432 Hz Natural Tuning Foundation
    this.drone432 = this.ctx.createOscillator();
    this.drone432.type = "sine";
    this.drone432.frequency.value = 432;

    // 3. 528 Hz Cellular DNA Repair & Biophotonic Light Frequency
    this.drone528 = this.ctx.createOscillator();
    this.drone528.type = "triangle";
    this.drone528.frequency.value = 528;

    // 4. Slow LFO Modulation for Organic Wave Swell (0.1 Hz)
    this.lfo = this.ctx.createOscillator();
    this.lfo.type = "sine";
    this.lfo.frequency.value = 0.1;

    const lfoGain = this.ctx.createGain();
    lfoGain.gain.value = 0.08;
    this.lfo.connect(lfoGain);

    const droneGain = this.ctx.createGain();
    droneGain.gain.value = 0.12;
    lfoGain.connect(droneGain.gain);

    const filter = this.ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 650;

    this.subDrone.connect(droneGain);
    this.drone432.connect(droneGain);
    this.drone528.connect(droneGain);

    droneGain.connect(filter);
    filter.connect(this.masterGain);

    this.subDrone.start();
    this.drone432.start();
    this.drone528.start();
    this.lfo.start();

    this.isInitialized = true;
  }

  public toggleMute(): boolean {
    if (!this.isInitialized) this.init();
    if (this.ctx && this.ctx.state === "suspended") {
      this.ctx.resume();
    }

    this.isMuted = !this.isMuted;
    if (this.masterGain && this.ctx) {
      const now = this.ctx.currentTime;
      const targetGain = this.isMuted ? 0 : 0.22;
      this.masterGain.gain.linearRampToValueAtTime(targetGain, now + 0.5);
    }
    return this.isMuted;
  }

  public playNodeAudition(index: number = 0, duration: number = 1.2) {
    if (this.isMuted || !this.ctx || !this.masterGain) return;

    // Solfeggio Biophotonic Scale Frequencies (Hz)
    const solfeggioScale = [432, 528, 639, 741, 852, 963, 1080];
    const freq = solfeggioScale[index % solfeggioScale.length];

    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(freq, now);

    gain.gain.setValueAtTime(0.01, now);
    gain.gain.exponentialRampToValueAtTime(0.2, now + 0.1);
    gain.gain.exponentialRampToValueAtTime(0.001, now + duration);

    osc.connect(gain);
    gain.connect(this.masterGain);

    osc.start(now);
    osc.stop(now + duration + 0.1);
  }

  public getMutedState(): boolean {
    return this.isMuted;
  }
}
