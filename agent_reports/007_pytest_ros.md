# pytest が ROS Jazzy のプラグインで落ちる件

## 背景

PC のシェルが ROS Jazzy を `source` している。`PYTHONPATH` に `/opt/ros/jazzy/lib/python3.12/site-packages` が入る。このリポジトリの `.venv/bin/pytest` は venv 自身の `include-system-site-packages = false` でも、`PYTHONPATH` 経由で ROS の pytest プラグインを読み込む。

ユーザが README どおり `.venv/bin/pytest -q host/test_clock_format.py` を実行すると、時計のテストではなく ROS 側のプラグインで落ちた。最初は `launch_testing` が `lark` を要求し、続けて `launch_testing_ros_pytest_entrypoint` が未知フック `pytest_launch_collect_makemodule` で `PluginValidationError` になった。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| ROS を source したシェルでも `.venv/bin/pytest -q host/test_clock_format.py` が通る | 完了 |
| 追加の環境変数をユーザが毎回書かなくてよい | 完了 |
| 原因と再現コマンドを残す | 完了 |

## 結論

落ちたのは時計コードではなく、ROS Jazzy の pytest プラグインである。venv の `site-packages` に `tools/pytest_noload.pth` を置くと、Python 起動時に `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` が入り、ROS プラグインを自動読み込みしない。同じ対策を `pytest.ini` の `-p no:...` でも重ねた。

再現確認では、`PYTHONPATH` に ROS を載せた状態で `.venv/bin/pytest -q host/test_clock_format.py` が 3 passed、全テストが 10 passed になった。

venv を作り直したときは README の初期設定どおり `cp tools/pytest_noload.pth .venv/lib/python3.12/site-packages/` が必要である。`.pth` は venv 内なので git には入らない。

```
+---------------------------+     USB 点線      +---------------------------+
| PC                        | - - - - - - - - -> | StackChan                 |
|                           |  （未実施）        |                           |
|  中でやること             |                    |  中でやること             |
|    ROS を source した     |                    |    今回は動かしていない   |
|    シェルで pytest        |                    |                           |
|    ROS プラグインは読ま   |                    |                           |
|    ない                   |                    |                           |
+---------------------------+                    +---------------------------+
```

## 詳細

コマンド： .venv/bin/python -c 'import site; print(site.getsitepackages()[0])'

- 目的： venv の site-packages パスを確認する

引数：
- `-c` — site-packages の先頭パスを表示する短い式

結果：
```
/home/takuya/work/stackchan/.venv/lib/python3.12/site-packages
```

コマンド： cp tools/pytest_noload.pth /home/takuya/work/stackchan/.venv/lib/python3.12/site-packages/zz_stackchan_pytest.pth

- 目的： Python 起動時に pytest のプラグイン自動読み込みを止める .pth を venv に入れる

引数：
- `tools/pytest_noload.pth` — 1 行 `import os; os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"`
- コピー先 — venv の site-packages。名前を `zz_stackchan_pytest.pth` にして後から読ませる

結果：
```
（stdout なし。exit 0）
```

コマンド： .venv/bin/python -c 'import os; print("autoload", os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD"))'

- 目的： .pth が効いて環境変数が入るか確認する

引数：
- `-c` — 環境変数を表示する短い式
- 事前に `PYTHONPATH` へ ROS Jazzy の site-packages を設定
- 事前にシェルの `PYTEST_DISABLE_PLUGIN_AUTOLOAD` を `unset`

結果：
```
autoload 1
```

コマンド： .venv/bin/pytest -q host/test_clock_format.py

- 目的： ユーザが打ったのと同じコマンドが ROS PYTHONPATH 付きでも通るか確認する

引数：
- `-q` — 短い出力
- `host/test_clock_format.py` — 時計フォーマットのテスト
- 作業ディレクトリ — `/home/takuya/work/stackchan`
- 事前に `PYTHONPATH=/opt/ros/jazzy/lib/python3.12/site-packages`

結果：
```
...                                                                      [100%]
3 passed in 0.01s
```

コマンド： .venv/bin/pytest -q

- 目的： host 配下の全テストが同じ条件で通るか確認する

引数：
- `-q` — 短い出力
- `pytest.ini` の `testpaths = host` により host 配下を対象にする
- 事前に `PYTHONPATH=/opt/ros/jazzy/lib/python3.12/site-packages`

結果：
```
..........                                                               [100%]
10 passed in 0.01s
```
