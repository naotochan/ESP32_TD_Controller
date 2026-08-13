# TouchDesigner — CYD_TD_Controller (Editor controls)

Cloud CI では TouchDesigner を実行できません。`CYD_TD_Controller.tox` は **TD があるマシン** でインストーラを一度実行して生成してください。

---

## 1. 使い方（推奨）

1. ローカルでインストーラを実行し `td/CYD_TD_Controller.tox` を生成（下記 §2）
2. TD プロジェクトに `CYD_TD_Controller.tox` をドラッグ＆ドロップ
3. COMP の **Editor** ページで **Project Dir** を確認（既定はこの `.toe` のフォルダ = `project.folder`）
4. **Setup** パルス → リポジトリが無ければ `.toe` フォルダ内に `CYD_TD_Controller/` へ shallow clone、その後 `uv sync` / `.env` テンプレ / `npm install`（**サーバーは起動しない**）
5. **Setup** 成功後、**Run** / **Refresh Status** が有効になる → **Run** ON でデプロイサーバー + Vite 起動  
   **Edit CYD** → ブラウザで Web エディタを開く（**Run** ON 時のみ有効；**Flash MicroPython** もエディタ内）  
   **Run** OFF → 停止  
   （Setup 完了までは **Run** / **Refresh Status** は無効 — 先に **Setup** をパルス。**Edit CYD** は Setup 完了かつ **Run** ON のときのみ有効）

`editor_ctl.py` が既に **Project Dir** 直下にある場合（開発用にリポジトリを toe ルートに置いている等）は clone せず、そのフォルダをそのまま使います。

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

Editor ページの表示順（上から）:

1. **Project Dir** (`Projectdir`)
2. **Setup** — パルス（clone + deps ensure、サーバー起動なし）
3. **Setup Status** (`Setupstatus`) — 読み取り専用 Str。**Setup** の直下。`complete` または `incomplete`
4. **Run** — Toggle（`onValueChange` → start/stop；Setup 成功後のみ有効）
5. **Status** (`Runstatus`) — 読み取り専用 Str。**Run** の直下。`running (http://localhost:5173)` または `stopped`
6. **Edit CYD** (`Editcyd`) — パルス（Setup 成功かつ **Run** ON のときのみ有効）
7. **Refresh Status** (`Refreshstatus`) — パルス（Setup 成功後のみ有効）
8. **Serial Port** (`Serialport`) — 読み取り専用 Str（status JSON から更新）

- COMP 内 `parexec_editor`（parameterexecuteDAT）: `ops = '..'`（親 COMP のカスタムパラを監視）
- `onPulse` / `OnRunChanged` → `parent().ext.CydEditorExt` → `editor_ctl setup|start|stop|open|status`
- **Flash MicroPython** は Web エディタのみ（Deploy 横）。CLI: `editor_ctl flash`
- TD の **Flashmicropython** パラメータは v0.12.4 で削除（インストーラが既存 tox から破棄）

COMP のノードビューア（`bg`）には **Run** 状態とバージョンがリアルタイム表示されます（ポート 3737/5173）。

**CYD** ページ: Active 以外（Listenport, Esp32address, Sendport, Stripsegments, Sendactive）は `enableExpr = me.par.Active` で Active ON 時のみ有効。新規 COMP 作成時に CYD ページを追加し、既存 tox でもインストーラ再実行で enableExpr を適用。

## 5. English (short)

1. Generate `td/CYD_TD_Controller.tox` locally by running `install_editor_controls.py` in TD Textport.
2. Drop the tox into your project; **Project Dir** defaults to the `.toe` folder.
3. Pulse **Setup** to shallow-clone into `CYD_TD_Controller/` when needed and install deps (no servers). **Setup Status** (`Setupstatus`) is `complete` or `incomplete`. **Status** (`Runstatus`) under **Run** shows `running (...)` or `stopped`.
4. After **Setup** succeeds, toggle **Run** ON for deploy server + Vite; use **Edit CYD** only while **Run** is ON (Web editor has **Flash MicroPython** next to Deploy); **Refresh Status** anytime after setup. Until setup completes, **Run** and **Refresh Status** are disabled — pulse **Setup** first.
5. Cloud agents cannot run TouchDesigner — commit the tox after generating it on a TD machine.
