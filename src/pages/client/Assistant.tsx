import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bot, Mic, MicOff, Plus, Send, Square, Trash2, Volume2, VolumeX } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { ErrorState } from '@/components/QueryState';
import { ApiError } from '@/lib/api/client';
import { assistantApi, type Card, type ChatResult, type Lang, type Message } from '@/lib/api/assistant';
import { browserRecognition, canBrowserSpeak, canRecordAudio, recognizeOnce, speakInBrowser } from '@/lib/speech';
import { useCapabilities, useConversations, useDeleteConversation } from '@/hooks/useAssistant';
import { useQueryClient } from '@tanstack/react-query';

const T = {
  en: { placeholder: 'Ask about places, trips, hotels or bookings…', send: 'Send', hint: 'Try “plan 3 days in Jaipur” or “show my bookings”' },
  hi: { placeholder: 'जगहों, यात्राओं, होटल या बुकिंग के बारे में पूछें…', send: 'भेजें', hint: 'कहकर देखें “जयपुर के लिए 3 दिन का प्लान बनाओ” या “मेरी बुकिंग दिखाओ”' },
};

const cardLink = (c: Card): string | null =>
  c.type === 'destination' ? `/dashboard/destinations/${c.slug}` : c.type === 'itinerary' ? `/dashboard/itineraries/${c.id}` : c.type === 'booking' ? '/dashboard/bookings' : c.type === 'hotel' ? `/dashboard/hotels/${c.slug}` : null;
const cardLabel = (c: Card) => c.name ?? c.title ?? c.reference ?? c.type;

