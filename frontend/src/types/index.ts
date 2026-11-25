export type UserRole = 'user' | 'admin';

export interface User {
  id: string;
  nickname: string;
  avatar_url?: string;
  phone?: string | null;
  username?: string | null;
  email?: string | null;
  roles: UserRole[];
  created_at: string;
  updated_at: string;
  account: Account;
}

export interface Account {
  balance_points: number;
  reserve_points: number;
  frozen_points: number;
  total_earned: number;
  total_spent: number;
  reserve_contribution: number;
  pool_total_points: number;
  pool_contributors: number;
}

export interface GpuSpec {
  gpu_model: string;
  vendor: string;
  vram_gb: number;
  peak_tflops: number;
}

export interface Node {
  id: string;
  owner_id: string;
  name: string;
  gpu_model: string;
  vram_gb: number;
  peak_tflops: number;
  gpu_count: number;
  region_province?: string | null;
  region_city?: string | null;
  region_district?: string | null;
  gpu_uuid?: string | null;
  benchmark_tflops?: number | null;
  benchmark_status: 'pending' | 'verified' | 'failed';
  benchmarked_at?: string | null;
  status: 'online' | 'offline' | 'maintenance';
  is_online: boolean;
  last_heartbeat_at?: string | null;
  gpu_utilization?: number | null;
  vram_used_gb?: number | null;
  temp_c?: number | null;
  total_tasks_completed: number;
  total_points_earned: number;
  reputation_score: number;
  created_at: string;
  updated_at: string;
}

export interface NodeDetail extends Node {
  today_tasks: number;
  today_points: number;
}

export interface NodeExecution {
  id: string;
  task_id: string;
  task_no?: string | null;
  attempt_no: number;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  compute_duration_seconds?: number | null;
  compute_points?: number | null;
  platform_fee_rate: number;
  platform_fee_points?: number | null;
  supplier_earnings_points?: number | null;
  error_message?: string | null;
  created_at: string;
}

export interface MarketplaceNode {
  id: string;
  name: string;
  gpu_model: string;
  vram_gb: number;
  peak_tflops: number;
  gpu_count: number;
  region_province?: string | null;
  region_city?: string | null;
  status: 'online' | 'offline' | 'maintenance';
  is_online: boolean;
  gpu_utilization?: number | null;
  vram_used_gb?: number | null;
  total_tasks_completed: number;
  reputation_score: number;
  owner_nickname?: string | null;
  last_heartbeat_at?: string | null;
  created_at: string;
}

export type TaskStatus = 'pending' | 'scheduling' | 'assigned' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface Task {
  id: string;
  task_no: string;
  demander_id: string;
  type: 'inference' | 'training' | 'batch';
  title: string;
  description?: string;
  model_source: string;
  model_id?: string;
  model_file_key?: string;
  model_file_size?: number;
  input_file_key?: string;
  input_file_size?: number;
  batch_size: number;
  total_work_units?: number | null;
  completed_work_units: number;
  docker_image?: string;
  command?: string;
  env_vars: Record<string, string>;
  params: Record<string, unknown>;
  concurrency: number;
  min_concurrency: number;
  max_concurrency?: number | null;
  timeout_minutes: number;
  required_vram_gb: number;
  required_tflops?: number;
  budget_points: number;
  min_settlement_unit: number;
  status: TaskStatus;
  retry_count: number;
  max_retries: number;
  assigned_node_id?: string;
  scheduled_at?: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
  executions?: TaskExecution[];
}

export interface TaskExecution {
  id: string;
  task_id: string;
  node_id: string;
  slice_index: number;
  attempt_no: number;
  completed_work_units: number;
  work_unit_start?: number | null;
  work_unit_end?: number | null;
  status: 'assigned' | 'running' | 'completed' | 'failed' | 'cancelled';
  started_at?: string | null;
  completed_at?: string | null;
  compute_duration_seconds?: number | null;
  compute_points?: number | null;
  logs?: string;
  result_path?: string;
  error_message?: string;
  duration_seconds?: number;
}

export type SettlementRole = 'supplier' | 'demander'

export type SettlementStatus = 'pending' | 'settled' | 'refunding' | 'refunded' | 'reversed'

