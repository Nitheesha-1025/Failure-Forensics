export interface User {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  mime_type: string;
  file_size: number;
  processing_status: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: Document[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface PipelineRun {
  id: string;
  document_id: string;
  trace_id: string | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  error_message: string | null;
  created_at: string;
}

export interface PipelineRunListResponse {
  items: PipelineRun[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ApiErrorBody {
  detail?: string | { msg: string; type?: string }[];
}
