import api from './api'

export interface RuleCondition {
  id?: string
  rule_id?: string
  field: 'counterparty_name' | 'description' | 'amount' | 'date'
  operator: 'is' | 'contains' | 'does_not_contain' | 'is_not' | 'eq' | 'gt' | 'lt' | 'before' | 'after'
  value: string
  created_at?: string
}

export interface RuleAction {
  id?: string
  rule_id?: string
  action_type: 'mark_hsa' | 'mark_potential' | 'hide' | 'assign_member'
  member_id?: string | null
  created_at?: string
}

export interface HsaRule {
  id: string
  user_id: string
  name: string
  priority: number
  is_active: boolean
  conditions: RuleCondition[]
  actions: RuleAction[]
  created_at: string
  updated_at: string
}

export interface HsaRuleInput {
  name: string
  priority: number
  is_active: boolean
  conditions: Omit<RuleCondition, 'id' | 'rule_id' | 'created_at'>[]
  actions: Omit<RuleAction, 'id' | 'rule_id' | 'created_at'>[]
}

export interface ReorderItem {
  id: string
  priority: number
}

export interface ApplyResult {
  updated: number
}

export const rulesService = {
  list: (): Promise<HsaRule[]> =>
    api.get<HsaRule[]>('/bank/rules').then(r => r.data),

  get: (id: string): Promise<HsaRule> =>
    api.get<HsaRule>(`/bank/rules/${id}`).then(r => r.data),

  create: (input: HsaRuleInput): Promise<HsaRule> =>
    api.post<HsaRule>('/bank/rules', input).then(r => r.data),

  update: (id: string, input: HsaRuleInput): Promise<HsaRule> =>
    api.put<HsaRule>(`/bank/rules/${id}`, input).then(r => r.data),

  delete: (id: string): Promise<void> =>
    api.delete(`/bank/rules/${id}`).then(() => undefined),

  reorder: (items: ReorderItem[]): Promise<HsaRule[]> =>
    api.patch<HsaRule[]>('/bank/rules/reorder', items).then(r => r.data),

  applyAll: (): Promise<ApplyResult> =>
    api.post<ApplyResult>('/bank/rules/apply').then(r => r.data),
}