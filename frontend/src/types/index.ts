export interface User {
  id: string;
  email: string;
  display_name: string;
  timezone: string;
}

export interface Subject {
  id: string;
  name: string;
  code: string | null;
  professor: string | null;
  term: string | null;
  color: string;
  description: string | null;
  is_archived: boolean;
}

export interface Task {
  id: string;
  subject_id: string | null;
  title: string;
  description: string | null;
  status: "pending" | "in_progress" | "completed";
  priority: "low" | "normal" | "high" | "urgent";
  due_at: string | null;
  estimated_minutes: number | null;
  sync_due_to_google: boolean;
  completed_at: string | null;
  created_at: string;
  subject?: Subject | null;
}

export interface CalendarEvent {
  id: string;
  subject_id: string | null;
  linked_task_id: string | null;
  title: string;
  description: string | null;
  location: string | null;
  event_type: "class" | "exam" | "assignment" | "academic" | "personal" | "other";
  all_day: boolean;
  start_at: string | null;
  end_at: string | null;
  start_date: string | null;
  end_date: string | null;
  timezone: string;
  origin: "uniflow" | "google" | "ics" | "task";
  sync_to_google: boolean;
  is_read_only: boolean;
  subject?: Subject | null;
}

export interface GoogleStatus {
  configured: boolean;
  connection_status: string;
  account_email: string | null;
  calendar_id: string | null;
  last_synced_at: string | null;
  last_error: string | null;
}

export interface CalendarSource {
  id: string;
  name: string;
  source_type: "url" | "upload";
  last_fetched_at: string | null;
  is_enabled: boolean;
  last_error: string | null;
}

export interface SyncRun {
  id: string;
  provider: string;
  trigger: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  items_created: number;
  items_updated: number;
  items_deleted: number;
  items_unchanged: number;
  error_summary: string | null;
}

export interface NotificationItem {
  id: string;
  notification_type: string;
  title: string;
  body: string;
  webhook_sent: boolean;
  read_at: string | null;
  created_at: string;
}

export interface DashboardData {
  today_events: CalendarEvent[];
  overdue_tasks: Task[];
  upcoming_tasks: Task[];
  weekly_completed: number;
  weekly_pending: number;
  overdue_count: number;
  google_status: GoogleStatus;
  unread_notifications: number;
}
