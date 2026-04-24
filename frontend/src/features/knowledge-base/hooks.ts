import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";
import type { KbArticle, CreateArticleInput } from "./types";

export function useKbArticles(search?: string, category?: string) {
  return useQuery({
    queryKey: ["kb-articles", search, category],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (category) params.set("category", category);
      const res = await apiClient.get<KbArticle[]>(`/knowledge-base/articles?${params}`);
      return res.data;
    },
  });
}

export function useCreateArticle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateArticleInput) => {
      const res = await apiClient.post<KbArticle>("/knowledge-base/articles", data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["kb-articles"] });
      toast.success("Article created");
    },
    onError: () => toast.error("Failed to create article"),
  });
}
