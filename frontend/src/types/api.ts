// Mirrors the actual Pydantic schemas in app/schemas/*.py — kept
// hand-in-sync rather than generated, since this is a 3-flow demo
// build, not a full client. Only what these 3 flows actually touch.

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface Dataset {
  id: number
  filename: string
  sheet_name: string | null
  rows: number
  columns: number
  workspace_id: number
  uploaded_at: string
}

export interface DatasetSummary {
  id: number
  filename: string
  sheet_name: string | null
  rows: number
  columns: number
  column_name: string[]
  missing_values: Record<string, number>
  data_types: Record<string, string>
}

export interface UploadSingleResponse {
  message: string
  dataset: {
    id: number
    filename: string
    rows: number
    columns: number
    workspace_id: number
    storage_key: string
    uploaded_at: string
  }
}

export interface UploadMultiResponse {
  message: string
  datasets: Dataset[]
}

export type UploadResponse = UploadSingleResponse | UploadMultiResponse

export interface ColumnMapping {
  id: number
  dataset_id: number
  column_name: string
  display_name: string
  description: string | null
  unit: string | null
  is_metric: boolean
  is_dimension: boolean
  created_at: string
  updated_at: string | null
}

// The AI query response's `data` shape varies by operation — never
// force-fit one interface, render conditionally on what's present
// (see ResultRenderer).
export interface StructuredQueryResult {
  operation: 'groupby' | 'filter' | 'sort' | 'aggregate' | 'correlate'
  records?: Record<string, unknown>[]
  row_count?: number
  column?: string | null
  metric?: string | null
  aggregate?: string
  value?: number
  filter_value?: string | null
  filter_operator?: string
  correlation?: number | null
}

export interface QueryResponse {
  answer: string
  data: StructuredQueryResult
  query_used: Record<string, unknown>
  tokens_used: number
}

export interface JobSubmitResponse {
  task_id: string
  status: string
}

export interface JobResponse {
  task_id: string
  status: 'pending' | 'success' | 'failed' | string
  result: Record<string, unknown> | null
  error: string | null
}

export type PinType = 'dataset_query' | 'join_query' | 'analytics' | 'report'

export interface DashboardPin {
  id: number
  dashboard_id: number
  pinned_by: number
  title: string
  pin_type: PinType
  source_id: number
  query_params: Record<string, unknown>
  last_refreshed_at: string | null
  cached_result: Record<string, unknown> | null
  position: number
  created_at: string
}

export interface Dashboard {
  id: number
  workspace_id: number
  created_by: number
  name: string
  description: string | null
  is_default: boolean
  is_active: boolean
  created_at: string
}

export interface DashboardDetail extends Dashboard {
  pins: DashboardPin[]
}

export type ExportSource = 'query' | 'insights' | 'trends' | 'breakdown'
export type ExportFormat = 'csv' | 'xlsx' | 'pdf'

export interface ExportResult {
  export_id: number
  status: 'success' | 'failed'
  format: ExportFormat
  download_url: string | null
  expires_at: string
  error: string | null
}

export type ScheduleSourceType = 'dataset_query' | 'join_query' | 'report'
export type ScheduleFrequency = 'daily' | 'weekly' | 'monthly'

export interface ScheduledReport {
  id: number
  workspace_id: number
  name: string
  source_type: ScheduleSourceType
  source_id: number
  question: string | null
  export_format: ExportFormat
  frequency: ScheduleFrequency
  day_of_week: number | null
  day_of_month: number | null
  hour: number
  recipients: string[]
  is_active: boolean
  last_run_at: string | null
  next_run_at: string
  created_at: string
}

export interface CreateScheduleRequest {
  name: string
  source_type: ScheduleSourceType
  source_id: number
  question?: string
  export_format: ExportFormat
  frequency: ScheduleFrequency
  day_of_week?: number
  day_of_month?: number
  hour: number
  recipients: string[]
}

export interface ApiErrorBody {
  detail?: string | { msg: string }[]
}
