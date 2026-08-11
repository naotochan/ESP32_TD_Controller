# TouchDesigner — CYD_TD_Controller (Editor controls)

Cloud CI では TouchDesigner を実行できません。`CYD_TD_Controller.tox` は **TD があるマシン** でインストーラを一度実行して生成してください。

---

## 1. 使い方（推奨）

1. ローカルでインストーラを実行し `td/CYD_TD_Controller.tox` を生成（下記 §2）
2. TD プロジェクトに `CYD_TD_Controller.tox` をドラッグ＆ドロップ
3. COMP の **Editor** ページで **Project Dir** を git リポジトリルート（`editor_ctl.py` があるフォルダ）に設定
4. **Start Setup** → デプロイサーバー + Vite 起動  
   **Edit CYD** → ブラウザで Web エディタを開く  
   **Stop Setup** → 停止  
   **Refresh Status** → `Setupstatus` を更新

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
| `CydEditorExt.py` | COMP 内 Extension（`editor_ctl.py` を subprocess 実行） |
| `parexec_editor.py` | Parameter Execute DAT の `onPulse` コールバック |
| `install_editor_controls.py` | 既存 COMP への Editor ページ追加、または最小 COMP 新規作成 + tox 保存 |

インストーラは Extension / parexec のソースを COMP 内 Text DAT に埋め込むため、保存後の tox は外部 `.py` なしでも動作します。

## 4. Editor パルス配線

- COMP 内 `parexec_editor`（parameterexecuteDAT）: `ops = '..'`（親 COMP のカスタムパラを監視）
- 親 COMP の Editor ページ: `Startsetup` / `Stopsetup` / `Editcyd` / `Refreshstatus` パルス
- `onPulse` → `parent().ext.CydEditorExt` → `editor_ctl start|stop|open|status`
- 結果は **Setupstatus**（読み取り専用 Str）に反映

**CYD** ページ（Active, Listenport, Esp32address, Sendport, Stripsegments, Sendactive）はインストーラが変更しません（新規 COMP 作成時のみ追加）。

## 5. English (short)

1. Generate `td/CYD_TD_Controller.tox` locally by running `install_editor_controls.py` in TD Textport.
2. Drop the tox into your project; set **Project Dir** to the repo root.
3. Use **Start Setup**, **Edit CYD**, **Stop Setup**, **Refresh Status** on the Editor page.
4. Cloud agents cannot run TouchDesigner — commit the tox after generating it on a TD machine.
