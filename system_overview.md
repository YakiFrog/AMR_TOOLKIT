# Map and Waypoint Editor システム概要

## 1. システム構成

### 1.1 メインコンポーネント

#### MainWindow クラス
- アプリケーションのメインウィンドウ
- 画面レイアウトの管理
- 各コンポーネント間の連携制御

#### ImageViewer クラス
- PGM画像の表示と管理
- ウェイポイントの管理
- レイヤー管理システム
- 描画機能
- ズーム・パン機能

#### RightPanel クラス
- レイヤー制御パネル
- ウェイポイントリスト
- フォーマットエディタ
- エクスポート機能

### 1.2 補助コンポーネント

#### MenuPanel クラス
- ファイル操作
- ズーム制御
- グリッド表示切り替え
- 編集履歴（Undo/Redo）

#### LayerControl クラス
- レイヤーの表示/非表示制御
- 透明度制御

#### WaypointListItem クラス
- ウェイポイントのUI表示
- ドラッグ&ドロップによる順序変更
- 削除機能

## 2. データ管理

### 2.1 レイヤーシステム
1. PGMレイヤー（ベース画像）
2. 描画レイヤー（ペン・消しゴム）
3. パスレイヤー（経路表示）
4. ウェイポイントレイヤー
5. 原点レイヤー

### 2.2 ウェイポイント管理
- 位置情報（ピクセル座標・メートル座標）
- 角度情報
- カスタム属性
- YAML形式でのインポート/エクスポート

## 3. 主要機能

### 3.1 ファイル操作
- PGM画像の読み込み
- YAML設定ファイルの読み込み
- 編集済み画像のエクスポート
- ウェイポイントデータのエクスポート

### 3.2 描画機能
- ペンツール
- 消しゴムツール
- サイズ調整
- 不透明度調整

### 3.3 ウェイポイント機能
- 追加・削除
- 位置・角度の編集
- 属性の追加・編集
- 順序の変更
- パス生成

### 3.4 表示制御
- レイヤーの表示/非表示
- 透明度調整
- グリッド表示
- ズーム・パン

## 4. データフォーマット

### 4.1 ウェイポイントフォーマット
```yaml
format_version: '1.0'
format:
  number: int
  x: float
  y: float
  angle_degrees: float
  angle_radians: float
  # カスタム属性を追加可能
```

### 4.2 座標系
- ピクセル座標系（画像ベース）
- メートル座標系（実世界）
- 原点設定による座標変換

## 5. シグナル・スロットシステム

### 5.1 主要シグナル
- ウェイポイント追加/削除/編集
- レイヤー状態変更
- スケール変更
- 履歴更新

### 5.2 イベント処理
- マウス操作（クリック、ドラッグ）
- キーボードショートカット
- ジェスチャー（ピンチズーム）

## 6. 履歴管理システム

### 6.1 操作履歴
- ウェイポイントの追加/削除/編集
- 描画操作
- 最大50件まで保存

### 6.2 Undo/Redo機能
- 状態の保存と復元
- 操作の取り消しと再実行

## 7. ユーザーインターフェース

### 7.1 レイアウト
- 左側：画像表示領域
- 右側：制御パネル
- 上部：メニューバー

### 7.2 視覚的フィードバック
- ツールチップ表示
- 座標情報表示
- 編集状態の表示
- ドラッグ&ドロップのビジュアル効果

## 8. エラー処理

### 8.1 ファイル操作
- ファイル形式の検証
- 読み込みエラーの処理

### 8.2 データ検証
- フォーマット整合性チェック
- 座標範囲の検証
- 属性値の型チェック
