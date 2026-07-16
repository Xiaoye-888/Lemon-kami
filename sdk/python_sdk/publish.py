"""
Lemon Kami SDK 自动发布脚本
用法: python publish.py [--test]
  --test: 上传到 TestPyPI（测试）
  不加参数: 上传到正式 PyPI
"""

import subprocess
import sys
import shutil
from pathlib import Path


def run_command(cmd, description):
    """执行命令并显示结果"""
    print(f"\n{'='*60}")
    print(f"📦 {description}")
    print(f"{'='*60}")
    print(f"命令: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ 成功")
        if result.stdout:
            print(result.stdout)
        return True
    else:
        print(f"❌ 失败")
        print(f"错误: {result.stderr}")
        return False


def clean_build_files():
    """清理构建文件"""
    print("\n🧹 清理旧的构建文件...")
    
    dirs_to_remove = ['build', 'dist', 'lemon_kami_sdk.egg-info']
    for dir_name in dirs_to_remove:
        dir_path = Path(dir_name)
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"  已删除: {dir_name}")
    
    print("✅ 清理完成")


def main():
    """主函数"""
    # 检查参数
    test_mode = '--test' in sys.argv
    
    print("="*60)
    print("🚀 Lemon Kami SDK 发布工具")
    print("="*60)
    
    if test_mode:
        print("⚠️  模式: 测试环境 (TestPyPI)")
    else:
        print("⚠️  模式: 正式环境 (PyPI)")
    
    print("\n请确认：")
    print("  1. 已更新 setup.py 中的版本号")
    print("  2. 已更新 README.md")
    print("  3. 已测试所有功能")
    
    confirm = input("\n是否继续？(y/n): ")
    if confirm.lower() != 'y':
        print("❌ 取消发布")
        return
    
    # 步骤 1: 清理
    clean_build_files()
    
    # 步骤 2: 构建
    if not run_command(
        [sys.executable, "-m", "build"],
        "构建分发包"
    ):
        print("\n❌ 构建失败，请检查错误信息")
        return
    
    # 步骤 3: 检查
    if not run_command(
        ["twine", "check", "dist/*"],
        "检查分发包"
    ):
        print("\n❌ 检查失败，请修复问题后重试")
        return
    
    # 步骤 4: 上传
    if test_mode:
        upload_cmd = ["twine", "upload", "--repository", "testpypi", "dist/*"]
        target = "TestPyPI"
    else:
        upload_cmd = ["twine", "upload", "dist/*"]
        target = "PyPI"
    
    print(f"\n{'='*60}")
    print(f"📤 准备上传到 {target}")
    print(f"{'='*60}")
    print("请输入 PyPI 凭据：")
    print("  - 如果使用密码，直接输入用户名和密码")
    print("  - 如果使用 Token，用户名为: __token__")
    print("    密码为: pypi-xxxxx")
    
    if not run_command(upload_cmd, f"上传到 {target}"):
        print(f"\n❌ 上传到 {target} 失败")
        return
    
    # 完成
    print("\n" + "="*60)
    print("🎉 发布成功！")
    print("="*60)
    
    if test_mode:
        print("\n测试安装命令：")
        print("  pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple lemon-kami-sdk")
    else:
        print("\n安装命令：")
        print("  pip install lemon-kami-sdk")
        print("\n查看项目页面：")
        print("  https://pypi.org/project/lemon-kami-sdk/")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

