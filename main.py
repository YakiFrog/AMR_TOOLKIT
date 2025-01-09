import sys
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QMenuBar, QMenu, QLabel, QPushButton,
                            QFileDialog, QScrollArea, QSplitter, QGesture, 
                            QPinchGesture, QSlider)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QEvent, QSize
from PyQt6.QtGui import QPixmap, QImage, QWheelEvent

# ピンチジェスチャーの感度調整用定数
SCALE_SENSITIVITY = 0.2

# スケール関連の定数を追加
MIN_SCALE = 0.02  # 1/50 (スライダー値1に対応)
MAX_SCALE = 2.0   # 100/50 (スライダー値100に対応)
DEFAULT_SCALE = 1.0  # 50/50 (スライダー値50に対応)

class CustomScrollArea(QScrollArea):
    """カスタムスクロールエリアクラス
    画像の表示領域とスクロール・ズーム機能を提供"""
    scale_changed = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.last_pos = None
        self.mouse_pressed = False
        
        # ジェスチャー設定を1箇所に集約
        for attr in [self, self.viewport()]:
            attr.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.grabGesture(Qt.GestureType.PinchGesture)

    def mousePressEvent(self, event):
        """マウス押下時のイベント処理
        左クリックでドラッグ開始"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed = True
            self.last_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """マウス移動時のイベント処理
        ドラッグによるスクロール処理を実装"""
        if self.mouse_pressed and self.last_pos:
            delta = event.pos() - self.last_pos
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y())
            self.last_pos = event.pos()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # 現在のスケールを考慮して調整
            factor = 1.04 if event.angleDelta().y() > 0 else 0.96
            self.scale_changed.emit(factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def event(self, event):
        # ジェスチャー処理を簡略化
        if event.type() == QEvent.Type.Gesture:
            if gesture := event.gesture(Qt.GestureType.PinchGesture):
                # ピンチジェスチャーのスケール係数をスライダーの単位に合わせて調整
                total_scale = gesture.totalScaleFactor()
                if abs(total_scale - 1.0) > 0.01:
                    # より滑らかなスケーリングのために調整
                    scale = 1.0 + ((total_scale - 1.0) * 0.05)
                    self.scale_changed.emit(scale)
                return True
        return super().event(event)

class ImageViewer(QWidget):
    """画像表示用ウィジェット
    PGM画像の表示とズーム機能を管理"""
    # スケール変更通知用のシグナルを追加
    scale_changed = pyqtSignal(float)
    
    def __init__(self):
        super().__init__()
        self.scale_factor = 1.0  # 画像の拡大率
        self.current_pixmap = None  # 現在表示中の画像
        
        self.setup_display()
        self.setup_scroll_area()

    def setup_display(self):
        """画像表示用ラベルの設定を集約"""
        self.pgm_display = QLabel()
        self.pgm_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pgm_display.setStyleSheet("background-color: white;")

    def setup_scroll_area(self):
        """スクロールエリアの設定を集約"""
        self.scroll_area = CustomScrollArea()
        self.scroll_area.setWidget(self.pgm_display)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumSize(600, 500)
        self.scroll_area.setStyleSheet("QScrollArea { border: 2px solid #ccc; background-color: white; }")
        self.scroll_area.scale_changed.connect(self.handle_scale_change)

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.scroll_area)

    def load_image(self, img_array, width, height):
        """PGM画像データを読み込んで表示"""
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
        """ジェスチャーやホイールによるスケール変更を処理"""
        # スケール係数の範囲を制限（例: 0.1 から 10.0）
        new_scale = self.scale_factor * factor
        # スケールの範囲をスライダーと同じに制限
        if MIN_SCALE <= new_scale <= MAX_SCALE:
            self.scale_factor = new_scale
            self.update_display()
            # スケール変更を通知
            self.scale_changed.emit(self.scale_factor)

    def update_display(self):
        """画像の表示を更新
        スケールファクターに応じて画像サイズを変更"""
        if self.current_pixmap:
            new_size = QSize(
                int(self.current_pixmap.width() * self.scale_factor),
                int(self.current_pixmap.height() * self.scale_factor)
            )
            if (current := self.pgm_display.pixmap()) and current.size() == new_size:
                return
            
            scaled_pixmap = self.current_pixmap.scaled(
                new_size, 
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            self.pgm_display.setPixmap(scaled_pixmap)
            self.pgm_display.adjustSize() # 必要な場合に画像サイズを調整

class MenuPanel(QWidget):
    """メニューパネル
    ファイル操作とズーム制御のUIを提供"""
    
    # シグナルの定義
    file_selected = pyqtSignal(str)  # ファイル選択時のシグナル
    zoom_value_changed = pyqtSignal(int)  # ズーム値変更時のシグナル
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """UIコンポーネントの初期化と配置"""
        layout = QVBoxLayout()
        self.setStyleSheet("background-color: #e8e8e8;")
        self.setFixedHeight(120)

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
        
        # ズームコントロールをメソッドに分離
        zoom_widget = self.create_zoom_controls()
        
        layout.addWidget(menu_bar)
        layout.addWidget(self.select_button) # 1. ファイル選択ボタン
        layout.addWidget(zoom_widget) # 2. ズームコントロール
        self.setLayout(layout)

    def create_zoom_controls(self):
        """ズームコントロールの作成を集約"""
        zoom_widget = QWidget()
        zoom_layout = QHBoxLayout()
        
        # ズームスライダーの設定
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(1, 100)
        self.zoom_slider.setValue(50)
        
        # ズーム率表示用ラベル
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(50)  # ラベルの最小幅を設定
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # スライダー値変更時の処理を更新
        def update_zoom(value):
            zoom_percent = int((value / 50.0) * 100)
            self.zoom_label.setText(f"{zoom_percent}%")
            self.zoom_value_changed.emit(value)
        
        self.zoom_slider.valueChanged.connect(update_zoom)
        
        reset_button = QPushButton("Reset Zoom")
        reset_button.clicked.connect(lambda: self.zoom_slider.setValue(50))
        
        # レイアウトにコンポーネントを追加
        zoom_layout.addWidget(self.zoom_slider, stretch=1)  # スライダーを伸縮可能に
        zoom_layout.addWidget(self.zoom_label)
        zoom_layout.addWidget(reset_button)
        zoom_widget.setLayout(zoom_layout)
        return zoom_widget

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
    """画像分析パネル
    ヒストグラム表示や統計情報、画像処理オプションを提供"""
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
    """メインウィンドウ
    アプリケーションの主要なUIと機能を統合"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PGM画像ビューア")  # ウィンドウタイトルを日本語に
        self.setGeometry(100, 100, 1200, 800)
        
        # メインウィジェットとレイアウト
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左側パネル
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(5) # スペースを追加
        left_layout.setContentsMargins(5, 5, 5, 5) # マージンを追加
        
        # メニューパネル
        self.menu_panel = MenuPanel()
        
        # 画像ビューア
        self.image_viewer = ImageViewer()
        
        # シグナルの接続（シグナルが発生したときにスロットを呼び出す）
        self.menu_panel.file_selected.connect(self.load_pgm_file)
        self.menu_panel.zoom_value_changed.connect(self.handle_zoom_value_changed)
        # ImageViewerからのスケール変更通知を処理
        self.image_viewer.scale_changed.connect(self.handle_scale_changed)
        
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
        """PGMファイルを読み込む
        Parameters:
            file_path (str): 読み込むPGMファイルのパス
        """
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

    def handle_zoom_value_changed(self, value):
        """ズームスライダーの値変更を処理
        Parameters:
            value (int): スライダーの現在値（1-100）
        """
        scale_factor = value / 50.0
        self.image_viewer.scale_factor = scale_factor
        self.image_viewer.update_display()

    def handle_scale_changed(self, scale_factor):
        """ImageViewerからのスケール変更通知を処理"""
        # スライダー値を更新（シグナルの発行を防ぐためにblockSignals使用）
        slider_value = int(scale_factor * 50)
        self.menu_panel.zoom_slider.blockSignals(True)
        self.menu_panel.zoom_slider.setValue(slider_value)
        self.menu_panel.zoom_slider.blockSignals(False)
        # ズーム率表示を更新
        zoom_percent = int(scale_factor * 100)
        self.menu_panel.zoom_label.setText(f"{zoom_percent}%")

def main():
    """アプリケーションのメインエントリーポイント"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
