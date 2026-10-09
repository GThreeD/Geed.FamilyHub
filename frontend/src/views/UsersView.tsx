import type { User, Role } from '../api';
import { UserService, type ManagedUser } from '../services/UserService';
import UserCreator from '../components/UserCreator';

type UsersViewProps = {
  users: ManagedUser[];
  user: User;
  act: (action: () => Promise<unknown>) => Promise<void>;
};

export default function UsersView({ users, user, act }: UsersViewProps) {
  function changeRole(id: number, role: Role) {
    void act(() => UserService.updateRole(id, role));
  }

  function changeActive(id: number, active: boolean) {
    void act(() => UserService.setActive(id, active));
  }

  return (
    <section className="panel">
      <h2>Benutzer & Berechtigungen</h2>

      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Login</th>
              <th>Rolle</th>
              <th>Aktiv</th>
            </tr>
          </thead>
          <tbody>
            {users.map((entry) => (
              <tr key={entry.id}>
                <td>{entry.display_name}</td>
                <td>{entry.username}</td>
                <td>
                  <select
                    disabled={entry.id === user.id}
                    value={entry.role}
                    onChange={(event) => changeRole(entry.id, event.target.value as Role)}
                  >
                    <option value="admin">Admin</option>
                    <option value="manager">Manager</option>
                    <option value="viewer">Betrachter</option>
                  </select>
                </td>
                <td>
                  <input
                    type="checkbox"
                    checked={!!entry.active}
                    disabled={entry.id === user.id}
                    onChange={(event) => changeActive(entry.id, event.target.checked)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <UserCreator create={(payload) => act(() => UserService.create(payload))} />
    </section>
  );
}
