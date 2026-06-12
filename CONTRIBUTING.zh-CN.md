# 为 vimhjkl 做贡献

感谢你的帮助！欢迎提交 Bug 修复、新课和更好的示例缓冲区。

## 环境搭建

你需要在 `PATH` 上有 [uv](https://docs.astral.sh/uv/) 以及 `vim` 或 `nvim`。没有其他依赖项——本包是纯标准库。

```sh
git clone https://github.com/S-Sigdel/vimhjkl && cd vimhjkl
uv sync
uv run vimhjkl            # 运行
```

在提交 PR 之前请运行测试套件（评分测试会通过真实 vim 回放按键）：

```sh
uv run python -m tests.test_grader
uv run python -m tests.test_engine
```

## 工作流程

在分支上工作，永远不要直接在 `main` 上操作——命名分支能让你的拉取请求更易于审查，也能让你无冲突地拉取上游变更。

1. **Fork** 本仓库并克隆你的 fork。

2. **创建以变更命名的分支。** 使用简短的前缀以便目了然：
   `fix/` 用于 Bug，`lesson/` 用于新课或重做的课程，`feature/` 用于其他所有情况。

   ```sh
   git switch -c fix/ctrl-j-quit-counted
   ```

3. **做一个聚焦的变更。** 每个分支只做一个 Bug 修复或一课——小 PR 审查和合并更快。遵循周围代码的风格（本包仅限标准库；未经讨论不得引入新依赖）。

4. **运行两个测试套件**（见上方命令）并确认它们通过。如果你修改了评分行为，在 `tests/test_grader.py` 中添加测试；如果你修改了选择/评分逻辑，在 `tests/test_engine.py` 中添加测试。

5. **以仓库风格提交**——简短、小写、祈使句摘要，不带 `type:` 前缀，例如：

   ```
   count the save keystrokes correctly when Enter sends <NL>
   ```

   保持每次提交为一个逻辑变更；在推送前 squash 杂乱的提交。

6. **推送并打开针对 `main` 的拉取请求。** 在描述中说明变更内容和原因。对于课程，附上**起始缓冲区**、**目标缓冲区**和**按键序列**，以便审查者可以一次粘贴验证。

## 布局

```
src/vimhjkl/
  cli.py            # 菜单、模式、会话编排
  engine.py         # 调度和评分——不关心具体技巧
  challenge.py      # Challenge/Skill 模型 + 类别注册表
  grader.py         # 启动真实 vim，捕获结果 + 按键，评分
  store.py          # JSON 持久化
  tui.py            # ANSI 渲染和输入
  data/skills.json  # 课程（数据，不是代码）
tests/              # 无头评分和引擎检查
```

引擎是通用的：一项技巧是一条**数据条目**，而非引擎编辑。新技巧应该是 `skills.json` 中的一课，而不是 `grader.py` 或 `engine.py` 中的特例——如果你发现自己为了教授某个具体操作而编辑这些文件，请停下来重新思考。

## 添加或修复课程

课程位于 `src/vimhjkl/data/skills.json`。每项技能都有一个 `category`（`challenge.py` 中 `CATEGORIES` 的键之一），它决定了评分方式，以及一个 `challenges` 列表：

```json
{
  "id": "marks-as-ex-range",
  "title": "将标记用作 Ex 范围（'a,'b）",
  "category": "ex_command",
  "teach": "用两三个句子解释该操作。",
  "key_commands": [":'a,'b", "ma", "mb"],
  "difficulty": 4,
  "challenges": [
    {
      "start": ["用户起始的行"],
      "goal":  ["完成时缓冲区必须等于的行"],
      "solution": "字面按键序列，用 <Esc>/<CR> 写出",
      "par_keys": 25,
      "hint": "简短提示",
      "why": "一行说明为什么这是惯用路径"
    }
  ]
}
```

`motion` 类挑战使用 `start_cursor` + `target`（1-based 的 `[行, 列]`）代替 `goal`。详见 `challenge.py` 中的 `CATEGORIES`。

**好**挑战的标准：

- **例子必须需要该技术。** 调整缓冲区大小，使得该课的操作是最短的正确答案。在 2 行缓冲区上进行 `:g`/宏/排序/范围练习毫无意义——更简单的操作就能击败它。对于范围/标记练习，在范围*之外*放一个匹配项，这样全文件 `:%…` 会改错行。
- **原创、具体的文本。** 不要用 `foo`/`bar`，不要用 `one/two/three`。使用生动、具体的示例文本；切勿复制真实的书籍/歌曲/源代码文本。
- **`solution` 是最优路径**（`par_keys` 是最优按键次数，不含最后的保存/退出）且必须在真实 vim 中回放时精确复现 `goal`。在干净的编辑器（`vim -u NONE`）中运行你的按键以确认。

## 报告问题

针对 Bug 或课程建议请打开一个 [issue](https://github.com/S-Sigdel/vimhjkl/issues)。对于新课程，最有用的报告是**起始缓冲区**、**目标缓冲区**和**按键序列**——这就是验证所需的一切。

贡献即表示你同意你的作品根据 [MIT 许可证](LICENSE) 授权。
