import { HttpService } from './HttpService';

export interface ScheduleException {
  id: number;
  tv_id: string;
  name: string;
  start_date: string;
  end_date: string;
  windows: [string, string][];
}

export interface NewScheduleException {
  name: string;
  start_date: string;
  end_date: string;
  windows: [string, string][];
}

export class ScheduleExceptionService {
  private static path(tvId: string) {
    return `/api/tvs/${encodeURIComponent(tvId)}/exceptions`;
  }

  static list(tvId: string) {
    return HttpService.request<ScheduleException[]>(this.path(tvId));
  }

  static create(tvId: string, payload: NewScheduleException) {
    return HttpService.request<ScheduleException[]>(this.path(tvId), 'POST', payload);
  }

  static remove(tvId: string, exceptionId: number) {
    return HttpService.request<{ ok: boolean }>(`${this.path(tvId)}/${exceptionId}`, 'DELETE');
  }
}
