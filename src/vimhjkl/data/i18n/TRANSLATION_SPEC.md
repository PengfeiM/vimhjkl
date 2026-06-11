# vimhjkl Translation Specification

> Version: 1.0  
> Status: **Living document** — update when new skills or terms are added to the curriculum.

---

## 1. Overview

This document is the **translation norm** for vimhjkl's i18n system. It defines:

1. **What must be translated** (teaching text: title, teach, hint, why)
2. **What must NOT be translated** (Vim native keystrokes, Ex commands, data fields)
3. **How to translate consistently** (term glossary, register names, mode names)

### Audience

This spec has two readers:

| Reader | Role |
|--------|------|
| **Human translator** | Manually reviews and edits locale JSON files. Uses the glossary and checklists below. |
| **AI translation system** | Reads this spec as part of the CI translation prompt to enforce term preservation and key literal handling. |

### File structure

```
src/vimhjkl/data/i18n/
├── i18n-schema.json        # JSON Schema for validation
├── TRANSLATION_SPEC.md     # ← This file: translation norms
├── zh-CN.json              # Chinese (Simplified) locale overlay
└── {locale}.json           # Future language overlays (fr, de, ja, ...)
```

### Source of truth

**English is the single source of truth.** The file `src/vimhjkl/data/skills.json` is the canonical curriculum. Locale files are *overlays*: they only contain translated fields. Any field missing from a locale file falls back to the English value at runtime. This means:

- Adding a new skill to `skills.json` is safe — it will display in English until a translation is provided.
- Removing a field from a locale file restores the English version.
- Locale files are **never merged into** `skills.json`.

---

## 2. Format

Locale files follow the JSON Schema defined in `i18n-schema.json` (draft 2020-12).

Key structural rules:

| Rule | Detail |
|------|--------|
| File name | `{locale}.json` where `locale` matches `^[a-z]{2}(-[A-Z]{2})?$` |
| Root `locale` field | Must match the file name (e.g. `zh-CN`) |
| Root `skills` object | Keyed by **skill_id**, matching `^[a-z][a-z0-9_-]+$` |
| Challenge overlay | Array index corresponds to the English `challenges[]` array position |
| All fields optional | Partial overlay is valid — only supplied fields are applied |

---

## 3. Restrictive Phrase 1 — Vim Native Key/Command Literals

**This is the single most important rule.** Vim native keystrokes, Ex commands, operator sequences, register references, and any other Vim-internal notation MUST remain in their raw form. They are **not natural language** and must never be translated, localized, or modified.

### 3.1 Key names

Chevron-delimited key names (`<...>`) are literal Vim internal representations. Do not translate them.

| Raw form | ❌ Wrong | ✅ Correct |
|----------|----------|------------|
| `<Esc>` | `退出键` or `Escape` | Keep as `<Esc>` |
| `<CR>` | `回车` | Keep as `<CR>` |
| `<Tab>` | `制表符` | Keep as `<Tab>` |
| `<C-p>` | `Ctrl+P` or `控制-P` | Keep as `<C-p>` |
| `<C-w>h` | `Ctrl+W 然后 H` | Keep as `<C-w>h` |
| `<C-a>` | `Ctrl+A` | Keep as `<C-a>` |
| `<C-x>` | `Ctrl+X` | Keep as `<C-x>` |
| `<C-v>` | `Ctrl+V` | Keep as `<C-v>` |
| `<C-n>` | `Ctrl+N` | Keep as `<C-n>` |
| `<C-r>` | `Ctrl+R` | Keep as `<C-r>` |
| `<C-r>=` | `Ctrl+R then =` | Keep as `<C-r>=` |
| `<C-x><C-l>` | `Ctrl+X then Ctrl+L` | Keep as `<C-x><C-l>` |

**Exception:** In the *surrounding prose* of `teach` or `hint` text that describes a key, it is acceptable to parenthetically note the key name in the target language for readability, but the raw `<...>` notation itself must still be present when the keystroke is referenced as a command:

> Example (Chinese): `按 <C-a> 增加数字` — the `<C-a>` literal is preserved.

### 3.2 Ex commands

Everything starting with `:` is an Ex command. The `:` is literal and must not be removed.

