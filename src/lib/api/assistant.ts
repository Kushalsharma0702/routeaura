import { apiFetch } from './client';
import type { Page } from './users';

export type Lang = 'en' | 'hi';
export interface Action { type: string; status: 'ok' | 'failed' | 'needs_info' | 'awaiting_confirmation'; detail: Record<string, unknown> }
export interface Card { type: 'destination' | 'itinerary' | 'booking' | 'hotel'; slug?: string; id?: string; name?: string; title?: string; reference?: string; status?: string }
export interface ChatResult {
  conversation_id: string; language: Lang; detected_language: Lang; language_mismatch: boolean; reply: string; actions: Action[]; cards: Card[];
  awaiting_confirmation: boolean; interpreted_by: string;
}
export interface Message { id: string; role: 'user' | 'assistant'; content: string; language: string; input_mode: string; actions: Action[]; cards: Card[]; created_at: string }
export interface Conversation { id: string; title: string; language: Lang; updated_at: string; message_count: number }
export interface ConversationDetail extends Conversation { messages: Message[] }
export interface Capabilities { text_chat: boolean; languages: string[]; speech_provider: string; server_speech_to_text: boolean; server_text_to_speech: boolean; browser_fallback: boolean; max_audio_bytes: number }

export const assistantApi = {
  capabilities: () => apiFetch<Capabilities>('/assistant/capabilities'),
  chat: (body: { message: string; conversation_id?: string; language?: Lang; input_mode?: 'text' | 'voice' }) => apiFetch<ChatResult>('/assistant/chat', { method: 'POST', body }),
  conversations: (p: { page?: number; page_size?: number }) => apiFetch<Page<Conversation>>('/assistant/conversations', { params: { ...p } }),
  conversation: (id: string) => apiFetch<ConversationDetail>(`/assistant/conversations/${id}`),
  patch: (id: string, body: { language?: Lang; title?: string }) => apiFetch<Conversation>(`/assistant/conversations/${id}`, { method: 'PATCH', body }),
  remove: (id: string) => apiFetch<void>(`/assistant/conversations/${id}`, { method: 'DELETE' }),
  transcribe: (audio: Blob, language?: Lang) => {
    const f = new FormData();
    f.append('audio', audio, 'speech.webm');
    if (language) f.append('language', language);
    return apiFetch<{ text: string; language: Lang; provider: string }>('/assistant/voice/transcribe', { method: 'POST', body: f });
  },
  synthesize: (text: string, language: Lang) => apiFetch<Blob>('/assistant/voice/synthesize', { method: 'POST', body: { text, language }, parse: 'blob' }),
};
