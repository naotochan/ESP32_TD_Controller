# TouchDesigner — CYD_TD_Controller (Editor controls)

Cloud CI では TouchDesigner を実行できません。`CYD_TD_Controller.tox` は **TD があるマシン** でインストーラを一度実行して生成してください。

---

## 1. 使い方（推奨）

1. ローカルでインストーラを実行し `td/CYD_TD_Controller.tox` を生成（下記 §2）
2. TD プロジェクトに `CYD_TD_Controller.tox` をドラッグ＆ドロップ
3. COMP の **Editor** ページで **Project Dir** を確認（既定はこの `.toe` のフォルダ = `project.folder`）
4. **Setup** パルス → リポジトリが無ければ `.toe` フォルダ内に `CYD_TD_Controller/` へ shallow clone、その後 `uv sync` / `.env` テンプレ / `npm install`（**サーバーは起動しない**）
5. **Setup Ready** が `ready` になったら **Run** ON → デプロイサーバー + Vite 起動  
   **Edit CYD** → ブラウザで Web エディタを開く（**Flash MicroPython** もエディタ内）  
   **Run** OFF → 停止

`editor_ctl.py` が既に **Project Dir** 直下にある場合（開発用にリポジトリを toe ルートに置いている等）は clone せず、そのフォルダをそのまま使います。

既存 tox に **Start Setup** / **Stop Setup** パルスがある場合はレガシー（無効化）。**Setup** と **Run** を使ってください。

## 2. tox の生成 / 更新

TouchDesigner の **Textport** で:

```python
exec(open('/path/to/repo/td/install_editor_controls.py').read())
```

または `td/install_editor_controls.py` を Text DAT に読み込み、その DAT を実行。

リポジトリルートが自動検出できない場合は、スクリプト先頭の `PROJECT_DIR` を設定してから再実行:

```python
PROJECT_DIR = "/path/to/repo"
```

成功時: `td/CYD_TD_Controller.tox` が保存されます。

## 3. ファイル構成

| ファイル | 役割 |
|---|---|
| `CydEditorExt.py` | COMP 内 Extension（clone + `editor_ctl.py` を subprocess 実行） |
| `parexec_editor.py` | Parameter Execute DAT の `onPulse` / `onValueChange` コールバック |
| `install_editor_controls.py` | 既存 COMP への Editor ページ追加、または最小 COMP 新規作成 + tox 保存 |

インストーラは Extension / parexec のソースを COMP 内 Text DAT に埋め込むため、保存後の tox は外部 `.py` なしでも動作します。

## 4. Editor パラメータ配線

- COMP 内 `parexec_editor`（parameterexecuteDAT）: `ops = '..'`（親 COMP のカスタムパラを監視）
- 親 COMP の Editor ページ:
  - **Setupready** / **Serialport** — 読み取り専用 Str（status JSON から更新）
  - **Setup** — パルス（clone + deps ensure、サーバー起動なし）
  - **Run** — Toggle（`onValueChange` → start/stop）
  - **Editcyd** / **Refreshstatus** — パルス
- `onPulse` / `OnRunChanged` → `parent().ext.CydEditorExt` → `editor_ctl setup|start|stop|open|status`
- 結果は **Setupstatus**（読み取り専用 Str）と各読み取り専用フィールドに反映
- **Flash MicroPython** は Web エディタ（Deploy 横）。CLI: `editor_ctl flash`
- 既存 tox の **Flashmicropython** パルスは無効化（レガシー）

COMP のノードビューア（`bg`）には **Run** 状態とバージョンがリアルタイム表示されます（ポート 3737/5173）。

**CYD** ページ（Active, Listenport, Esp32address, Sendport, Stripsegments, Sendactive）はインストーラが変更しません（新規 COMP 作成時のみ追加）。

## 5. English (short)

1. Generate `td/CYD_TD_Controller.tox` locally by running `install_editor_controls.py` in TD Textport.
2. Drop the tox into your project; **Project Dir** defaults to the `.toe` folder.
3. Pulse **Setup** to shallow-clone into `CYD_TD_Controller/` when needed and install deps (no servers).
4. When **Setup Ready** is `ready`, toggle **Run**, use **Edit CYD** (Web editor has **Flash MicroPython** next to Deploy), **Refresh Status**.
5. Legacy Start/Stop Setup pulses are disabled on upgraded installs — use **Setup** then **Run**.
6. Cloud agents cannot run TouchDesigner — commit the tox after generating it on a TD machine.
