# Māori Chatbot Web App

Flask + Hugging Face Transformers を使った Māori chatbot の Web アプリです。

## 重要
このアプリは **Python バックエンドが必要** です。したがって、**GitHub Pages だけでは動きません**。

公開方法は次の形が現実的です。
- ソースコード: GitHub
- Web公開: Render / Railway / Hugging Face Spaces など

## ローカル実行
```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

## Render で公開する場合
1. GitHub にこのフォルダを push
2. Render で **New Web Service** を選択
3. GitHub リポジトリを接続
4. 以下を設定
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python app.py`
5. Environment Variables を追加
   - `SECRET_KEY`: 長いランダム文字列
   - 必要なら `MODEL_NAME`: 例 `bigscience/bloomz-560m`

## 注意
- `bigscience/bloomz-1b1` は重く、無料枠では厳しいことがあります。
- まずは `bigscience/bloomz-560m` を推奨します。
- もっと軽くしたい場合は別モデルに差し替えてください。

## 主な修正点
- `.DS_Store` など不要ファイルを除外
- セッション履歴の保存まわりを整理
- テンプレート中の JS 文字列埋め込みを安全化
- `health` エンドポイント追加
- Render 用の `Procfile` と `runtime.txt` を追加
