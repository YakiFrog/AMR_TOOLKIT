import sys
import numpy as np
from PIL import Image
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QMenuBar, QMenu, QLabel, QPushButton,
                            QFileDialog, QScrollArea, QSplitter)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QEvent, QSize  # QSizeをQtCoreからインポート
from PyQt6.QtGui import QPixmap, QImage, QWheelEvent
from PyQt6.QtWidgets import QGesture, QPinchGesture

class CustomScrollArea(QScrollArea):
    scale_changed = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.last_pos = None
        self.mouse_pressed = False
        
        # タッチスクリーンとジェスチャーのサポートを有効化
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.grabGesture(Qt.GestureType.PinchGesture)
        self.viewport().installEventFilter(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed = True
            self.last_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()  # イベントを受け付けたことを明示
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()  # イベントを受け付けたことを明示
        else:
            super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.mouse_pressed and self.last_pos is not None:
            delta = event.pos() - self.last_pos
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y())
            self.last_pos = event.pos()
            event.accept()  # イベントを受け付けたことを明示
        else:
            super().mouseMoveEvent(event)
    
    def eventFilter(self, obj, event):
        if obj is self.viewport():
            if event.type() == QEvent.Type.Gesture:
                gesture = event.gesture(Qt.GestureType.PinchGesture)
                if gesture:
                    scale_factor = gesture.scaleFactor()
                    
                    # 過剰な呼び出しを防ぐ
                    if abs(scale_factor - 1.0) > 0.01:
                        self.scale_changed.emit(scale_factor)
                    return True
        return super().eventFilter(obj, event)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.1 if delta > 0 else 0.9
            self.scale_changed.emit(factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def event(self, event):
        if event.type() == QEvent.Type.Gesture:
            gesture = event.gesture(Qt.GestureType.PinchGesture)
            if isinstance(gesture, QPinchGesture):
                current_scale = gesture.totalScaleFactor()
                if current_scale != 1.0:  # ジェスチャーの状態チェックを単純化
                    self.scale_changed.emit(current_scale)
                return True
        return super().event(event)

class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.scale_factor = 1.0
        self.current_pixmap = None
        
        # 画像表示用ラベル
        self.pgm_display = QLabel()
        self.pgm_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pgm_display.setStyleSheet("background-color: white;")
        
        # スクロールエリア
        self.scroll_area = CustomScrollArea()
        self.scroll_area.setWidget(self.pgm_display)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumSize(600, 500)
        self.scroll_area.setStyleSheet("QScrollArea { border: 2px solid #ccc; background-color: white; }")
        
        # スクロールエリアのスケール変更シグナルを接続
        self.scroll_area.scale_changed.connect(self.handle_scale_change)
        
        # レイアウト
        layout = QVBoxLayout()
        layout.addWidget(self.scroll_area)
        self.setLayout(layout)

        # タッチイベントを有効化
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        
        # ジェスチャーを有効化
        self.grabGesture(Qt.GestureType.PinchGesture)

    def load_image(self, img_array, width, height):
        bytes_per_line = width
        q_img = QImage(img_array.data, width, height, bytes_per_line,
                      QImage.Format.Format_Grayscale8)
        self.current_pixmap = QPixmap.fromImage(q_img)
        self.update_display()

    def zoom_in(self):
        self.scale_factor *= 1.2
        self.update_display()

    def zoom_out(self):
        self.scale_factor /= 1.2
        self.update_display()

    def zoom_reset(self):
        self.scale_factor = 1.0
        self.update_display()

    def handle_scale_change(self, factor):
        # スケール係数の範囲を制限（例: 0.1 から 10.0）
        new_scale = self.scale_factor * factor
        if 0.1 <= new_scale <= 10.0:
            self.scale_factor = new_scale
            self.update_display()

    def update_display(self):
        if self.current_pixmap:
            current_pixmap = self.pgm_display.pixmap()
            new_width = int(self.current_pixmap.width() * self.scale_factor)
            new_height = int(self.current_pixmap.height() * self.scale_factor)
            new_size = QSize(new_width, new_height)
            
            # 同じスケールサイズなら再描画しない
            if current_pixmap and current_pixmap.size() == new_size:
                return

            scaled_pixmap = self.current_pixmap.scaled(
                new_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.pgm_display.setPixmap(scaled_pixmap)
            self.pgm_display.adjustSize()

    def event(self, event):
        if event.type() == QEvent.Type.Gesture:
            return self.scroll_area.eventFilter(self.scroll_area.viewport(), event)
        return super().event(event)

class MenuPanel(QWidget):
    # シグナルの定義
    file_selected = pyqtSignal(str)
    zoom_in_clicked = pyqtSignal()    # 追加
    zoom_out_clicked = pyqtSignal()   # 追加
    zoom_reset_clicked = pyqtSignal() # 追加
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.setStyleSheet("background-color: #e8e8e8;")
        self.setFixedHeight(200)

        # メニューバー
        menu_bar = QMenuBar()
        file_menu = QMenu("File", self)
        edit_menu = QMenu("Edit", self)
        
        # ファイルメニューのアクションを作成
        open_action = file_menu.addAction("Open PGM")
        save_action = file_menu.addAction("Save PGM")
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        
        menu_bar.addMenu(file_menu)
        menu_bar.addMenu(edit_menu)

        # ボタン
        self.select_button = QPushButton("Select PGM File")
        self.select_button.clicked.connect(self.open_file_dialog)
        
        # ズームコントロール
        zoom_widget = QWidget()
        zoom_layout = QHBoxLayout()
        
        # ズームボタンの作成と接続
        self.zoom_in_button = QPushButton("+")
        self.zoom_out_button = QPushButton("-")
        self.zoom_reset_button = QPushButton("Reset")
        
        self.zoom_in_button.clicked.connect(self.zoom_in_clicked.emit)
        self.zoom_out_button.clicked.connect(self.zoom_out_clicked.emit)
        self.zoom_reset_button.clicked.connect(self.zoom_reset_clicked.emit)
        
        zoom_layout.addWidget(self.zoom_in_button)
        zoom_layout.addWidget(self.zoom_out_button)
        zoom_layout.addWidget(self.zoom_reset_button)
        zoom_widget.setLayout(zoom_layout)

        layout.addWidget(menu_bar)
        layout.addWidget(self.select_button)
        layout.addWidget(zoom_widget)
        self.setLayout(layout)

        # ボタンとズームコントロールを返す必要はなくなりました
        return self.select_button

    def open_file_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open PGM File",
            "",
            "PGM Files (*.pgm);;All Files (*)"
        )
        if file_name:
            self.file_selected.emit(file_name)  # シグナルを発信

class AnalysisPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setStyleSheet("QWidget { background-color: #f5f5f5; border-radius: 5px; }")

        titles = ["Histogram", "Statistics", "Processing Options"]
        for title in titles:
            widget = QWidget()
            widget_layout = QVBoxLayout(widget)
            
            title_label = QLabel(title)
            title_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: bold;
                    padding: 5px;
                    background-color: #e0e0e0;
                    border-radius: 3px;
                }
            """)
            
            content = QWidget()
            content.setStyleSheet("""
                QWidget {
                    background-color: white;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                }
            """)
            content.setMinimumHeight(200)
            
            widget_layout.addWidget(title_label)
            widget_layout.addWidget(content)
            layout.addWidget(widget)

        self.setLayout(layout)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 Window")
        self.setGeometry(100, 100, 1200, 800)
        
        # メインウィジェットとレイアウト
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左側パネル
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)
        left_layout.setContentsMargins(10, 10, 10, 10)
        
        # 画像ビューアを先に作成
        self.image_viewer = ImageViewer()
        
        # メニューパネル
        self.menu_panel = MenuPanel()
        
        # シグナルの接続
        self.menu_panel.file_selected.connect(self.load_pgm_file)
        self.menu_panel.zoom_in_clicked.connect(self.image_viewer.zoom_in)
        self.menu_panel.zoom_out_clicked.connect(self.image_viewer.zoom_out)
        self.menu_panel.zoom_reset_clicked.connect(self.image_viewer.zoom_reset)
        
        # 左側レイアウトの構成
        left_layout.addWidget(self.menu_panel)
        left_layout.addWidget(self.image_viewer)
        left_widget.setLayout(left_layout)
        
        # 分析パネル
        analysis_panel = AnalysisPanel()
        
        # スプリッタの設定
        splitter.addWidget(left_widget)
        splitter.addWidget(analysis_panel)
        splitter.setSizes([600, 400])
        
        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def load_pgm_file(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                magic = f.readline().decode('ascii').strip()
                if (magic != 'P5'):
                    raise ValueError('Not a P5 PGM file')

                while True:
                    line = f.readline().decode('ascii').strip()
                    if not line.startswith('#'):
                        break
                width, height = map(int, line.split())
                max_val = int(f.readline().decode('ascii').strip())
                
                data = f.read()
                img_array = np.frombuffer(data, dtype=np.uint8)
                img_array = img_array.reshape((height, width))
                
                self.image_viewer.load_image(img_array, width, height)
                print(f"Successfully loaded image: {width}x{height}, max value: {max_val}")

        except Exception as e:
            print(f"Error loading PGM file: {str(e)}")
            import traceback
            traceback.print_exc()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
