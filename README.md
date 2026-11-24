# 奶康 桌面宠物

奶康 是一只橙色卷发、戴黑框眼镜、穿紫色球衣的小金龙。Windows 单文件版内置全部素材，双击 `Fig.exe` 即可运行。

![Fig 跳跃预览](assets/preview.gif)

## 使用

- 按住鼠标左键拖动 奶康。
- 单击挥手，双击跳跃。
- 移动鼠标时，奶康 会朝鼠标方向看。
- 右键打开菜单，可以切换全部九种动作、开关视线跟随、调整大小、显示或隐藏、退出。
- 系统托盘图标也提供相同菜单。双击托盘图标可以显示或隐藏 奶康。
- 位置、大小和视线设置保存在当前 Windows 用户的设置中。

支持 Windows 10 / 11 的 x64 系统。发布包内含 `Fig.exe`，无需安装 Python。

该程序是独立桌宠。思考、等待和检查等动作可以从菜单播放。

## 从源码运行

需要 Python 3.14 和 Windows x64。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python fig_pet.py
```

## 打包

```powershell
.\build.ps1
```

产物为 `dist/Fig.exe`。

```powershell
.\dist\Fig.exe --smoke-test smoke-report.json
```

这个检查会启动实际窗口，逐一验证全部动画帧、十六个视线方向和动作结束后的回到休息状态，然后写入 JSON 并退出。

## 素材

精灵图为 1536 × 2288 像素，单格为 192 × 208 像素，共 73 个有效帧。素材由用户提供的角色参考图生成。角色美术的使用范围由相关权利决定。
