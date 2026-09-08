---
name: fill-card-statements
description: >-
  Fills blank credit-card statement amounts in Shane_balance.numbers from Gmail
  inbox statements, then updates running balances. Use when the user asks to
  fill card statements, update the balance sheet from email, or pull statement
  balances into Numbers.
---

# Fill Card Statements

MCPs: `user-apple-numbers` (read/write) and `plugin-gmail-gmail` (inbox).

## 1. Discover the target table

Call `get-file-info` first. Do not assume old names.

- First sheet is the current month, named `YYMM` (e.g. `2609` = 2026-09).
- That sheet has **one** table. — copy it **exactly** from `get-file-info`. 
- Pass both `sheet` and `table` on every read/write.

Then `read-table` that sheet+table. Blank **Amount** cells on card rows are the ones to fill.

## 2. Match cards

Inbox search (`in:inbox`, recent statements):

```
in:inbox (statement OR "statement balance" OR "statement is ready") newer_than:45d
```

Also search Chase / Amex senders if needed. Read matching messages as `PLAIN_TEXT`.

Map last-four / account names to **Description** (not last-four on the sheet):

| Sheet name | Identity |
|---|---|
| Chase Amazon | Chase Prime Visa `...0915` |
| Chase Freedom | Chase Freedom Visa `...6741` |
| AMEX ED | Amex ending `01005` |
| AMEX Hilton | Amex ending `71005` |

**Apple Card:** inbox often has no dollar amount (Wallet-only). Leave blank and say so.

Write **negative** amounts (cash out), matching existing rows.

## 3. Writting

This workbook is large. `set-cell` / `set-cells-batch` might time out. Use them first, if fails, use `set-formula` or `set-formulas-batch`. Both with the **exact** `sheet` + `table`.

0-based `(row, col)` → Numbers `A1`: col 2 = `C`, row 10 = `C11`.

Set each filled card **Amount** (`col` 2) to `=-167` style literals (if setting formula).

## 4. Verify and report

Re-read the same sheet+table. Tell the user:

- What was filled (card, amount, email source)
- What stayed blank and why
