import { useEffect, useState } from 'react'

type LlmConnection = { provider: string; position: number; model?: string; base_url?: string; configured: boolean; status: string; latency_ms?: number; http_status?: number }
type LlmConnectionsPanelProps = { apiBaseUrl: string }
const statusLabel: Record<string, string> = { configured: 'Sẵn sàng kiểm tra', reachable: 'Kết nối thành công', missing_credentials: 'Thiếu API key', authentication_failed: 'API key không hợp lệ', unavailable: 'Không thể kết nối', unsupported: 'Provider chưa hỗ trợ' }

export function LlmConnectionsPanel({ apiBaseUrl }: LlmConnectionsPanelProps) {
  const [connections, setConnections] = useState<LlmConnection[]>([])
  const [loading, setLoading] = useState(true)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [checkedAt, setCheckedAt] = useState<string | null>(null)
  async function request(path: string, method = 'GET') { const response = await fetch(`${apiBaseUrl}${path}`, { method }); if (!response.ok) throw new Error('request failed'); return response.json() }
  async function load() { setLoading(true); setError(null); try { const result = await request('/v1/admin/system/llm-connections'); setConnections(result.connections ?? []) } catch { setError('Không thể đọc cấu hình kết nối AI.') } finally { setLoading(false) } }
  useEffect(() => { void load() }, [])
  async function checkConnections() { setChecking(true); setError(null); try { const result = await request('/v1/admin/system/llm-connections/check', 'POST'); setConnections(result.connections ?? []); setCheckedAt(result.checked_at ?? null) } catch { setError('Không thể hoàn tất kiểm tra kết nối AI.') } finally { setChecking(false) } }
  return <main className="llm-panel" aria-label="LLM connection status">
    <header><p className="section-kicker">SYSTEM HEALTH</p><h1>Kết nối AI</h1><p>Kiểm tra các LLM được khai báo trong môi trường chạy. API key không bao giờ hiển thị trên giao diện.</p></header>
    <section className="llm-actions"><div><strong>Chuỗi fallback</strong><span>Provider được thử theo thứ tự cấu hình trong <code>LLM_PROVIDER_ORDER</code>.</span></div><button className="primary-button" type="button" disabled={loading || checking} onClick={() => void checkConnections()}>{checking ? 'Đang kiểm tra…' : 'Kiểm tra kết nối'}</button></section>
    {error ? <p className="system-error" role="alert">{error}</p> : null}{loading ? <p role="status">Đang đọc cấu hình AI…</p> : null}
    {!loading && connections.length === 0 ? <section className="empty-state"><strong>Chưa có LLM nào được cấu hình.</strong><span>Thêm provider và API key vào biến môi trường, sau đó khởi động lại API.</span></section> : null}
    <section className="llm-grid">{connections.map((connection) => <article key={`${connection.provider}-${connection.position}`} className="llm-card"><div className="provider-row"><span className="provider-order">{connection.position}</span><div><h2>{connection.provider}</h2><p>{connection.model || 'Chưa có model'}</p></div><span className={`connection-status status-${connection.status}`}>{statusLabel[connection.status] || connection.status}</span></div><dl><div><dt>Endpoint</dt><dd>{connection.base_url || '—'}</dd></div><div><dt>Trạng thái cấu hình</dt><dd>{connection.configured ? 'API key đã khai báo' : 'Chưa khai báo API key'}</dd></div>{connection.http_status ? <div><dt>HTTP</dt><dd>{connection.http_status}{connection.latency_ms !== undefined ? ` · ${connection.latency_ms} ms` : ''}</dd></div> : null}</dl></article>)}</section>
    {checkedAt ? <p className="checked-at">Lần kiểm tra gần nhất: {checkedAt}</p> : null}
  </main>
}
