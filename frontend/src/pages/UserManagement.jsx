import { useState, useEffect } from 'react'
import { getAuthUsers, createAuthUser, updateAuthUser, deleteAuthUser } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

export default function UserManagement() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showInvite, setShowInvite] = useState(false)
  const [invite, setInvite] = useState({ email: '', name: '', role: 'viewer' })
  const [error, setError] = useState(null)

  const fetchUsers = () => {
    setLoading(true)
    getAuthUsers()
      .then(setUsers)
      .catch(() => setError('Failed to load users'))
      .finally(() => setLoading(false))
  }

  useEffect(fetchUsers, [])

  const handleInvite = async () => {
    if (!invite.email || !invite.name) return
    setError(null)
    try {
      await createAuthUser(invite)
      setInvite({ email: '', name: '', role: 'viewer' })
      setShowInvite(false)
      fetchUsers()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to create user')
    }
  }

  const handleRoleChange = async (id, newRole) => {
    try {
      await updateAuthUser(id, { role: newRole })
      fetchUsers()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to update role')
    }
  }

  const handleDeactivate = async (id) => {
    try {
      await deleteAuthUser(id)
      fetchUsers()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to deactivate user')
    }
  }

  const handleReactivate = async (id) => {
    try {
      await updateAuthUser(id, { is_active: true })
      fetchUsers()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to reactivate user')
    }
  }

  return (
    <div style={{
      maxWidth: 900, margin: '0 auto',
      padding: '40px 28px',
      fontFamily: 'var(--font-ui)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{
            fontSize: 22, fontWeight: 700,
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-display)',
            margin: 0,
          }}>
            User Management
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0', fontFamily: 'var(--font-mono)' }}>
            {users.length} user{users.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => setShowInvite(true)}
          style={{
            background: 'var(--gold)', color: '#000',
            border: 'none', borderRadius: 8,
            padding: '10px 20px', fontSize: 13, fontWeight: 600,
            cursor: 'pointer', fontFamily: 'var(--font-ui)',
          }}
        >
          Invite User
        </button>
      </div>

      {error && (
        <div style={{
          background: 'var(--red-muted)', color: 'var(--red)',
          padding: '10px 16px', borderRadius: 8, marginBottom: 16,
          fontSize: 13, fontFamily: 'var(--font-mono)',
        }}>
          {error}
        </div>
      )}

      {/* Invite form */}
      {showInvite && (
        <div style={{
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          borderRadius: 10, padding: 20, marginBottom: 20,
        }}>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'end' }}>
            <div style={{ flex: 1, minWidth: 180 }}>
              <label style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', display: 'block', marginBottom: 4 }}>Email</label>
              <input
                type="email"
                value={invite.email}
                onChange={e => setInvite(p => ({ ...p, email: e.target.value }))}
                placeholder="user@company.com"
                style={{
                  width: '100%', padding: '8px 12px',
                  background: 'var(--bg-deep)', border: '1px solid var(--border)',
                  borderRadius: 6, color: 'var(--text-primary)',
                  fontFamily: 'var(--font-mono)', fontSize: 13,
                  outline: 'none',
                }}
              />
            </div>
            <div style={{ flex: 1, minWidth: 180 }}>
              <label style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', display: 'block', marginBottom: 4 }}>Name</label>
              <input
                type="text"
                value={invite.name}
                onChange={e => setInvite(p => ({ ...p, name: e.target.value }))}
                placeholder="Full name"
                style={{
                  width: '100%', padding: '8px 12px',
                  background: 'var(--bg-deep)', border: '1px solid var(--border)',
                  borderRadius: 6, color: 'var(--text-primary)',
                  fontFamily: 'var(--font-mono)', fontSize: 13,
                  outline: 'none',
                }}
              />
            </div>
            <div style={{ minWidth: 120 }}>
              <label style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', display: 'block', marginBottom: 4 }}>Role</label>
              <select
                value={invite.role}
                onChange={e => setInvite(p => ({ ...p, role: e.target.value }))}
                style={{
                  width: '100%', padding: '8px 12px',
                  background: 'var(--bg-deep)', border: '1px solid var(--border)',
                  borderRadius: 6, color: 'var(--text-primary)',
                  fontFamily: 'var(--font-mono)', fontSize: 13,
                  outline: 'none',
                }}
              >
                <option value="viewer">Viewer</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={handleInvite}
                style={{
                  background: 'var(--gold)', color: '#000',
                  border: 'none', borderRadius: 6,
                  padding: '8px 16px', fontSize: 13, fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Add
              </button>
              <button
                onClick={() => setShowInvite(false)}
                style={{
                  background: 'transparent', color: 'var(--text-muted)',
                  border: '1px solid var(--border)', borderRadius: 6,
                  padding: '8px 16px', fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Users table */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 10, overflow: 'hidden',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['User', 'Role', 'Last Login', 'Status', ''].map(h => (
                <th key={h} style={{
                  padding: '12px 16px', textAlign: 'left',
                  fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
                  letterSpacing: '0.06em', color: 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Loading...</td></tr>
            ) : users.map(u => {
              const isSelf = u.id === currentUser?.id
              return (
                <tr key={u.id} style={{ borderBottom: '1px solid var(--border-faint)' }}>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{u.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{u.email}</div>
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    {isSelf ? (
                      <RoleBadge role={u.role} />
                    ) : (
                      <select
                        value={u.role}
                        onChange={e => handleRoleChange(u.id, e.target.value)}
                        style={{
                          background: 'var(--bg-deep)', border: '1px solid var(--border)',
                          borderRadius: 6, color: 'var(--text-primary)',
                          padding: '4px 8px', fontSize: 12,
                          fontFamily: 'var(--font-mono)', outline: 'none',
                        }}
                      >
                        <option value="viewer">Viewer</option>
                        <option value="admin">Admin</option>
                      </select>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : 'Never'}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{
                      fontSize: 11, fontWeight: 600,
                      padding: '2px 8px', borderRadius: 10,
                      background: u.is_active ? 'var(--teal-muted)' : 'var(--red-muted)',
                      color: u.is_active ? 'var(--teal)' : 'var(--red)',
                      fontFamily: 'var(--font-mono)',
                    }}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                    {!isSelf && (
                      u.is_active ? (
                        <button
                          onClick={() => handleDeactivate(u.id)}
                          style={{
                            background: 'none', border: 'none',
                            color: 'var(--text-muted)', fontSize: 12,
                            cursor: 'pointer', fontFamily: 'var(--font-mono)',
                            padding: '4px 8px', borderRadius: 4,
                          }}
                          onMouseEnter={e => e.currentTarget.style.color = 'var(--red)'}
                          onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
                        >
                          Deactivate
                        </button>
                      ) : (
                        <button
                          onClick={() => handleReactivate(u.id)}
                          style={{
                            background: 'none', border: 'none',
                            color: 'var(--text-muted)', fontSize: 12,
                            cursor: 'pointer', fontFamily: 'var(--font-mono)',
                            padding: '4px 8px', borderRadius: 4,
                          }}
                          onMouseEnter={e => e.currentTarget.style.color = 'var(--teal)'}
                          onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
                        >
                          Reactivate
                        </button>
                      )
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RoleBadge({ role }) {
  const isAdmin = role === 'admin'
  return (
    <span style={{
      fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
      letterSpacing: '0.06em',
      padding: '2px 8px', borderRadius: 10,
      background: isAdmin ? 'var(--gold-muted)' : 'var(--blue-muted)',
      color: isAdmin ? 'var(--gold)' : 'var(--blue)',
      fontFamily: 'var(--font-mono)',
    }}>
      {role}
    </span>
  )
}
