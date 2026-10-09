import { HttpService } from './HttpService';
import type { Role } from '../api';
import type { CredentialType } from './AuthService';

export interface ManagedUser {
  id: number;
  username: string;
  display_name: string;
  role: Role;
  active: boolean;
}
export interface CreateUserRequest {
  username: string;
  display_name: string;
  role: Role;
  credential_type: CredentialType;
  credential: string;
}
export class UserService {
  static list() {
    return HttpService.request<ManagedUser[]>('/api/users');
  }
  static create(data: CreateUserRequest) {
    return HttpService.request<unknown>('/api/users', 'POST', data);
  }
  static updateRole(id: number, role: Role) {
    return HttpService.request<unknown>(`/api/users/${id}`, 'PATCH', { role });
  }
  static setActive(id: number, active: boolean) {
    return HttpService.request<unknown>(`/api/users/${id}`, 'PATCH', { active });
  }
}