| Raw form | ❌ Wrong | ✅ Correct |
|----------|----------|------------|
| `:wq` | `保存退出` | Keep as `:wq` |
| `:s/foo/bar/g` | `替换 foo 为 bar` | Keep as `:%s/foo/bar/g` |
| `:g/pattern/d` | `删除匹配的行` | Keep as `:g/pattern/d` |
| `:normal` | `普通模式命令` | Keep as `:normal` |
| `:%normal A;` | `全部行末尾加分号` | Keep as `:%normal A;` |
| `:sort n` | `数字排序` | Keep as `:sort n` |
| `:3,6normal I#` | `第3到6行行首加#` | Keep as `:3,6normal I#` |

### 3.3 Operator sequences

Operator + motion combinations are technical commands, not prose.

| Raw form | ❌ Wrong | ✅ Correct |
|----------|----------|------------|
| `dd` | `删除行` | Keep as `dd` (can be in code font) |
| `ci"` | `修改引号内内容` | Keep as `ci"` |
| `gU` | `转大写` | Keep as `gU` |
| `g~` | `大小写互换` | Keep as `g~` |
| `daw` | `删除一个词（含空格）` | Keep as `daw` |
| `2w` | `前进两个词` | Keep as `2w` |
| `;.` | `重复查找并修改` | Keep as `;.` |
| `xp` | `交换字符` | Keep as `xp` |
| `ddp` | `交换行` | Keep as `ddp` |

### 3.4 Register references

Register names are Vim-internal identifiers.

| Raw form | ❌ Wrong | ✅ Correct |
|----------|----------|------------|
| `"a` | `寄存器 a` | Keep as `"a` |
| `"0` | `寄存器 0` | Keep as `"0` |
| `"=` | `表达式寄存器` | Keep as `"=` |
| `"ap` | `粘贴寄存器 a` | Keep as `"ap` |

### 3.5 Range notation

Line ranges and file markers are Vim syntax.

| Raw form | ❌ Wrong | ✅ Correct |
|----------|----------|------------|
| `%s` | `全文替换` | Keep as `:%s` |
| `1,5s` | `第1到5行替换` | Keep as `:1,5s` |
| `'<,'>normal` | `选中区域执行` | Keep as `:'<,'>normal` |
| `.+1,/}/-1` | `块内范围` | Keep as `.+1,/}/-1` |

### 3.6 Mark names

Marks are single-letter Vim identifiers.

| Raw form | ❌ Wrong | ✅ Correct |
|----------|----------|------------|
| `ma` | `标记 a` | Keep as `ma` (can explain in prose) |
| `` `a `` | `跳转到标记 a` | Keep as `` `a `` |
| `'a` | `跳转到标记 a 行首` | Keep as `'a` |
| `` `` `` | `跳回之前位置` | Keep as `` `` `` |

### 3.7 Regex and patterns

Search patterns and regex syntax must be preserved verbatim.

| Raw form | ❌ Wrong | ✅ Correct |
|----------|----------|------------|
| `\v` | `极简模式` | Keep as `\v` |
| `\V` | `字面模式` | Keep as `\V` |
| `\c` | `忽略大小写` | Keep as `\c` |
| `\< \>` | `词边界` | Keep as `\< \>` |
| `\zs` | `匹配起始` | Keep as `\zs` |
| `\1`, `\2` | `反向引用` | Keep as `\1`, `\2` |
| `&` | `整个匹配` | Keep as `&` |
| `\u`, `\U` | `转大写` | Keep as `\u`, `\U` |

### 3.8 Data fields (never touched by translation)

The following fields in `skills.json` are **data, not prose** and must NEVER appear in a locale file:

| Field | Reason |
|-------|--------|
| `id` | Internal identifier, language-independent |
| `category` | Enum used in code logic |
| `difficulty` | Numeric difficulty level |
| `start` | Vim buffer content (language-independent) |
| `goal` | Target buffer content (language-independent) |
| `solution` | Vim keystroke sequence (must be exact) |
| `par_keys` | Optimal keystroke count (integer) |
| `target` | Cursor target position (integer coordinates) |
| `start_cursor` | Starting cursor position (integer coordinates) |
| `yank` | Expected yank register content |

---

## 4. General Translation Principles

### 4.1 English is source of truth; translations are overlays

- Never modify `skills.json`.
- Only translate fields listed as translatable (see §3.8 for non-translatable fields).
- Missing entries = English fallback. This is valid and expected.

### 4.2 Technical accuracy over literary elegance

- Vim learning material must be precise. A technically accurate but slightly awkward translation is better than a fluent but imprecise one.
- Keep Vim terminology consistent across every skill in the same locale file.
- When in doubt about a term, consult the Glossary (§5) or search for its usage in the `skills.json` source.