export default function Assistant() {
  const qc = useQueryClient();
  const caps = useCapabilities();
  const convs = useConversations();
  const del = useDeleteConversation();
  const [cid, setCid] = useState<string | undefined>();
  const [lang, setLang] = useState<Lang>('en');
  const [messages, setMessages] = useState<Message[]>([]);
  const [awaiting, setAwaiting] = useState(false);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [speak, setSpeak] = useState(false);
  const [listening, setListening] = useState(false);
  const stopRef = useRef<(() => void) | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  useEffect(() => { endRef.current?.scrollIntoView?.({ behavior: 'smooth' }); }, [messages]);

  const serverStt = !!caps.data?.server_speech_to_text && canRecordAudio();
  const micAvailable = serverStt || !!browserRecognition();
  const speakAvailable = !!caps.data?.server_text_to_speech || canBrowserSpeak();

  const say = async (reply: string, l: Lang) => {
    try {
      if (caps.data?.server_text_to_speech) {
        const blob = await assistantApi.synthesize(reply, l);
        audioRef.current?.pause();
        audioRef.current = new Audio(URL.createObjectURL(blob));
        await audioRef.current.play();
        return;
      }
      throw new Error('server speech unavailable');
    } catch {
      if (canBrowserSpeak()) { speakInBrowser(reply, l); return; }
      setNotice('Could not read the reply aloud. You can still read it here.');
    }
  };

  const send = async (message: string, mode: 'text' | 'voice' = 'text') => {
    const body = message.trim();
    if (!body || sending) return;
    setSending(true); setError(''); setNotice('');
    const mine: Message = { id: `u${Date.now()}`, role: 'user', content: body, language: lang, input_mode: mode, actions: [], cards: [], created_at: new Date().toISOString() };
    setMessages(m => [...m, mine]); setText('');
    try {
      const r: ChatResult = await assistantApi.chat({ message: body, conversation_id: cid, language: lang, input_mode: mode });
      setCid(r.conversation_id); setLang(r.language); setAwaiting(r.awaiting_confirmation);
      setMessages(m => [...m, { id: `a${Date.now()}`, role: 'assistant', content: r.reply, language: r.language, input_mode: 'text', actions: r.actions, cards: r.cards, created_at: new Date().toISOString() }]);
      qc.invalidateQueries({ queryKey: ['assistant-conversations'] });
      if (speak) void say(r.reply, r.language);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'The assistant could not be reached. Please try again.');
    } finally { setSending(false); }
  };

  const open = async (id: string) => {
    try {
      const d = await assistantApi.conversation(id);
      setCid(d.id); setLang(d.language); setMessages(d.messages); setAwaiting(false); setError('');
    } catch (e) { toast.error(e instanceof ApiError ? e.message : 'Could not open the conversation'); }
  };
  const fresh = () => { setCid(undefined); setMessages([]); setAwaiting(false); setError(''); setNotice(''); };

  const mic = async () => {
    if (listening) { stopRef.current?.(); return; }
    setNotice('');
    try {
      setListening(true);
      if (serverStt) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const rec = new MediaRecorder(stream);
        const chunks: Blob[] = [];
        rec.ondataavailable = e => chunks.push(e.data);
        const done = new Promise<void>(res => { rec.onstop = () => res(); });
        stopRef.current = () => rec.stop();
        rec.start();
        await done;
        stream.getTracks().forEach(t => t.stop());
        const t = await assistantApi.transcribe(new Blob(chunks, { type: rec.mimeType || 'audio/webm' }), lang);
        if (!t.text) throw new Error('No speech was recognised');
        setListening(false);
        await send(t.text, 'voice');
      } else {
        const { promise, stop } = recognizeOnce(lang);
        stopRef.current = stop;
        const heard = await promise;
        setListening(false);
        await send(heard, 'voice');
      }
    } catch (e) {
      setNotice(`Voice input didn't work: ${e instanceof Error ? e.message : 'unknown error'}. You can type your message instead.`);
    } finally { setListening(false); stopRef.current = null; }
  };

  const t = T[lang];
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-6 pb-24 lg:pb-0">
      <aside className="space-y-3" aria-label="Conversations">
        <Button className="w-full gap-2" variant="outline" onClick={fresh}><Plus className="w-4 h-4" />New conversation</Button>
        {convs.isError && <ErrorState message="Could not load conversations." onRetry={() => convs.refetch()} />}
        <ul className="space-y-1">
          {convs.data?.items.map(c => (
            <li key={c.id} className={`flex items-center gap-1 rounded-lg ${c.id === cid ? 'bg-primary/10' : ''}`}>
              <button type="button" className="flex-1 text-left text-sm px-3 py-2 truncate" onClick={() => open(c.id)} aria-label={`Open conversation ${c.title}`}>{c.title}</button>
              <Button size="icon" variant="ghost" aria-label={`Delete conversation ${c.title}`} onClick={() => del.mutate(c.id, { onSuccess: () => { if (c.id === cid) fresh(); } })}><Trash2 className="w-4 h-4" /></Button>
            </li>
          ))}
          {convs.data?.items.length === 0 && <li className="text-xs text-muted-foreground px-3">No conversations yet.</li>}
        </ul>
      </aside>

      <section className="space-y-4 min-w-0">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-display font-bold text-foreground flex items-center gap-2"><Bot className="w-6 h-6 text-primary" />Assistant</h1>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Label htmlFor="as-lang" className="text-sm">Language</Label>
              <Select value={lang} onValueChange={v => setLang(v as Lang)}>
                <SelectTrigger id="as-lang" className="w-32"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="en">English</SelectItem><SelectItem value="hi">हिन्दी</SelectItem></SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2"><Switch id="as-speak" checked={speak} disabled={!speakAvailable} onCheckedChange={setSpeak} />
              <Label htmlFor="as-speak" className="text-sm flex items-center gap-1">{speak ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}Read replies aloud</Label></div>
          </div>
        </div>

        <div className="bg-card rounded-xl border border-border/50 shadow-card p-4 h-[26rem] overflow-y-auto space-y-3" role="log" aria-live="polite" aria-label="Conversation">
          {messages.length === 0 && <p className="text-sm text-muted-foreground">{t.hint}</p>}
          {messages.map(m => (
            <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm whitespace-pre-line ${m.role === 'user' ? 'gradient-primary text-primary-foreground' : 'bg-muted text-foreground'}`}>
                {m.content}
                {m.input_mode === 'voice' && m.role === 'user' && <span className="block text-[10px] opacity-80 mt-1">🎤 voice</span>}
                {m.cards.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">{m.cards.map((c, i) => { const to = cardLink(c); return to
                    ? <Link key={i} to={to} className="text-xs underline text-primary">{cardLabel(c)}</Link> : <span key={i} className="text-xs">{cardLabel(c)}</span>; })}</div>
                )}
              </div>
            </div>
          ))}
          {sending && <p className="text-xs text-muted-foreground" role="status">Thinking…</p>}
          <div ref={endRef} />
        </div>

        {awaiting && !sending && (
          <div className="flex items-center gap-3" role="group" aria-label="Confirm change">
            <span className="text-sm text-muted-foreground">Confirm this change?</span>
            <Button size="sm" onClick={() => send(lang === 'hi' ? 'हाँ' : 'yes')}>{lang === 'hi' ? 'हाँ' : 'Yes'}</Button>
            <Button size="sm" variant="outline" onClick={() => send(lang === 'hi' ? 'नहीं' : 'no')}>{lang === 'hi' ? 'नहीं' : 'No'}</Button>
          </div>
        )}
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}

        <form className="flex gap-2" onSubmit={e => { e.preventDefault(); void send(text); }}>
          <Input aria-label="Message" value={text} maxLength={1000} placeholder={t.placeholder} onChange={e => setText(e.target.value)} disabled={sending} />
          <Button type="button" variant={listening ? 'destructive' : 'outline'} size="icon" onClick={mic} disabled={!micAvailable || sending}
            aria-label={listening ? 'Stop listening' : micAvailable ? 'Speak your message' : 'Voice input is not available in this browser'} title={micAvailable ? undefined : 'Voice input is not available in this browser: type instead'}>
            {listening ? <Square className="w-4 h-4" /> : micAvailable ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
          </Button>
          <Button type="submit" className="gradient-primary text-primary-foreground gap-2" disabled={!text.trim() || sending}><Send className="w-4 h-4" />{t.send}</Button>
        </form>
        <p className="text-xs text-muted-foreground">
          Voice: {caps.data ? (caps.data.server_speech_to_text ? `server speech (${caps.data.speech_provider})` : 'browser speech recognition where supported') : 'checking…'}. Text chat always works. The assistant can read and plan, but cancelling or paying for bookings is done on the My Bookings page.
        </p>
      </section>
    </div>
  );
}
