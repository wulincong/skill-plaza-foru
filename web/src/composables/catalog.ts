import { shallowRef } from 'vue'
import { bySlug, type Skill } from '../data/skills'

export const publishedSkills = shallowRef<Skill[]>([])
export const catalogUnavailable = shallowRef(false)

export const publishedSkill = (slug: string) => publishedSkills.value.find((s) => s.slug === slug)

export async function refreshCatalog() {
  try {
    const response = await fetch('/api/skills', { cache: 'no-store', signal: AbortSignal.timeout(5000) })
    if (!response.ok) throw new Error()
    const { skills } = (await response.json()) as { skills: { id: string; name: string; description: string }[] }
    publishedSkills.value = skills.map(
      (s) =>
        bySlug.get(s.id) ?? {
          slug: s.id,
          name: s.name,
          identifier: s.id,
          categoryId: 'industry',
          audiences: [],
          summary: s.description,
          tags: [],
          preconditions: '',
          outputs: [],
          dependencies: [],
          limitations: [],
          minimalInput: '',
        },
    )
    catalogUnavailable.value = false
  } catch {
    publishedSkills.value = []
    catalogUnavailable.value = true
  }
}
