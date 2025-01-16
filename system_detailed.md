# 詳細システム構造

## 1. クラス間の依存関係
```mermaid
classDiagram
    MainWindow --> ImageViewer
    MainWindow --> RightPanel
    MainWindow --> MenuPanel
    ImageViewer --> Layer
    ImageViewer --> Waypoint
    ImageViewer --> DrawableLabel
    RightPanel --> LayerControl
    RightPanel --> WaypointListItem
    RightPanel --> FormatEditorPanel
    
    class MainWindow {
        +ImageViewer image_viewer
        +RightPanel analysis_panel
        +MenuPanel menu_panel
        +handle_export()
        +load_yaml_file()
    }
    
    class ImageViewer {
        +scale_factor: float
        +layers: List[Layer]
        +waypoints: List[Waypoint]
        +setup_display()
        +update_display()
        +handle_waypoint_edited()
    }
    
    class Waypoint {
        +number: int
        +pixel_x: float
        +pixel_y: float
        +angle: float
        +attributes: Dict
        +update_metric_coordinates()
    }
```

## 2. シグナル・スロット詳細フロー
```mermaid
sequenceDiagram
    participant UI as ユーザー操作
    participant MW as MainWindow
    participant IV as ImageViewer
    participant WP as Waypoint
    participant RP as RightPanel
    
    UI->>MW: ファイル選択
    MW->>IV: load_pgm_file()
    IV->>IV: load_image()
    
    UI->>IV: ウェイポイント追加
    IV->>WP: create
    IV->>RP: waypoint_added.emit()
    
    UI->>RP: 属性編集
    RP->>WP: update_attributes()
    RP->>IV: waypoint_edited.emit()
```

## 3. レイヤーシステムの詳細構造
```mermaid
graph TB
    subgraph LayerSystem [レイヤー管理システム]
        direction TB
        LC[LayerControl] --> LM[Layer Manager]
        LM --> Layers[レイヤー群]
        
        subgraph Layers
            PGM[PGMレイヤー]
            Draw[描画レイヤー]
            Path[パスレイヤー]
            WP[ウェイポイントレイヤー]
            Origin[原点レイヤー]
        end
        
        LM --> Properties{プロパティ}
        Properties --> Visible[可視性]
        Properties --> Opacity[不透明度]
        Properties --> ZOrder[重ね順]
    end
```

## 4. データ保存形式の詳細
### 4.1 ウェイポイントYAML形式
```yaml
format_version: '1.0'
waypoints:
  - number: 1
    x: 10.5
    y: 20.3
    angle_degrees: 45.0
    angle_radians: 0.785
    actions:
      - type: "move_forward"
        distance: 1.0
      - type: "turn"
        angle: 90.0

  - number: 2
    x: 15.2
    y: 25.8
    angle_degrees: 90.0
    angle_radians: 1.571
    actions:
      - type: "pause"
        duration: 5.0
```

## 5. イベント処理の詳細フロー
```mermaid
stateDiagram-v2
    [*] --> Idle
    
    state Idle {
        [*] --> Ready
        Ready --> MouseOver: マウス移動
        MouseOver --> Ready: マウス離脱
    }
    
    state WaypointEdit {
        [*] --> SelectMode
        SelectMode --> MoveMode: 通常クリック
        SelectMode --> AngleMode: Shiftクリック
        MoveMode --> SelectMode: マウスリリース
        AngleMode --> SelectMode: マウスリリース
    }
    
    state DrawingMode {
        [*] --> PenMode
        PenMode --> EraserMode: モード切替
        PenMode --> Drawing: マウスドラッグ
        EraserMode --> Erasing: マウスドラッグ
    }
```

## 6. エラー処理フロー
```mermaid
graph TB
    Error[エラー発生] --> Type{種類判定}
    
    Type -->|ファイル| FileError[ファイルエラー]
    Type -->|フォーマット| FormatError[フォーマットエラー]
    Type -->|操作| OperationError[操作エラー]
    
    FileError --> FL{レベル判定}
    FL -->|Critical| FC[致命的]
    FL -->|Warning| FW[警告]
    
    FormatError --> FE{検証}
    FE -->|Invalid| FEI[無効なフォーマット]
