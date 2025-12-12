# PDFwiki

**PDFwiki** は、ローカルのPDFファイルを高速に全文検索し、文脈をスマートにプレビューできるデスクトップアプリケーションです。
小説や論文など、テキスト中心のPDF閲覧と検索に最適化されています。

![License](https://img.shields.io/badge/license-AGPL%20v3.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

## ✨ 主な機能

### 🔍 高速全文検索
- **瞬時の検索**: PyMuPDFを使用した高速なテキスト抽出と検索。
- **インメモリ処理**: PDFの内容をメモリに展開し、数千ページでもストレスのない検索を実現。
- **文脈表示**: 検索ヒット箇所の前後を表示し、ページを開かなくても大まかな内容を確認できます。

### 🖼️ インスタントプレビュー & ハイライト (v1.1.0 New!)
- **オンデマンド表示**: 検索結果をダブルクリックした時だけ、瞬時にプレビューを表示します。
- **自動ハイライト**: 検索キーワードが含まれる箇所をピンポイントで黄色くマーキングして表示します。
- **軽量動作**: 必要なページだけをメモリ上で画像化するため、PCの容量を圧迫しません。

### 🎨 モダンUI
- **テーマ対応**: ライト/ダークモードの切り替え（システム設定への自動追従も可能）。
- **分割レイアウト**: 検索リストとプレビューを並べて効率的に閲覧できます。

## 📦 インストールと実行

1. [Releases](https://github.com/ryojihido/PDFwiki/releases) ページから最新の `PDFwiki_v1.1.0.zip` をダウンロードしてください。
2. 解凍したフォルダ内の `PDFwiki.exe` をダブルクリックして起動します。

## ⚠️ 「WindowsによってPCが保護されました」と表示される場合

本ソフトウェアは個人開発であり、Microsoftのコード署名証明書を購入していないため、初回起動時にWindows SmartScreenの警告が表示されることがあります。
**ウイルスではありませんのでご安心ください。**

以下の手順で起動してください：
1. ブルーの警告画面にある **「詳細情報」** というテキストリンクをクリックします。
2. 画面右下に現れる **「実行」** ボタンをクリックします。

※ 2回目以降は表示されなくなります。

## 🛠️ 技術スタック & クレジット

このソフトウェアは、以下のオープンソースライブラリを使用して開発されています。

- **Language**: Python 3.11
- **PyMuPDF** (AGPL v3.0) - © Artifex Software, Inc.
- **ttkbootstrap** (MIT License) - © Israel Dryer
- **Darkdetect** (3-clause BSD License)

## 📝 ライセンス
本ソフトウェアは **GNU Affero General Public License v3.0 (AGPL v3.0)** の下で公開されています。
ソースコードの公開義務等の詳細については [LICENSE](./LICENSE) ファイルをご確認ください。

Copyright (c) 2025 RyojiHido