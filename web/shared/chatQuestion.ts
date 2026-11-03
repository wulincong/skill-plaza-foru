export interface QuestionOption {
  label: string
  description?: string
}

export interface ChatQuestion {
  kind: 'confirm' | 'single' | 'multiple' | 'input'
  question: string
  note?: string
  options: QuestionOption[]
}
