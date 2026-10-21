"""
FastAPI 主入口
航空发动机装配排产仿真系统 - AeroEngine Assembly Scheduling Simulation
北京航空航天大学 (Beihang University)
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

from app.api import config, process, simulation, results, unity_playback, factory_layout, pt6a29_layout

# 创建FastAPI应用实例
app = FastAPI(
    title="航空发动机装配排产仿真系统",
    description="AeroEngine Assembly Scheduling Simulation - Beihang University",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS中间件配置 - 允许跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务 - 前端资源
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    # 挂载css和js目录到根路径（支持模块化前端）
    css_dir = os.path.join(frontend_dir, "css")
    js_dir = os.path.join(frontend_dir, "js")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

# 注册API路由
app.include_router(config.router, prefix="/api/config", tags=["配置管理"])
app.include_router(process.router, prefix="/api/process", tags=["工艺流程"])
app.include_router(simulation.router, prefix="/api/simulation", tags=["仿真控制"])
app.include_router(unity_playback.router, prefix="/api/simulation/unity", tags=["Unity 同步播放"])
app.include_router(factory_layout.router, prefix="/api/simulation/unity", tags=["工厂布局"])
app.include_router(pt6a29_layout.router, prefix="/api/simulation/unity", tags=["原场景29工位物理布局"])
app.include_router(results.router, prefix="/api/results", tags=["结果查询"])


@app.get("/", response_class=HTMLResponse)
async def root():
    """
    根路径 - 返回前端页面
    """
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>航空发动机装配排产仿真系统</title>
        <style>
            body {
                font-family: 'Microsoft YaHei', sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: #eee;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }
            .container {
                text-align: center;
                padding: 40px;
                background: rgba(255,255,255,0.05);
                border-radius: 16px;
                border: 1px solid rgba(255,255,255,0.1);
            }
            h1 { color: #00d4ff; margin-bottom: 10px; }
            h2 { color: #888; font-weight: normal; margin-bottom: 30px; }
            a {
                display: inline-block;
                padding: 12px 24px;
                background: #00d4ff;
                color: #1a1a2e;
                text-decoration: none;
                border-radius: 8px;
                margin: 10px;
                font-weight: bold;
            }
            a:hover { background: #00b8e6; }
            .watermark {
                margin-top: 40px;
                color: rgba(255,255,255,0.3);
                font-size: 12px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛫 航空发动机装配排产仿真系统</h1>
            <h2>AeroEngine Assembly Scheduling Simulation</h2>
            <p>后端服务已启动，前端页面待部署</p>
            <a href="/docs">📖 API文档 (Swagger)</a>
            <a href="/redoc">📚 API文档 (ReDoc)</a>
            <div class="watermark">
                北京航空航天大学 | Beihang University<br>
                AeroEngine Scheduling System v1.0.0
            </div>
        </div>
    </body>
    </html>
    """)


@app.get("/health")
async def health_check():
    """
    健康检查接口
    """
    return JSONResponse(content={
        "status": "healthy",
        "version": "1.0.0",
        "service": "AeroEngine Assembly Scheduling Simulation"
    })


@app.on_event("startup")
async def startup_event():
    """
    应用启动事件
    """
    # 创建结果存储目录
    results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)
    print("🛫 航空发动机装配排产仿真系统启动成功!")
    print("📖 API文档: http://localhost:8000/docs")
    print("🌐 前端界面: http://localhost:8000")


@app.on_event("shutdown")
async def shutdown_event():
    """
    应用关闭事件
    """
    print("🛬 航空发动机装配排产仿真系统已关闭")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
