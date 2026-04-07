# 贡献指南

感谢您对 openHarness 项目的关注！我们欢迎各种形式的贡献，包括但不限于代码、文档、问题报告和功能建议。

## 📋 目录

- [行为准则](#行为准则)
- [开发环境设置](#开发环境设置)
- [代码规范](#代码规范)
- [贡献流程](#贡献流程)
- [提交规范](#提交规范)
- [问题报告](#问题报告)
- [功能请求](#功能请求)
- [代码审查](#代码审查)
- [发布流程](#发布流程)

## 🤝 行为准则

本项目遵循 [Contributor Covenant 行为准则](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)。参与本项目即表示您同意遵守其条款。

## 🛠️ 开发环境设置

### 前置要求

- Python 3.8+
- Git
- [OpenCode](https://opencode.ai) 或 [Claude Code](https://www.anthropic.com/claude-code)（测试需要）

### 步骤

1. **Fork 仓库**
   ```bash
   # 在 GitHub 上 Fork 仓库
   git clone https://github.com/你的用户名/openHarness.git
   cd openHarness
   ```

2. **创建虚拟环境**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate
   
   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **安装开发依赖**
   ```bash
   pip install -e ".[dev]"
   ```

4. **设置 pre-commit 钩子**（可选但推荐）
   ```bash
   pre-commit install
   ```

5. **验证环境**
   ```bash
   pytest
   ruff check src/openharness
   mypy src/
   ```

## 📏 代码规范

### 代码风格

- 使用 [Ruff](https://github.com/astral-sh/ruff) 进行代码风格检查和格式化
- 行宽限制：88 字符
- 使用类型提示（Type Hints）
- 所有公共函数必须有文档字符串（Docstring）

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 类名 | PascalCase | `GitRepository`, `ConfigManager` |
| 函数/变量 | snake_case | `get_project_config`, `file_path` |
| 常量 | UPPER_SNAKE_CASE | `MAX_DEPTH`, `DEFAULT_TIMEOUT` |
| 私有成员 | _leading_underscore | `_internal_method` |

### 文档字符串格式

使用 Google 风格的文档字符串：

```python
def function_with_types(param1: int, param2: str) -> bool:
    """函数简要描述。

    函数详细描述（如果需要）。

    Args:
        param1: 参数1的描述
        param2: 参数2的描述

    Returns:
        返回值的描述

    Raises:
        ValueError: 异常情况的描述

    Examples:
        >>> function_with_types(1, "test")
        True
    """
```

### 文件结构

- 每个模块都应该有清晰的职责
- 避免循环导入
- 使用相对导入在包内引用

## 🔄 贡献流程

### 1. 选择任务

- 查看 [Issues](https://github.com/hahaxiang27/openHarness/issues) 中标记为 `good first issue` 或 `help wanted` 的任务
- 如果你想实现新功能，先创建 Issue 讨论

### 2. 创建分支

```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/issue-description
```

### 3. 开发

- 编写代码
- 添加测试
- 更新文档

### 4. 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_installer.py

# 生成测试覆盖率报告
pytest --cov=src --cov-report=html
```

### 5. 代码检查

```bash
# 代码风格检查
ruff check src/

# 代码格式化
ruff format src/

# 类型检查
mypy src/
```

### 6. 提交更改

```bash
git add .
git commit -m "feat: 添加新功能描述"
git push origin feature/your-feature-name
```

### 7. 创建 Pull Request

- 在 GitHub 上创建 PR 到 `main` 分支
- 填写 PR 模板中的所有必要信息
- 确保所有 CI 检查通过

## 📝 提交规范

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<类型>[可选 范围]: <描述>

[可选 正文]

[可选 脚注]
```

### 类型说明

| 类型 | 描述 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat: 添加Git分支选择功能` |
| `fix` | 修复bug | `fix: 修复路径解析错误` |
| `docs` | 文档更新 | `docs: 更新安装说明` |
| `style` | 代码格式调整 | `style: 调整缩进格式` |
| `refactor` | 代码重构 | `refactor: 重构配置加载逻辑` |
| `test` | 测试相关 | `test: 添加配置模块测试` |
| `chore` | 构建/工具相关 | `chore: 更新依赖版本` |

### 示例

```bash
# 新功能
git commit -m "feat(scanner): 添加多Git仓库并行扫描支持"

# 修复bug
git commit -m "fix(config): 修复YAML解析编码问题"

# 带正文的提交
git commit -m "feat(init): 添加分支选择功能

- 支持本地和远程分支选择
- 支持新建分支
- 支持多个Git仓库依次处理

Closes #123"
```

## 🐛 问题报告

### 报告bug

使用 [Bug 报告模板](https://github.com/hahaxiang27/openHarness/issues/new?template=bug_report.md) 创建 Issue，包含：

1. **环境信息**
   - 操作系统和版本
   - Python版本
   - openHarness版本
   - AI后端（OpenCode/Claude Code）

2. **重现步骤**
   ```bash
   # 具体的命令和操作
   hc init
   hc start
   ```

3. **期望行为**
   - 描述你期望发生什么

4. **实际行为**
   - 描述实际发生了什么
   - 包含错误信息、日志、截图

5. **补充信息**
   - 相关配置
   - 可能的解决方案

### 安全漏洞

如果发现安全漏洞，请**不要**公开创建 Issue。请通过邮件联系维护者。

## ✨ 功能请求

使用 [功能请求模板](https://github.com/hahaxiang27/openHarness/issues/new?template=feature_request.md) 创建 Issue，包含：

1. **问题描述**
   - 这个功能要解决什么问题？

2. **解决方案**
   - 你希望如何实现？

3. **替代方案**
   - 考虑过哪些替代方案？

4. **使用场景**
   - 具体的使用示例

## 🔍 代码审查

### 审查标准

- [ ] 代码符合项目规范
- [ ] 有足够的测试覆盖
- [ ] 文档已更新（如需要）
- [ ] 没有破坏现有功能
- [ ] 性能可接受
- [ ] 安全性考虑

### 审查流程

1. 至少需要一位维护者批准
2. 所有 CI 检查必须通过
3. 解决所有审查意见
4. 使用 "Squash and merge" 合并

## 🚀 发布流程

### 版本号规范

遵循 [语义化版本](https://semver.org/lang/zh-CN/)：

- **主版本号**：不兼容的API修改
- **次版本号**：向下兼容的功能性新增
- **修订号**：向下兼容的问题修正

### 发布步骤

1. 更新 `pyproject.toml` 中的版本号
2. 更新 `CHANGELOG.md`
3. 创建 Git 标签：`git tag v4.2.0`
4. 推送标签：`git push origin v4.2.0`
5. GitHub Actions 自动发布到 PyPI

## 📞 获取帮助

- **讨论区**：GitHub Discussions
- **问题**：GitHub Issues
- **邮件**：维护者邮箱

## 🙏 致谢

感谢所有贡献者的付出！您的每一份贡献都让 openHarness 变得更好。

---

**最后更新**：2026年4月7日
**维护者**：Helans(VibeCoder黄老斯)