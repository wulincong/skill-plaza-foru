export type SandboxErrorCode =
  | 'DOCKER_UNREACHABLE'
  | 'DOCKER_API'
  | 'RUNTIME_UNAVAILABLE'
  | 'RUNTIME_MISMATCH'
  | 'START_FAILED'
  | 'RUN_EXISTS'
  | 'IMAGE_LOCK'
  | 'INVALID_SPEC'
  | 'VERIFY_FAILED'
  | 'PI_NOT_READY'
  | 'RPC_TIMEOUT'
  | 'RPC_CLOSED'
  | 'RPC_COMMAND'
  | 'FRAME_TOO_LARGE'
  | 'RECLAIM_FAILED'

export class SandboxError extends Error {
  readonly code: SandboxErrorCode
  readonly details: unknown

  constructor(code: SandboxErrorCode, message: string, details?: unknown, options?: { cause?: unknown }) {
    super(message, options)
    this.name = 'SandboxError'
    this.code = code
    this.details = details
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
