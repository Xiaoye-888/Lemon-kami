@echo off
chcp 65001 >nul
echo ========================================
echo   部署测试场景页面到管理后台
echo ========================================
echo.

cd /d "%~dp0"

echo 📁 正在复制测试页面...
if not exist "admin\public\sdk" mkdir "admin\public\sdk"
xcopy /E /Y "sdk\js_sdk\*" "admin\public\sdk\"

echo.
echo ✅ 部署完成！
echo.
echo 📍 测试页面位置: admin\public\sdk\js_example.html
echo 🔗 访问方式: 在应用列表中点击"测试场景"按钮
echo.
pause
