// Pi supplies a request-local copy of the tool declarations. Add display metadata
// there so a missing annotation never prevents a built-in tool from executing.
const annotatedTools = new Set(['bash', 'read', 'edit', 'write'])

export default function registerToolPurpose(pi) {
  pi.on('context_with_system', ({ messages }) => {
    for (const message of messages) {
      if (message.role !== 'system') continue
      for (const tool of message.toolsAdded ?? []) {
        if (!annotatedTools.has(tool.name) || tool.parameters.properties.purpose) continue
        tool.parameters.properties.purpose = {
          type: 'string',
          description: '给用户看的本次操作用途。用四至二十四个汉字写动词加具体对象，例如“核对各地区岗位数量”。每次调用分别填写。只写用途，避免重复工具名称，不写命令、文件名、路径、个人信息或结果。',
        }
        tool.parameters.required = [...(tool.parameters.required ?? []), 'purpose']
      }
    }
  })
}
