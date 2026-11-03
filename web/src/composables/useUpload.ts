import { browserHeaders } from './browserHistory.ts'
/* ============================================================
   附件上传（POST /api/upload）
   ------------------------------------------------------------
   文件 → base64 → 后端写入会话沙箱 workspace/<sessionId>/uploads/。
   返回的 sessionId 对应本次任务的沙箱目录，必须随后传给
   /api/chat（同一目录），附件才能被引擎读到。
   ============================================================ */

export interface UploadedFile {
  sessionId: string
  name: string
  /** 相对会话沙箱目录的路径（uploads/xxx） */
  path: string
  size: number
}

const ALLOWED_EXTS = ['.pdf', '.docx', '.doc', '.md', '.txt']
const MAX_FILE_MB = 6

/** 返回错误文案；通过校验返回 null */
export function validateUploadFile(file: File): string | null {
  const lower = file.name.toLowerCase()
  if (!ALLOWED_EXTS.some(ext => lower.endsWith(ext))) {
    return `仅支持 ${ALLOWED_EXTS.join(' / ')} 文件`
  }
  if (!file.size) return '文件内容为空'
  if (file.size > MAX_FILE_MB * 1024 * 1024) return `文件超过 ${MAX_FILE_MB}MB 上限`
  return null
}

export function uploadFile(file: File, sessionId?: string): Promise<UploadedFile> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('读取文件失败'))
    reader.onload = async () => {
      try {
        const response = await fetch('/api/upload', {
          method: 'POST',
          headers: { ...browserHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sessionId,
            filename: file.name,
            dataBase64: String(reader.result ?? ''),
          }),
        })
        const data = (await response.json()) as UploadedFile & { error?: string }
        if (!response.ok || data.error) throw new Error(data.error || '上传失败，请稍后重试。')
        resolve(data)
      } catch (exc) {
        reject(exc instanceof Error ? exc : new Error('上传失败'))
      }
    }
    reader.readAsDataURL(file)
  })
}

/** 内置演示附件直传（文本走 dataText，不经 FileReader），一键测试用 */
export function uploadDemoFile(filename: string, text: string, sessionId?: string): Promise<UploadedFile> {
  return (async () => {
    const response = await fetch('/api/upload', {
      method: 'POST',
      headers: { ...browserHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, filename, dataText: text }),
    })
    const data = (await response.json()) as UploadedFile & { error?: string }
    if (!response.ok || data.error) throw new Error(data.error || '上传失败，请稍后重试。')
    return data
  })()
}

export function formatSize(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)}MB`
    : `${Math.max(1, Math.round(bytes / 1024))}KB`
}
