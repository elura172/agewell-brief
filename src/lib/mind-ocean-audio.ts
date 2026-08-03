// Native Web Audio API Ambient Synthesizer for Mind Ocean
export class MindOceanAudio {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private isMuted: boolean = true;
  private droneOsc1: OscillatorNode | null = null;
  private droneOsc2: OscillatorNode | null = null;
  private isInitialized: boolean = false;

  public init() {
    if (this.isInitialized) return;
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;

    this.ctx = new AudioCtx();
    this.masterGain = this.ctx.createGain();
    this.masterGain.gain.value = 0; // Starts muted by default
    this.masterGain.connect(this.ctx.destination);

    // Deep ambient ocean drone (432 Hz harmonics)
    this.droneOsc1 = this.ctx.createOscillator();
    this.droneOsc1.type = "sine";
    this.droneOsc1.frequency.value = 108; // Sub-octave

    this.droneOsc2 = this.ctx.createOscillator();
    this.droneOsc2.type = "triangle";
    this.droneOsc2.frequency.value = 216; // Harmonic

    const droneGain = this.ctx.createGain();
    droneGain.gain.value = 0.15;

    const filter = this.ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 400;

    this.droneOsc1.connect(droneGain);
    this.droneOsc2.connect(droneGain);
    droneGain.connect(filter);
    filter.connect(this.masterGain);

    this.droneOsc1.start();
    this.droneOsc2.start();
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
      const targetGain = this.isMuted ? 0 : 0.25;
      this.masterGain.gain.linearRampToValueAtTime(targetGain, now + 0.4);
    }
    return this.isMuted;
  }

  public playNodeAudition(freq: number = 432, duration: number = 0.8) {
    if (this.isMuted || !this.ctx || !this.masterGain) return;
    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(freq, now);

    gain.gain.setValueAtTime(0.01, now);
    gain.gain.exponentialRampToValueAtTime(0.18, now + 0.08);
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
