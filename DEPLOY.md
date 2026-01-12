# 工商业分布式光伏评估系统 V2.0

## 部署到 Streamlit Cloud

### 步骤 1：准备文件

确保项目包含以下文件：
- `app18.py` - 主程序文件
- `requirements_cloud.txt` - 依赖清单
- `.streamlit/config.toml` - 配置（可选）

### 步骤 2：推送到 GitHub

1. 创建 GitHub 仓库：https://github.com/new
2. 在项目目录执行：

```bash
git init
git add .
git commit -m "Initial commit: 工商业分布式光伏评估系统"
git branch -M main
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

### 步骤 3：部署到 Streamlit Cloud

1. 访问 https://streamlit.io/cloud
2. 点击 "New project"
3. 选择 "Connect to GitHub"
4. 选择你的仓库
5. 设置：
   - Main file path: `app18.py`
   - Requirements file: `requirements_cloud.txt`
6. 点击 "Deploy"

### 步骤 4：手机访问

部署完成后，Streamlit Cloud 会提供一个 URL（如：`https://你的应用.streamlit.app`），在手机浏览器中打开即可使用。

## 功能模块

1. 项目测绘与面积确认 - 地图框选区域
2. 技术选型与造价配置 - 选择组件、逆变器等
3. 深度财务测算 - IRR、DSCR 分析
4. BOM清单与报价 - 导出设备清单和报价单
