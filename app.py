import sys
import os

# 1. 確保能找到 src 下的模組
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "src"))

# 2. 從 gui 模組導入 create_app 函式
try:
    from formula_altsearch.gui import create_app
except ImportError as e:
    print(f"導入失敗：{e}")
    # 這裡預防萬一，如果路徑不對則顯示當前目錄內容
    print("當前路徑內容:", os.listdir(os.path.join(current_dir, "src", "formula_altsearch")))
    raise

if __name__ == "__main__":
    # 3. 建立並啟動 app
    # Hugging Face Spaces 環境必須綁定在 0.0.0.0 且 7860 埠口
    app = create_app()
    app.launch(server_name="0.0.0.0", server_port=7860)
