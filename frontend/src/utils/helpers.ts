export function formatPrice(amount: number, currency = 'CNY'): string { return new Intl.NumberFormat('zh-CN', { style: 'currency', currency }).format(amount / 100) }
export function normalizeAccessCode(code: string): string { return code.replace(/[\s-]/g, '').toUpperCase() }
export function formatAccessCode(code: string): string { return normalizeAccessCode(code).match(/.{1,4}/g)?.join('-') || '' }
export async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard) return navigator.clipboard.writeText(text)
  const input = document.createElement('textarea')
  input.value = text; document.body.appendChild(input); input.select()
  const copied = document.execCommand('copy'); input.remove()
  if (!copied) throw new Error('复制失败，请手动选中并复制。')
}
export function rememberCode(grantId: string, code: string) { sessionStorage.setItem(`quiz-code-${grantId}`, code) }
