# Soul-Shell

带点赛博脾气的终端代理。平时可以直接执行 shell 命令，需要 AI 介入时用 `?` 开头提问。

## 快速开始

要求：

- Python 3.11+
- 一个可用的模型渠道 API Key

安装依赖：

```bash
uv sync
```

或：

```bash
pip install -e .
```

## 配置渠道

Soul-Shell 会从下面这个路径读取配置：

```text
~/.config/soul-shell/channels.toml
```

最小示例：

```toml
[[channels]]
name = "deepseek"
provider = "openai"
base_url = "https://api.deepseek.com"
api_key = "sk-你的key"
models = ["deepseek-chat"]
default_model = "deepseek-chat"
```

也可以按需补 `settings`：

```toml
[settings]
shell_log_size = 200
shell_context_inject = 20
react_probability = 0.30
max_history_turns = 20
risk_threshold = 70
```

## 配置用户画像

仓库里只提交模板，不提交你的真实画像。

复制模板：

```bash
cp prompts/user_profile.template.md prompts/user_profile.md
```

Windows PowerShell：

```powershell
Copy-Item prompts/user_profile.template.md prompts/user_profile.md
```

然后编辑 `prompts/user_profile.md`。这个文件已经被 `.gitignore` 忽略，不会再被 Git 跟踪。

## 启动

```bash
uv run soul-shell
```

或：

```bash
python -m soul_shell
```

启动时指定模型：

```bash
uv run soul-shell --model deepseek/deepseek-chat
```

## 基本用法

- 普通输入：直接当 shell 命令执行
- `? 你的问题`：向 Soul 提问
- `/model`：查看模型列表
- `/model 渠道/模型`：切换模型
- `/model probe 渠道名`：探测渠道可用模型
- `/history`：查看对话历史
- `/clear`：清空对话历史
- `/help`：查看帮助
- `/exit`：退出

## 说明

- `prompts/system.md` 是系统提示词
- `prompts/user_profile.md` 是你的本地私有画像
- `prompts/user_profile.template.md` 是给别人复制的模板
- 如果仓库里没找到 `channels.toml`，程序会在启动时打印示例配置
