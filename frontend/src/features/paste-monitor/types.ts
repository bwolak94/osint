export interface PasteMention {
  id: string;
  title: string | null;
  snippet: string | null;
  url: string | null;
  date: string | null;
  source: string;
  tags: string[];
}

export interface PasteMonitorResult {
  query: string;
  total: number;
  mentions: PasteMention[];
}
