"""Fig, a standalone animated Windows desktop companion."""

import argparse
import json
import math
from pathlib import Path
import sys

from PySide6.QtCore import QPoint, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCursor, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon, QWidget


VERSION = "1.0.0"
CELL = QSize(192, 208)
ANIMATIONS = {
    "idle": (0, [280, 110, 110, 140, 140, 320]),
    "running-right": (1, [120] * 7 + [220]),
    "running-left": (2, [120] * 7 + [220]),
    "waving": (3, [140, 140, 140, 280]),
    "jumping": (4, [140, 140, 140, 140, 280]),
    "failed": (5, [140] * 7 + [240]),
    "waiting": (6, [150] * 5 + [260]),
    "running": (7, [120] * 5 + [220]),
    "review": (8, [150] * 5 + [280]),
}
LABELS = {
    "idle": "休息", "running-right": "向右跑", "running-left": "向左跑",
    "waving": "挥手", "jumping": "跳跃", "failed": "沮丧",
    "waiting": "等你回应", "running": "认真思考", "review": "检查成果",
}


def asset(name):
    return Path(__file__).resolve().parent / "assets" / name


def look_direction(dx, dy):
    """Map screen coordinates to clockwise directions, with zero pointing up."""
    return int((math.degrees(math.atan2(dx, -dy)) % 360 + 11.25) // 22.5) % 16


class FigPet(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fig Desktop Pet")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowIcon(QIcon(str(asset("fig.ico"))))
        self.setAccessibleName("Fig 桌面宠物")
        self.setToolTip("Fig · 拖动移动 · 单击挥手 · 双击跳跃 · 右键菜单")
        self.settings = QSettings("FigDesktopPet", "Fig")
        self.sheet = QPixmap(str(asset("fig.png")))
        if self.sheet.size() != QSize(1536, 2288):
            raise ValueError("Fig sprite sheet is missing or has invalid dimensions.")
        self.frames = {}
        for state, (row, durations) in ANIMATIONS.items():
            self.frames[state] = [self.sheet.copy(col * 192, row * 208, 192, 208)
                                  for col in range(len(durations))]
        self.looks = [self.sheet.copy((i % 8) * 192, (9 + i // 8) * 208, 192, 208)
                      for i in range(16)]
        self.state = "idle"
        self.frame = 0
        self.look = None
        self.repeat = True
        self.press_position = None
        self.drag_origin = None
        self.last_drag_position = None
        self.dragging = False
        self.follow_cursor = self.settings.value("follow_cursor", True, type=bool)
        self.scale = 1.0
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.advance)
        self.gaze_timer = QTimer(self)
        self.gaze_timer.setInterval(80)
        self.gaze_timer.timeout.connect(self.track_cursor)
        self.click_timer = QTimer(self)
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(lambda: self.play("waving"))
        self.menu = self.build_menu()
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("Fig 桌宠 · 右键打开菜单")
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        try:
            scale = float(self.settings.value("scale", 1.0))
        except (TypeError, ValueError):
            scale = 1.0
        self.set_scale(scale)
        self.place_on_screen()
        self.play("idle", repeat=True)
        self.gaze_timer.start()

    def build_menu(self):
        menu = QMenu(self)
        heading = menu.addAction(f"Fig 桌面宠物  v{VERSION}")
        heading.setEnabled(False)
        menu.addSeparator()
        menu.addAction("显示 / 隐藏", self.toggle_visible)
        self.follow_action = menu.addAction("跟随鼠标看向")
        self.follow_action.setCheckable(True)
        self.follow_action.setChecked(self.follow_cursor)
        self.follow_action.toggled.connect(self.set_follow_cursor)
        sizes = menu.addMenu("大小")
        self.size_group = QActionGroup(self)
        for label, value in [("75%", 0.75), ("100%", 1.0), ("125%", 1.25), ("150%", 1.5), ("200%", 2.0)]:
            action = QAction(label, sizes)
            action.setCheckable(True)
            action.setData(value)
            self.size_group.addAction(action)
            action.triggered.connect(lambda checked=False, size=value: self.set_scale(size))
            sizes.addAction(action)
        animations = menu.addMenu("播放动作")
        for state in ANIMATIONS:
            animations.addAction(LABELS[state], lambda checked=False, name=state: self.play(name, repeat=name == "idle"))
        menu.addAction("回到屏幕右下角", self.reset_position)
        menu.addSeparator()
        menu.addAction("退出 Fig", self.quit)
        menu.aboutToShow.connect(self.menu_opened)
        menu.aboutToHide.connect(self.gaze_timer.start)
        return menu

    def menu_opened(self):
        self.click_timer.stop()
        self.gaze_timer.stop()

    def set_follow_cursor(self, enabled):
        self.follow_cursor = enabled
        self.settings.setValue("follow_cursor", enabled)
        self.look = None
        self.update()

    def set_scale(self, value):
        self.scale = value if value in (0.75, 1.0, 1.25, 1.5, 2.0) else 1.0
        self.setFixedSize(round(CELL.width() * self.scale), round(CELL.height() * self.scale))
        self.settings.setValue("scale", self.scale)
        for action in self.size_group.actions():
            action.setChecked(action.data() == self.scale)
        if self.isVisible():
            self.keep_visible()
        self.update()

    def place_on_screen(self):
        saved = self.settings.value("position")
        if isinstance(saved, QPoint):
            self.move(saved)
            self.keep_visible()
        else:
            self.reset_position()

    def reset_position(self):
        area = QApplication.primaryScreen().availableGeometry()
        self.move(area.right() - self.width() - 24, area.bottom() - self.height() - 8)
        self.keep_visible()

    def keep_visible(self):
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        max_x = max(area.left(), area.right() + 1 - self.width())
        max_y = max(area.top(), area.bottom() + 1 - self.height())
        self.move(min(max(self.x(), area.left()), max_x), min(max(self.y(), area.top()), max_y))

    def play(self, state, repeat=False):
        self.timer.stop()
        self.state, self.frame, self.repeat, self.look = state, 0, repeat, None
        self.update()
        self.timer.start(ANIMATIONS[state][1][0])

    def advance(self):
        durations = ANIMATIONS[self.state][1]
        self.frame += 1
        if self.frame >= len(durations):
            if not self.repeat:
                self.play("idle", repeat=True)
                return
            self.frame = 0
        self.update()
        self.timer.start(durations[self.frame])

    def track_cursor(self):
        if not self.follow_cursor or self.state != "idle" or self.press_position is not None or not self.isVisible():
            return
        eye_center = self.pos() + QPoint(self.width() // 2, round(88 * self.scale))
        delta = QCursor.pos() - eye_center
        radius = math.hypot(delta.x(), delta.y())
        direction = look_direction(delta.x(), delta.y()) if 35 * self.scale < radius < 700 * self.scale else None
        if direction != self.look:
            self.look = direction
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        pixmap = self.looks[self.look] if self.look is not None else self.frames[self.state][self.frame]
        painter.drawPixmap(self.rect(), pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_position = event.globalPosition().toPoint()
            self.drag_origin = self.pos()
            self.last_drag_position = self.press_position
            self.dragging = False
            self.look = None
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        if self.press_position is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        global_position = event.globalPosition().toPoint()
        delta = global_position - self.press_position
        if not self.dragging and delta.manhattanLength() < QApplication.startDragDistance():
            return
        self.dragging = True
        self.click_timer.stop()
        direction = "running-right" if global_position.x() >= self.last_drag_position.x() else "running-left"
        self.last_drag_position = global_position
        if direction != self.state:
            self.play(direction, repeat=True)
        self.move(self.drag_origin + delta)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.press_position is None:
            return
        was_dragging = self.dragging
        self.press_position = self.drag_origin = None
        self.dragging = False
        self.unsetCursor()
        if was_dragging:
            self.keep_visible()
            self.settings.setValue("position", self.pos())
            self.play("idle", repeat=True)
        else:
            self.click_timer.start(QApplication.doubleClickInterval())
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.click_timer.stop()
            self.press_position = self.drag_origin = None
            self.dragging = False
            self.unsetCursor()
            self.play("jumping")
            event.accept()

    def contextMenuEvent(self, event):
        self.menu.popup(event.globalPos())
        event.accept()

    def toggle_visible(self):
        self.setVisible(not self.isVisible())
        if self.isVisible():
            self.keep_visible()
            self.raise_()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_visible()

    def quit(self):
        self.settings.setValue("position", self.pos())
        self.settings.sync()
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        self.quit()
        event.accept()


def smoke_test(app, pet, report_path):
    """Exercise rendering and the real animation controller in a packaged build."""
    result = {"version": VERSION, "ok": False, "states": {}, "directions": 0}
    try:
        pet.gaze_timer.stop()
        for state, (_, durations) in ANIMATIONS.items():
            pet.play(state)
            pet.timer.stop()
            for index in range(len(durations)):
                assert pet.state == state and pet.frame == index
                app.processEvents()
                assert not pet.grab().isNull()
                pet.advance()
                pet.timer.stop()
            assert pet.state == "idle" and pet.frame == 0
            result["states"][state] = len(durations)
        for index, pixmap in enumerate(pet.looks):
            assert not pixmap.isNull()
            pet.look = index
            app.processEvents()
            assert not pet.grab().isNull()
            result["directions"] += 1
        assert [look_direction(*p) for p in [(0, -10), (10, 0), (0, 10), (-10, 0)]] == [0, 4, 8, 12]
        result["ok"] = True
    except Exception as error:
        result["error"] = repr(error)
    Path(report_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    app.exit(0 if result["ok"] else 1)


def main():
    parser = argparse.ArgumentParser(description="Fig desktop pet")
    parser.add_argument("--smoke-test", metavar="REPORT", help="Check animation/rendering and write JSON, then exit")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Fig Desktop Pet")
    app.setApplicationVersion(VERSION)
    app.setQuitOnLastWindowClosed(False)
    server = QLocalServer(app)
    if not args.smoke_test:
        socket = QLocalSocket()
        socket.connectToServer("FigDesktopPet-v1")
        if socket.waitForConnected(400):
            socket.write(b"show")
            socket.waitForBytesWritten(400)
            return 0
        if not server.listen("FigDesktopPet-v1"):
            QMessageBox.warning(None, "Fig", "无法启动 Fig 的单实例通信。请关闭现有 Fig 后重试。")
            return 1
    try:
        pet = FigPet()
    except Exception as error:
        QMessageBox.critical(None, "Fig", f"启动失败\n{error}")
        return 1

    def show_existing():
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            connection.close()
            connection.deleteLater()
        pet.show()
        pet.keep_visible()
        pet.raise_()

    server.newConnection.connect(show_existing)
    pet.show()
    if args.smoke_test:
        QTimer.singleShot(300, lambda: smoke_test(app, pet, args.smoke_test))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
