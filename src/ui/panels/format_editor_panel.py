import yaml
from collections import OrderedDict
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
                               QWidget, QTextEdit, QPushButton, QMessageBox, 
                               QFileDialog)
from PySide6.QtCore import Qt, Signal

from ...utils.format_manager import format_manager
from ...utils.format_manager import WAYPOINT_FORMAT

class FormatEditorPanel(QFrame):
    format_updated = Signal(dict)  # フォーマット更新時のシグナル

    def __init__(self):
        super().__init__()
        self.setAutoFillBackground(True)
        # デフォルトのフォーマットを保存
        self.default_format = WAYPOINT_FORMAT
        self.setup_ui()
        format_manager.add_observer(self.on_format_changed)

    def setup_ui(self):
        # パネル自体のスタイルを設定
        self.setStyleSheet("""
            FormatEditorPanel {
                background-color: #f8fafc;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
            }
            QWidget#contentWidget {
                background-color: white;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 12px;
            }
            QTextEdit {
                font-family: 'JetBrains Mono', 'Cascadia Code', monospace;
                font-size: 11px;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 10px;
                background-color: #ffffff;
                color: #1e293b;
                min-height: 150px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # タイトル
        title_label = QLabel("Format Editor")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 600;
                color: #334155;
                padding: 8px 12px;
                background-color: #f1f5f9;
                border-radius: 6px;
            }
        """)
        
        # コンテンツエリア
        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")  # スタイルシートで参照するためのID
        content_widget.setMinimumHeight(200)
        
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(12)
        
        # エディタ
        self.editor = QTextEdit()
        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # ボタンレイアウト
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # 更新ボタン (Primary)
        update_button = QPushButton("Update Format")
        update_button.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                min-width: 110px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        update_button.clicked.connect(self.update_format)

        # リセットボタン (Secondary)
        reset_button = QPushButton("Reset")
        reset_button.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #e2e8f0;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        reset_button.clicked.connect(self.reset_to_default)
        
        # エクスポートボタン (Success)
        export_button = QPushButton("Export")
        export_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #334155;
                border: 1px solid #e2e8f0;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
            }
        """)
        export_button.clicked.connect(self.export_format)
        
        # インポートボタン (Neutral)
        import_button = QPushButton("Import")
        import_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #334155;
                border: 1px solid #e2e8f0;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
            }
        """)
        import_button.clicked.connect(self.import_format)

        # ボタンをレイアウトに追加
        button_layout.addWidget(update_button)
        button_layout.addWidget(reset_button)
        button_layout.addWidget(export_button)
        button_layout.addWidget(import_button)
        
        # コンテンツレイアウトに要素を追加
        content_layout.addWidget(self.editor)
        content_layout.addLayout(button_layout)

        # メインレイアウトに要素を追加
        layout.addWidget(title_label)
        layout.addWidget(content_widget)

        # 初期フォーマットを表示
        self.show_current_format()

    def reset_to_default(self):
        """フォーマットをデフォルトに戻す"""
        # デフォルトのフォーマットを設定
        format_manager.set_format(self.default_format)
        self.show_current_format()
        QMessageBox.information(self, "Success", "Format reset to default")

    def show_current_format(self):
        """現在のフォーマットを表示"""
        # カスタムYAML表示形式を使用
        format_data = format_manager.get_format()
        formatted_text = (
            f"version: '{format_data['version']}'\n"
            f"format:\n"
        )
        
        # format内の各項目を整形
        for key, value in format_data['format'].items():
            formatted_text += f"  {key}: {value}\n"
        
        self.editor.setText(formatted_text)

    def update_format(self):
        try:
            # テキストをYAMLとしてパース
            new_format = yaml.safe_load(self.editor.toPlainText())
            # OrderedDictに変換して順序を保持
            ordered_format = OrderedDict([
                ('version', new_format['version']),
                ('format', OrderedDict())
            ])
            
            # format内の項目を順序を保持して変換
            for key, value in new_format['format'].items():
                ordered_format['format'][key] = value
            
            # 必要なキーの存在チェック
            if 'version' not in ordered_format or 'format' not in ordered_format:
                raise ValueError("Format must contain 'version' and 'format' keys")
            
            # フォーマットを更新
            format_manager.set_format(ordered_format)
            self.format_updated.emit(ordered_format)
            
            # 成功メッセージを表示
            QMessageBox.information(self, "Success", "Format updated successfully")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Invalid format: {str(e)}")
            
    def export_format(self):
        """フォーマットをYAMLファイルとしてエクスポート"""
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export Format",
            "",
            "YAML Files (*.yaml);;All Files (*)"
        )
        if file_name:
            try:
                # カスタム形式でフォーマットを書き出し
                format_data = format_manager.get_format()
                with open(file_name, 'w') as f:
                    f.write(f"version: '{format_data['version']}'\n")
                    f.write("format:\n")
                    for key, value in format_data['format'].items():
                        f.write(f"  {key}: {value}\n")
                QMessageBox.information(self, "Success", "Format exported successfully")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error exporting format: {str(e)}")
                
    def import_format(self):
        """フォーマットをYAMLファイルからインポート"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Import Format",
            "",
            "YAML Files (*.yaml);;All Files (*)"
        )
        if file_name:
            try:
                with open(file_name, 'r') as f:
                    new_format = yaml.safe_load(f)
                format_manager.set_format(new_format)
                self.show_current_format()
                QMessageBox.information(self, "Success", "Format imported successfully")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error importing format: {str(e)}")

    def on_format_changed(self, new_format):
        self.show_current_format()
