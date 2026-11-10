/** Thin wrappers over the browser's speech APIs (used when the server has no speech provider). */
import type { Lang } from '@/lib/api/assistant';

interface RecognitionEvent { results: ArrayLike<ArrayLike<{ transcript: string }>> }
interface Recognition {
  lang: string; interimResults: boolean; maxAlternatives: number;
  onresult: ((e: RecognitionEvent) => void) | null; onerror: ((e: { error: string }) => void) | null; onend: (() => void) | null;
  start: () => void; stop: () => void; abort: () => void;
}
type RecognitionCtor = new () => Recognition;

export const LOCALE: Record<Lang, string> = { en: 'en-IN', hi: 'hi-IN' };

export function browserRecognition(): RecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}
export const canBrowserSpeak = () => typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined';
export const canRecordAudio = () => typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined';

export function speakInBrowser(text: string, lang: Lang): void {
  const u = new SpeechSynthesisUtterance(text);
  u.lang = LOCALE[lang];
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

export function recognizeOnce(lang: Lang): { promise: Promise<string>; stop: () => void } {
  const Ctor = browserRecognition();
  if (!Ctor) throw new Error('Speech recognition is not supported in this browser');
  const rec = new Ctor();
  rec.lang = LOCALE[lang];
  rec.interimResults = false;
  rec.maxAlternatives = 1;
  const promise = new Promise<string>((resolve, reject) => {
    let got = '';
    rec.onresult = e => { got = e.results[0]?.[0]?.transcript ?? ''; };
    rec.onerror = e => reject(new Error(e.error === 'not-allowed' ? 'Microphone permission was denied' : `Speech recognition error: ${e.error}`));
    rec.onend = () => (got ? resolve(got) : reject(new Error('No speech was recognised')));
    rec.start();
  });
  return { promise, stop: () => rec.stop() };
}
