export type Role = 'admin' | 'manager' | 'viewer';
export type User = { id: number; username: string; display_name: string; role: Role };
export type TV = {
  tv_id: string;
  name: string;
  ip: string;
  enabled: boolean;
  timezone: string;
  daily_limit_minutes: number | null;
  weekly_limit_minutes: number | null;
  schedule: Record<string, string[][]>;
};
export type TVStatus = {
  allowed: boolean;
  reason: string;
  within_schedule: boolean;
  used_today_seconds: number;
  used_week_seconds: number;
  bonus_remaining_seconds: number;
  bonus_granted_seconds: number;
  bonus_consumed_seconds: number;
  online_observation: { state: string; confirmed_online: boolean; last_checked_at: string | null };
};
