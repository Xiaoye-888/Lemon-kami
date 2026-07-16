# Lemon Kami SDK 发布到 PyPI 指南

## 📋 前置准备

### 1. 注册 PyPI 账号

访问 https://pypi.org/ 注册账号（如果还没有）

### 2. 安装发布工具

```bash
pip install --upgrade build twine
```

---

## 🚀 发布步骤

### 第一步：修改版本号

编辑 `setup.py`，修改 version：

```python
version="1.0.0",  # 每次发布递增版本号
```

**版本规范：**
- `1.0.0` - 正式发布
- `1.0.1` - Bug 修复
- `1.1.0` - 新功能
- `2.0.0` - 重大更新

### 第二步：构建分发包

在 `sdk/python_sdk/` 目录下执行：

```bash
cd D:\pythonspider\激活加密\lemon_kami\sdk\python_sdk
python -m build
```

这会生成两个文件：
- `dist/lemon-kami-sdk-1.0.0.tar.gz` （源码包）
- `dist/lemon_kami_sdk-1.0.0-py3-none-any.whl` （wheel 包）

### 第三步：检查分发包

```bash
twine check dist/*
```

确保输出包含：
```
Checking dist/lemon-kami-sdk-1.0.0.tar.gz: PASSED
Checking dist/lemon_kami_sdk-1.0.0-py3-none-any.whl: PASSED
```

### 第四步：上传到 TestPyPI（测试）

先上传到测试环境验证：

```bash
twine upload --repository testpypi dist/*
```

会提示输入 PyPI 用户名和密码。

### 第五步：测试安装

创建虚拟环境测试：

```bash
# 创建测试环境
python -m venv test_env
test_env\Scripts\activate  # Windows

# 从 TestPyPI 安装
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple lemon-kami-sdk

# 测试导入
python -c "from lemon_kami import LemonKamiSDK; print('✅ 安装成功')"
```

### 第六步：上传到正式 PyPI

测试通过后，上传到正式环境：

```bash
twine upload dist/*
```

### 第七步：验证正式安装

```bash
pip install lemon-kami-sdk
python -c "from lemon_kami import LemonKamiSDK; print('✅ 安装成功')"
```

---

## 🔐 使用 API Token（推荐）

相比密码，使用 API Token 更安全：

1. 访问 https://pypi.org/manage/account/
2. 点击 "Add API token"
3. 选择 "Entire account" 或特定项目
4. 复制生成的 token

使用时：
```bash
# 用户名固定为 __token__
# 密码是刚才复制的 token
twine upload --username __token__ --password pypi-xxxxx dist/*
```

或者配置 `.pypirc` 文件：

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-xxxxx

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-xxxxx
```

然后直接：
```bash
twine upload dist/*
```

---

## 📝 更新版本

### 修改代码后

1. 修改 `setup.py` 中的版本号
2. 更新 `README.md` 的变更日志
3. 重新构建：
   ```bash
   python -m build
   ```
4. 上传：
   ```bash
   twine upload dist/*
   ```

---

## ⚠️ 注意事项

### 1. 包名唯一性

`lemon-kami-sdk` 这个名字必须在 PyPI 上是唯一的。如果被占用，需要改名：
- `lemon-kami-client`
- `lemon-license-sdk`
- `kami-auth-sdk`

### 2. 不要重复上传同一版本

PyPI 不允许覆盖已发布的版本。如果出错，必须升级版本号重新发布。

### 3. 清理旧文件

每次发布前清理旧的构建文件：

```bash
# Windows PowerShell
Remove-Item -Recurse -Force build, dist, *.egg-info

# 或使用
rmdir /s /q build dist
del /s /q *.egg-info
```

### 4. 依赖声明

确保 `install_requires` 中包含所有依赖：
```python
install_requires=[
    "requests>=2.31.0",
    "pycryptodome>=3.19.0",
],
```

---

## 🔍 常见问题

### Q: 上传时提示 403 Forbidden

A: 检查用户名密码是否正确，或使用 API Token。

### Q: 包名已被占用

A: 修改 `setup.py` 中的 `name` 字段，换一个唯一的名字。

### Q: 如何删除已发布的包？

A: PyPI 不支持删除包，只能废弃（yank）或发布新版本。

### Q: 如何查看我的包？

A: 访问 `https://pypi.org/project/lemon-kami-sdk/`

---

## 📊 发布清单

发布前检查：

- [ ] 更新了 `setup.py` 中的版本号
- [ ] 更新了 `README.md`
- [ ] 测试了所有功能
- [ ] 运行了 `twine check dist/*`
- [ ] 在 TestPyPI 上测试过安装
- [ ] 清理了旧的构建文件
- [ ] 准备了 API Token

---

## 🎯 快速发布命令汇总

```bash
# 1. 进入目录
cd D:\pythonspider\激活加密\lemon_kami\sdk\python_sdk

# 2. 清理旧文件
Remove-Item -Recurse -Force build, dist, *.egg-info -ErrorAction SilentlyContinue

# 3. 构建
python -m build

# 4. 检查
twine check dist/*

# 5. 上传到正式 PyPI
twine upload dist/*
```

---

## 📞 获取帮助

- PyPI 官方文档: https://packaging.python.org/
- Twine 文档: https://twine.readthedocs.io/
- Build 文档: https://pypa-build.readthedocs.io/

祝您发布顺利！🎉
