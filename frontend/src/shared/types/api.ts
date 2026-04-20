export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  has_next: boolean;
  next_cursor?: string | null;
}

export interface ApiErrorResponse {
  detail: string;
  status_code?: number;
}

export interface MessageResponse {
  message: string;
}
