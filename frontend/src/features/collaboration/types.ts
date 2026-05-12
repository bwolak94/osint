export interface CollabSession {
  id: string;
  investigation_id: string;
  name: string;
  created_by: string;
  participants: Array<{ user: string; role: string; online: boolean }>;
  status: string;
  created_at: string;
  share_link: string;
}

export interface OnlineUser {
  user: string;
  avatar: string;
  current_page: string;
  online: boolean;
}
