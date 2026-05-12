import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { SecureNote } from "./types";
import { toast } from "@/shared/components/Toast";

export function useSecureNotes() {
  return useQuery({
    queryKey: ["secure-notes"],
    queryFn: async () => {
      const res = await apiClient.get<SecureNote[]>("/secure-notes");
      return res.data;
    },
  });
}

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      title: string;
      content: string;
      tags: string[];
      investigation_id?: string;
    }) => {
      const res = await apiClient.post<SecureNote>("/secure-notes", data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["secure-notes"] });
      toast.success("Note saved securely");
    },
  });
}

export function useDecryptNote() {
  return useMutation({
    mutationFn: async (noteId: string) => {
      const res = await apiClient.get<{ content: string }>(
        `/secure-notes/${noteId}/decrypt`
      );
      return res.data.content;
    },
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/secure-notes/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["secure-notes"] });
      toast.success("Note deleted");
    },
  });
}
