export interface KbArticle {
  id: string;
  title: string;
  category: string;
  content: string;
  tags: string[];
  severity_context: string;
  views: number;
  created_at: string;
  updated_at: string;
}

export interface CreateArticleInput {
  title: string;
  category: string;
  content: string;
  tags?: string[];
  severity_context?: string;
}
