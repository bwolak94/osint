export interface SecureNote {
  id: string;
  title: string;
  content_encrypted: string;
  tags: string[];
  investigation_id: string | null;
  is_encrypted: boolean;
  created_at: string;
  updated_at: string;
  word_count: number;
}
