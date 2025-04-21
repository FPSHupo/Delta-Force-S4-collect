import sys
import os
import configparser
from pystray import Icon, MenuItem, Menu
from PIL import Image
from PyQt5.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu, QAction, QVBoxLayout, QWidget, QLineEdit, QPushButton, QLabel, QHBoxLayout
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt

# 配置文件路径
CONFIG_FILE = "sjz.ini"


def center_window(window):
    """居中显示窗口"""
    screen = window.screen()
    screen_geometry = screen.availableGeometry()
    window_geometry = window.frameGeometry()
    center_position = screen_geometry.center() - window_geometry.center()
    window.move(center_position)


class CustomizeKeysWindow(QWidget):
    """自定义按键窗口类"""

    def __init__(self, custom_keys, on_save_callback):
        super().__init__()
        self.custom_keys = custom_keys
        self.on_save_callback = on_save_callback
        self.setWindowTitle("自定义按键")
        self.setGeometry(50, 50, 50, 50)

        layout = QVBoxLayout()

        # 显示/隐藏窗口的按键输入框
        show_key_label = QLabel("显示窗口的按键：", self)
        layout.addWidget(show_key_label)
        show_key_entry = QLineEdit(self)
        show_key_entry.setText(self.custom_keys["show_key"])
        layout.addWidget(show_key_entry)

        hide_key_label = QLabel("隐藏窗口的按键：", self)
        layout.addWidget(hide_key_label)
        hide_key_entry = QLineEdit(self)
        hide_key_entry.setText(self.custom_keys["hide_key"])
        layout.addWidget(hide_key_entry)

        def save_keys():
            self.custom_keys["show_key"] = show_key_entry.text()
            self.custom_keys["hide_key"] = hide_key_entry.text()
            self.on_save_callback()  # 调用回调函数保存设置
            self.close()

        save_button = QPushButton("保存", self)
        save_button.clicked.connect(save_keys)
        layout.addWidget(save_button)

        self.setLayout(layout)

        # Center the window when it opens
        center_window(self)


class MemoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.memo_data = {}  # 储存备忘录数据，格式为 {栏目名: { 'quantity': 数量, 'button': 按钮, 'label': 标签 }}
        self.custom_key = {
            "show_key": "home",  # 默认按键为 Home
            "hide_key": "end"  # 默认按键为 End
        }

        self.setup_gui()
        self.load_from_config()  # 加载配置文件中的数据

        # 使用 keyboard 库监听快捷键
        import keyboard  # 导入 keyboard 库
        keyboard.add_hotkey(self.custom_key["show_key"], self.show_window)
        keyboard.add_hotkey(self.custom_key["hide_key"], self.hide_window)

        self.tray_icon = None
        self.create_tray_icon()

    def setup_gui(self):
        """设置主窗口的 GUI"""
        self.setWindowTitle("Memo Application")
        self.setGeometry(100, 100, 730, 800)

        # 设置字体样式为黑体，字号12，文字颜色
        self.setStyleSheet("""
            QWidget {
                font-family: "黑体";
                font-size: 16px;
                color: #E28AD2;
                border: 1px solid #E8E8E8;  /* 绿色边框 */
                padding: 5px;  /* 按钮内边距，保证边框不会直接贴着文字 */
            }
        """)

        # 创建显示栏目和按钮的容器
        self.memo_frame = QWidget(self)
        self.memo_layout = QHBoxLayout(self.memo_frame)  # 使用水平布局容纳列
        self.memo_frame.setLayout(self.memo_layout)

        # 设置窗口为悬浮窗，保持在其他窗口之上
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 设置为显示窗口，防止没有界面可视化
        self.memo_frame.setGeometry(10, 10, 700, 500)

        # Center the main window
        screen_geometry = QApplication.desktop().availableGeometry()
        self.move(screen_geometry.right() - self.width(), screen_geometry.top())

    def add_memo_item(self, title, quantity):
        """向显示区域中添加一个新的栏目项和按钮"""
        # 创建一个包含文本和按钮的水平布局
        memo_item_layout = QHBoxLayout()

        # 标签显示栏目名称和数量
        memo_text = f"{title}: {quantity}"
        label = QLabel(memo_text)
        memo_item_layout.addWidget(label)

        # 创建按钮，点击后减少数量
        button = QPushButton("已收集")
        button.clicked.connect(lambda: self.decrease_quantity(title, label, button, memo_item_layout))
        memo_item_layout.addWidget(button)

        # 设置按钮文字颜色为绿色
        button.setStyleSheet("""
            QPushButton {
                color: #A885F0;
                background-color: transparent;
                border: 1px solid #E8E8E8;  /* 绿色边框 */
                padding: 5px;  /* 按钮内边距，保证边框不会直接贴着文字 */
            }
            QPushButton:hover {
                background-color: #D1F8F3;  /* 鼠标悬停时背景色略微变绿 */
            }
        """)
        # 将该项添加到主界面布局
        self.memo_data[title]["button"] = button
        self.memo_data[title]["label"] = label
        self.memo_data[title]["layout"] = memo_item_layout

        # 根据列数动态分配栏目
        column_count = len(self.memo_layout.children())
        if column_count == 0 or len(self.memo_layout.children()[-1].children()) >= 10:
            new_column = QVBoxLayout()  # 创建新的一列
            self.memo_layout.addLayout(new_column)

        # 获取当前列并添加到其中
        current_column = self.memo_layout.children()[-1]
        current_column.addLayout(memo_item_layout)

    def decrease_quantity(self, title, label, button, memo_item_layout):
        """减少指定栏目的数量并更新显示"""
        if title in self.memo_data:
            self.memo_data[title]["quantity"] -= 1
            if self.memo_data[title]["quantity"] <= 0:
                # 先从布局中移除这项
                self.memo_layout.removeItem(memo_item_layout)

                # 清除布局中的控件（防止悬挂） 
                for i in reversed(range(memo_item_layout.count())):
                    widget_item = memo_item_layout.itemAt(i)
                    widget = widget_item.widget()
                    if widget:
                        widget.setParent(None)

                # 删除数据
                del self.memo_data[title]

                self.save_to_config()
                self.adjust_window_size()  # 自动调整窗口大小
            else:
                # 更新标签中的显示内容
                label.setText(f"{title}: {self.memo_data.get(title, {'quantity': 0})['quantity']}")
            self.save_to_config()  # 更新配置文件

    def save_to_config(self):
        """将备忘录数据保存到配置文件，使用GBK编码"""
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE, encoding='gbk')  # 使用GBK编码读取配置文件

        # 清空当前的配置
        if 'MemoData' not in config.sections():
            config.add_section('MemoData')
        config.remove_section('MemoData')
        config.add_section('MemoData')

        # 将所有栏目及其数量写入配置文件
        for title, data in self.memo_data.items():
            config.set('MemoData', title, str(data["quantity"]))

        # 使用GBK编码保存配置文件
        with open(CONFIG_FILE, 'w', encoding='gbk') as configfile:
            config.write(configfile)

    def load_from_config(self):
        """从配置文件加载备忘录数据"""
        if not os.path.exists(CONFIG_FILE):
            return  # 如果没有配置文件，直接返回

        config = configparser.ConfigParser()
        config.read(CONFIG_FILE, encoding='gbk')  # 使用GBK编码读取配置文件

        if 'MemoData' in config.sections():
            for title, quantity in config.items('MemoData'):
                try:
                    self.memo_data[title] = {"quantity": int(quantity), "button": None, "label": None}
                    self.add_memo_item(title, int(quantity))
                except ValueError:
                    continue  # 如果配置中的数量不是有效的整数，跳过该项

    def show_customize_keys_window(self):
        """显示自定义按键窗口"""
        def on_save_callback():
            """保存自定义按键设置"""
            self.save_to_config()

        custom_keys_window = CustomizeKeysWindow(self.custom_key, on_save_callback)
        custom_keys_window.show()

    def on_exit(self):
        """退出程序"""
        self.tray_icon.hide()
        self.save_to_config()
        QApplication.quit()

    def adjust_window_size(self):
        """根据内容调整窗口大小"""
        self.resize(self.width(), self.height())

    def show_window(self):
        """显示窗口"""
        if not self.isVisible():
            self.show()

    def hide_window(self):
        """隐藏窗口"""
        self.hide()

    def create_tray_icon(self):
        """创建托盘图标"""
        tray_icon = QSystemTrayIcon(self)
        tray_icon.setIcon(QIcon("hupo.png"))  # 替换为合适的图标
        tray_icon.setVisible(True)

        # 创建菜单
        tray_menu = QMenu(self)

        toggle_action = QAction("显示/隐藏", self)
        toggle_action.triggered.connect(self.toggle_window)
        tray_menu.addAction(toggle_action)

        add_action = QAction("添加栏目", self)
        add_action.triggered.connect(self.show_add_column_window)
        tray_menu.addAction(add_action)

        customize_keys_action = QAction("自定义按键", self)
        customize_keys_action.triggered.connect(self.show_customize_keys_window)
        tray_menu.addAction(customize_keys_action)

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.on_exit)
        tray_menu.addAction(exit_action)

        tray_icon.setContextMenu(tray_menu)
        self.tray_icon = tray_icon

    def toggle_window(self):
        """显示/隐藏窗口"""
        if self.isVisible():
            self.hide_window()
        else:
            self.show_window()

    def show_add_column_window(self):
        """显示添加栏目窗口"""
        add_window = QWidget()
        add_window.setWindowTitle("添加栏目")
        add_window.setGeometry(50, 50, 50, 50)

        layout = QVBoxLayout()

        # 栏目名称输入框
        title_label = QLabel("栏目名称：", add_window)
        layout.addWidget(title_label)
        title_entry = QLineEdit(add_window)
        layout.addWidget(title_entry)

        # 数量输入框
        quantity_label = QLabel("数量：", add_window)
        layout.addWidget(quantity_label)
        quantity_entry = QLineEdit(add_window)
        layout.addWidget(quantity_entry)

        def add_column_action():
            title = title_entry.text()
            try:
                quantity = int(quantity_entry.text())
                if title and quantity >= 0:
                    self.memo_data[title] = {"quantity": quantity, "button": None, "label": None}
                    self.add_memo_item(title, quantity)
                    add_window.close()
                    self.save_to_config()  # 保存配置
                else:
                    print("输入无效")
            except ValueError:
                print("请输入有效的数量")

        # 添加按钮
        add_button = QPushButton("添加", add_window)
        add_button.clicked.connect(add_column_action)
        layout.addWidget(add_button)

        add_window.setLayout(layout)

        # Center the window when it opens
        center_window(add_window)

        add_window.show()


def start_app():
    app = QApplication(sys.argv)

    # 创建主窗口
    memo_app = MemoApp()

    # 启动应用
    memo_app.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    start_app()
