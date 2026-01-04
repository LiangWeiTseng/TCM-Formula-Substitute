import sys
import os

# 確保程式能找到 src 下的模組
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# 導入你的 gradio 介面
# 這裡要根據你 formula_altsearch 裡面定義 gradio 的位置來修改
from formula_altsearch.gui import demo 

if __name__ == "__main__":
    # HF Spaces 預設使用 7860 埠口
    demo.launch(server_name="0.0.0.0", server_port=7860)
