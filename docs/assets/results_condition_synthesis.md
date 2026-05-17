# Condition synthesis (paper §4)

| Cond | Task | V0 step | V1 step | V1−tc step | V0 timeout | V1 timeout | KG fired (V1) | Auto outcome |
|------|-----:|--------:|--------:|----------:|----------:|----------:|---------------|--------------|
| H1 | 309 | 19 | 21.0 | — | 0 | 0 | project/main | **refuted** |
| H2 | 102 | 15 | 9 | — | 0 | 0 | project/issue_list | **confirmed** |
| H3 | 156 | 4 | 4 | — | 0 | 0 | dashboard/merge_request_list | **partial** |
| L1 | 418 | 9 | 11 | — | 0 | 0 | account/edit | **needs_review** |
| L2 | 568 | — | — | — | 0 | 0 | project/member_list | **parity_review** |
| Null1 | 44 | 2 | 2 | — | 0 | 0 | dashboard/todo_list | **confirmed_parity** |
| Null2 | 664 | 14 | 14 | — | 0 | 0 | project/issue_detail | **confirmed_parity** |

Outcome labels are automated triage. Manual narrative for
each condition (especially `needs_review` rows) is added
during paper §4 writing.