export interface Settlement {
  id: string;
  settlement_no: string;
  task_id: string;
  task_no?: string | null;
  execution_id: string;
  role: SettlementRole;
  compute_points: number;
  platform_fee_rate: number;
  platform_fee_points: number;
  net_points: number;
  destination_account: string;
  status: SettlementStatus;
  settled_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlatformConfig {
  id: number;
  platform_fee_rate: number;
  min_settlement_unit: number;
  max_task_retries: number;
  node_offline_threshold_minutes: number;
  task_scheduling_timeout_minutes: number;
  settlement_timeout_hours: number;
  reserve_ratio: number;
  max_borrow_ratio: number;
  reserve_interest_ratio: number;
  updated_at: string;
  updated_by?: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data?: T;
  timestamp: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginRequest {
  account: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  nickname?: string;
}

export interface NodeCreateRequest {
  name: string;
  gpu_model: string;
  vram_gb: number;
  peak_tflops: number;
  gpu_count?: number;
  region_province?: string;
  region_city?: string;
  region_district?: string;
  docker_image?: string;
  config_json?: string;
  gpu_uuid?: string;
}

export interface NodeUpdateRequest {
  name?: string;
  gpu_model?: string;
  vram_gb?: number;
  peak_tflops?: number;
  gpu_count?: number;
  region_province?: string;
  region_city?: string;
  region_district?: string;
  docker_image?: string;
  config_json?: string;
  gpu_uuid?: string;
  cached_models?: string[];
}

export interface NodeHeartbeatRequest {
  gpu_util?: number;
  gpu_utilization?: number;
  vram_used_gb?: number;
  temp_c?: number;
  temperature?: number;
  docker_status?: string;
  cached_models?: string[];
}

export interface TaskCreateRequest {
  type: 'inference' | 'training' | 'batch';
  title: string;
  description?: string;
  model_source?: 'platform' | 'upload';
  model_id?: string;
  model_file_key?: string;
  model_file_size?: number;
  input_file_key?: string;
  input_file_size?: number;
  batch_size?: number;
  docker_image?: string;
  command?: string;
  env_vars?: Record<string, string>;
  params?: Record<string, unknown>;
  concurrency?: number;
  min_concurrency?: number;
  max_concurrency?: number | null;
  required_vram_gb: number;
  required_tflops?: number;
  budget_points: number;
  timeout_minutes: number;
}

export interface TaskListQuery {
  page?: number;
  page_size?: number;
  status?: string;
  type?: string;
}

export interface SettlementListQuery {
  page?: number;
  page_size?: number;
  status?: string;
  role?: string;
  start_date?: string;
  end_date?: string;
}

export interface AdminDashboardStats {
  online_nodes: number;
  pending_tasks: number;
  today_fee_points: number;
  fee_rate: number;
}

export interface AdminNodeListItem {
  id: string;
  name: string;
  owner_id: string;
  owner_phone?: string | null;
  gpu_model: string;
  vram_gb: number;
  peak_tflops: number;
  gpu_uuid?: string | null;
  benchmark_tflops?: number | null;
  benchmark_status: 'pending' | 'verified' | 'failed';
  benchmarked_at?: string | null;
  status: 'online' | 'offline' | 'maintenance';
  is_online: boolean;
  last_heartbeat_at?: string | null;
  total_tasks_completed: number;
  total_points_earned: number;
  reputation_score: number;
  created_at: string;
}

export interface AdminTaskListItem {
  id: string;
  task_no: string;
  demander_id: string;
  demander_phone?: string | null;
  type: string;
  status: TaskStatus;
  assigned_node_id?: string | null;
  created_at: string;
}

export interface AdminUserListItem {
  id: string;
  username?: string | null;
  phone?: string | null;
  email?: string | null;
  nickname?: string | null;
  roles: string[];
  is_active: boolean;
  balance_points: number;
  frozen_points: number;
  reserve_points: number;
  total_earned: number;
  total_spent: number;
  created_at: string;
}

export interface AdminAuditLogItem {
  id: string;
  prev_hash?: string | null;
  event_type: string;
  entity_type: string;
  entity_id?: string | null;
  user_id?: string | null;
  payload_json: string;
  hash: string;
  created_at: string;
}

export interface AdminAuditVerifyResult {
  valid: boolean;
  errors: string[];
}

export interface PresignUploadRequest {
  filename: string;
  size: number;
  content_type?: string;
}

export interface PresignUploadResponse {
  object_key: string;
  upload_url: string;
  expires_in: number;
}

export interface UploadConfirmResponse {
  object_key: string;
  exists: boolean;
  size: number;
}

export interface InputConfirmResponse {
  object_key: string;
  manifest_key: string;
  file_count: number;
  file_size: number;
}

export interface PlatformModel {
  id: string;
  name: string;
  framework: string;
  size_bytes: number;
  required_vram_gb: number;
  source: string;
  content_hash?: string;
  minio_key?: string;
  description?: string;
  is_published: boolean;
  created_at: string;
  updated_at: string;
}

export type NotificationType =
  | 'task_completed'
  | 'task_failed'
  | 'task_assigned'
  | 'task_started'
  | 'task_cancelled'
  | 'settlement_paid'
  | 'node_online'
  | 'node_offline'
  | 'system';

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  content: string;
  ref_id?: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationList {
  items: Notification[];
  total: number;
  page: number;
  page_size: number;
}

export interface PoolOverview {
  pool_total_points: number;
  pool_contributors: number;
  total_output_points: number;
  total_interest_points: number;
  last_distributed_at?: string | null;
}

export interface InterestRecord {
  id: string;
  cycle_output_points: number;
  interest_points: number;
  total_reserve_points: number;
  distributed_at: string;
}

export interface InterestAllocation {
  id: string;
  interest_points: number;
  reserve_points_before: number;
  distributed_at: string;
}

export interface BorrowResponse {
  amount_points: number;
  balance_points: number;
  reserve_points: number;
}

export interface BorrowRecord {
  id: string;
  amount_points: number;
  balance_before: number;
  reserve_before: number;
  created_at: string;
}