import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { assistantApi, type Lang } from '@/lib/api/assistant';

export const useCapabilities = () => useQuery({ queryKey: ['assistant-caps'], queryFn: assistantApi.capabilities, staleTime: 5 * 60_000, retry: false });
export const useConversations = () => useQuery({ queryKey: ['assistant-conversations'], queryFn: () => assistantApi.conversations({ page: 1, page_size: 30 }) });
export const useDeleteConversation = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (id: string) => assistantApi.remove(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['assistant-conversations'] }) });
};
export const useSetConversationLanguage = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (v: { id: string; language: Lang }) => assistantApi.patch(v.id, { language: v.language }), onSuccess: () => qc.invalidateQueries({ queryKey: ['assistant-conversations'] }) });
};