### 4.3 Community conventions

- Follow established Vim community translations where they exist.
- For Chinese (zh-CN), reference the existing Vim Chinese documentation and community usage (e.g. Vim 中文帮助文档, Vim 教程).
- For new terms not in the glossary, add an entry to the locale's `glossary` section and submit for review.

---

## 5. Term Glossary

### 5.1 Core concepts

| English | zh-CN | Notes | Category |
|---------|-------|-------|----------|
| operator | 操作符 | Generic Vim operator | core_concept |
| motion | 动作 | Movement command | core_concept |
| text object | 文本对象 | Structural text selection (iw, it, ip, etc.) | core_concept |
| register | 寄存器 | Storage for text (", 0, a-z, etc.) | core_concept |
| macro | 宏 | Recorded keystroke sequence | core_concept |
| buffer | 缓冲区 | In-memory file representation | core_concept |
| mark | 标记 | Named cursor position (m{a-z}) | core_concept |
| range | 范围 | Line range specification (1,5 or 'a,'b) | core_concept |
| count | 计数 | Numeric prefix before a command | core_concept |
| dot command | 点命令 | The `.` repeat command | core_concept |
| expression | 表达式 | Vim expression (`<C-r>=`) | core_concept |
| pattern | 模式 | Search/regex pattern | core_concept |
| replacement | 替换文本 | Substitute replacement string | core_concept |
| flag | 标志 | Substitute flags (g, c, i, etc.) | core_concept |
| word | 单词 | Vim word (alphanumeric + underscore) | core_concept |
| WORD | 字串 | Vim WORD (non-blank run, caps) | core_concept |
| text object | 文本对象 | Structured selection | core_concept |
| submatch | 子匹配 | Captured group in regex (\1, \2) | core_concept |

### 5.2 Modes

| English | zh-CN | Notes | Category |
|---------|-------|-------|----------|
| Normal mode | 普通模式 | Default Vim mode | mode |
| Insert mode | 插入模式 | For typing text | mode |
| Visual mode | 可视模式 | For selecting text | mode |
| Visual-Block mode | 可视块模式 | Rectangular selection | mode |
| Command-line mode | 命令行模式 | For Ex commands | mode |
| Operator-Pending mode | 操作符待决模式 | Between operator and motion | mode |

### 5.3 Commands and operations

| English | zh-CN | Notes | Category |
|---------|-------|-------|----------|
| delete | 删除 | d operator | command |
| change | 修改 | c operator | command |
| yank | 复制 | y operator (copy to register) | command |
| put | 粘贴 | p / P (paste from register) | command |
| substitute | 替换 | :s command | command |
| global | 全局 | :g command | command |
| sort | 排序 | :sort command | command |
| copy / :t | 复制 / :t | :t copy command | command |
| move / :m | 移动 / :m | :m move command | command |
| increment | 递增 | `<C-a>` | command |
| decrement | 递减 | `<C-x>` | command |
| repeat | 重复 | `.` or `@:` command | command |
| undo | 撤销 | u, `<C-r>` | command |
| find | 查找 | f / t motion | command |
| search | 搜索 | / ? motion | command |
| join | 连接 | J command | command |
| format | 格式化 | =, gq | command |
| fold | 折叠 | z commands | command |

### 5.4 Text objects

| English | zh-CN | Notes | Category |
|---------|-------|-------|----------|
| inside | 内部 | i prefix (ciw, di() | text_object |
| around | 周围 | a prefix (daw, das) | text_object |
| inner word | 内部单词 | iw text object | text_object |
| a word | 一个单词（含空格） | aw text object | text_object |
| inner paragraph | 段落内部 | ip text object | text_object |
| a paragraph | 一个段落（含空行） | ap text object | text_object |
| inner sentence | 句子内部 | is text object | text_object |
| a sentence | 一个句子（含空格） | as text object | text_object |
| inner tag | 标签内部 | it text object (HTML/XML) | text_object |

### 5.5 Key notation and special terms

| English | zh-CN | Notes | Category |
|---------|-------|-------|----------|
| unnamed register | 无名寄存器 | `""` default register | register |
| yank register | 复制寄存器 | `"0` register | register |
| named register | 命名寄存器 | `"a`-`"z` registers | register |
| expression register | 表达式寄存器 | `"=` register | register |
| small delete register | 小删除寄存器 | `"-` register | register |
| very magic | 极简模式 | `\v` regex mode | command |
| very nomagic | 字面模式 | `\V` regex mode | command |
| word boundary | 词边界 | `\<` `\>` anchors | command |
| lookahead | 先行断言 | `\ze` match end | command |
| lookbehind | 后顾断言 | `\zs` match start | command |
| case-insensitive | 忽略大小写 | `\c` flag | command |
| case-sensitive | 区分大小写 | `\C` flag | command |
| the Dot Formula | 点命令公式 | "one change, one move, then ." concept | core_concept |
| finger macro | 指法宏 | Ad-hoc two-key memory pattern | core_concept |

### 5.6 Category blurbs (used in menus)

| English | zh-CN | Notes | Category |
|---------|-------|-------|----------|
| motion | 动作 | Navigation and cursor movement | category |
| operator | 操作符 | Text manipulation commands | category |
| text object | 文本对象 | Structural text selection | category |
| register | 寄存器 | Text storage and retrieval | category |
| macro | 宏 | Keystroke recording and replay | category |
| Ex command | Ex 命令 | Command-line operations | category |
| search/replace | 搜索替换 | Search and substitute operations | category |

> **Note:** Category blurbs are currently hardcoded in `challenge.py` and may be moved to locale files in a future phase. When they are, use these translations.

---

## 6. Translation Quality Checklist

Use this checklist to review every locale file before submission.

### Structural checks

- [ ] File is valid JSON per `i18n-schema.json`
- [ ] `locale` field matches the file name
- [ ] All skill IDs in the locale file exist in `skills.json`
- [ ] No unknown fields present (schema `additionalProperties: false`)

### Vim literal preservation

- [ ] All `<...>` key notation is preserved exactly (no translation of `<Esc>`, `<CR>`, etc.)
- [ ] All `:command` syntax is preserved (including the `:` prefix)
- [ ] All operator sequences (`dd`, `ci"`, `gU`, etc.) remain as raw Vim notation
- [ ] All register references (`"a`, `"0`, `"=`) remain untouched
- [ ] All range notation (`%s`, `1,5s`, `.+1,/}/-1`) is literal
- [ ] All mark names (`ma`, `` `a ``, `'a`) are unchanged
- [ ] All regex metacharacters (`\v`, `\V`, `\c`, `\zs`, `\ze`, `\<`, `\>`, `\1`) are preserved
- [ ] No `start`, `goal`, `solution`, `par_keys`, `target`, `start_cursor`, or `yank` fields present

### Vocabulary consistency

- [ ] All occurrences of the same English term use the same glossary translation
- [ ] Mode names (Normal/Insert/Visual/Visual-Block/Command-line) are consistently translated
- [ ] `operator`, `motion`, and `text object` are consistent with glossary
- [ ] `register` and `macro` are consistently translated

### Overlay semantics

- [ ] Partial overlay is intentional (missing fields are not forgotten — they fall back to English)
- [ ] Each skill's `challenges` array length matches the English `skills.json` count
- [ ] Empty strings (`""`) are used for fields awaiting translation

---

## 7. CI Contract

### Trigger

The CI translation workflow (`.github/workflows/translate-curriculum.yml`) is triggered when `src/vimhjkl/data/skills.json` changes on the `main` branch.

### Automated flow

```
skills.json change detected
  → detect_curriculum_changes.py identifies changed fields
  → generate_translation.py calls AI API with context + spec
  → Locale files updated (changed fields only)
  → validate_translation.py checks:
      1. Schema compliance
      2. Field integrity (no data fields leaked)
      3. Glossary term consistency
  → PR created for human review
```

### Human review required

CI-generated translations are **drafts**. Every automated translation PR requires:

1. Human review of the diff
2. Verification against this spec's checklist (§6)
3. Manual approval before merge

### Adding a new language

To add a new language:

1. Create `src/vimhjkl/data/i18n/{locale}.json` (start from the skeleton template)
2. Translate all translatable fields
3. Validate against `i18n-schema.json`
4. Run the validation script: `uv run python -m scripts.validate_translation {locale}`
5. Submit for review

### Version tracking

Each locale file includes:
- `source_sha`: Git commit SHA of the `skills.json` used for this translation
- `generated_at`: ISO 8601 timestamp of last generation

When CI detects that `source_sha` does not match the current HEAD of `skills.json`, it flags the locale file as stale and triggers re-translation of changed fields.
