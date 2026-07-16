# 🚀 快速发布 Lemon Kami SDK 到 PyPI

## 📋 准备工作（只需做一次）

### 1. 安装发布工具

```powershell
pip install build twine
```

### 2. 注册 PyPI 账号

访问 https://pypi.org/account/register/ 注册账号

### 3. 获取 API Token（推荐）

1. 登录 https://pypi.org/
2. 访问 https://pypi.org/manage/account/
3. 点击 "Add API token"
4. 选择 "Entire account (all projects)"
5. 复制生成的 token（格式：`pypi-xxxxx`）

---

## 🎯 发布流程

### 方式一：使用自动化脚本（推荐）

```powershell
# 进入 SDK 目录
cd D:\pythonspider\激活加密\lemon_kami\sdk\python_sdk

# 测试发布（先上传到 TestPyPI）
python publish.py --test

# 正式发布的命令（测试通过后）
python publish.py
```

### 方式二：手动发布

```powershell
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

## ⚠️ 发布前检查清单

每次发布前确认：

- [ ] 更新了 `setup.py` 中的 `version`（如：1.0.0 → 1.0.1）
- [ ] 更新了 `README.md` 的变更说明
- [ ] 在本地测试了所有功能
- [ ] 运行了 `twine check dist/*` 并通过
- [ ] （首次）已在 TestPyPI 测试过安装

---

## 🧪 测试安装

### 从 TestPyPI 测试

```powershell
# 创建虚拟环境
python -m venv test_env
test_env\Scripts\activate

# 从 TestPyPI 安装
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple lemon-kami-sdk

# 测试导入
python -c "from lemon_kami import LemonKamiSDK; print('✅ 成功')"
```

### 从正式 PyPI 安装

```powershell
pip install lemon-kami-sdk
```

---

## 📝 版本管理规范

遵循语义化版本（Semantic Versioning）：

```
主版本号.次版本号.修订号
  ↑        ↑        ↑
  重大更新  新功能   Bug修复
```

**示例：**
- `1.0.0` - 首次发布
- `1.0.1` - 修复 Bug
- `1.1.0` - 添加新功能
- `2.0.0` - 不兼容的重大更新

---

## 🔍 常见问题

### Q1: 提示包名已存在

**解决：** 修改 `setup.py` 中的 `name`，换一个唯一的名字，如：
- `lemon-kami-client`
- `kami-auth-sdk`

### Q2: 上传时认证失败

**解决：** 
- 用户名：`__token__`
- 密码：你的 API Token（`pypi-xxxxx`）

### Q3: 想删除已发布的包

**注意：** PyPI 不支持删除包，只能：
1. 废弃版本（yank）
2. 发布新版本覆盖

### Q4: 如何查看我的包？

访问：`https://pypi.org/project/lemon-kami-sdk/`

---

## 📞 需要帮助？

查看详细文档：[`PUBLISH_GUIDE.md`](PUBLISH_GUIDE.md)

或参考官方文档：
- PyPI: https://pypi.org/
- Packaging Guide: https://packaging.python.org/
- Twine: https://twine.readthedocs.io/

---

**祝您发布顺利！** 🎉
