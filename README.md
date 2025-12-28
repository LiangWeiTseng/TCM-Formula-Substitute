為了解決科中缺藥使用GPT和Python協助寫出來的小程式。來源是衛福部中藥許可證的順天堂公司科中，若有建議或想複製代碼自行修改運用的都歡迎，也可以自己新增dictionary來擴充方劑資料庫。

致謝：曾建霖的python教學、呂易芩的討論與idea

## 安裝

1. 安裝 [Python >= 3.9](https://www.python.org/downloads/)

2. 下載套件原始檔後於該目錄下執行：
   ```
   pip install .[gui]
   ```

   > 若不使用圖形介面，可改用精簡安裝： `pip install .`

## 操作

```
# 查看說明文件
fas -h

# 啟動本地伺服器，並在瀏覽器開啟圖形操作介面
fas g

# 查看 s (search) 子命令的說明文件
fas s -h

# 搜尋科中配方「香砂六君子湯4克+四物湯4克」的替代組合
fas s 香砂六君子湯:4 四物湯:4

# 搜尋上述組合，限定最多 2 個複方及 3 個單方，複方最低劑量 2，單方最低劑量 1
fas s 香砂六君子湯:4 四物湯:4 -C 2 -S 3 -cd 2 -sd 1

# 搜尋科中配方「桂枝湯9克」的替代組合，且排除使用「小建中湯」、「葛根湯」
fas s 桂枝湯:9 -e 小建中湯 -e 葛根湯

# 搜尋生藥「桂枝16克+茯苓13克+白朮10克+炙甘草6克」的科中組合，限定最多 0 個複方及 4 個單方
fas s --raw 桂枝:16 茯苓:13 白朮:10 炙甘草:6 -C 0 -S 4

# 列出資料庫中所有科中品項
fas l

# 列出資料庫中含有「苓」及「桂」的科中品項，例如「苓桂朮甘湯」、「桂枝茯苓丸」
fas l 苓 桂

# 列出資料庫中所有生藥
fas l --raw

# 列出資料庫中所有科中品項並輸出至 list.txt 檔案
fas l >list.txt

# 列出資料庫中所有科中品項並輸出至 list.txt 檔案 (Windows)
# Windows 預設使用 Big5 (cp950) 編碼，需要先設定為 UTF8 編碼輸出以免發生編碼錯誤
(set PYTHONUTF8=1) && fas l >list.txt

# 將下載的 CSV 中醫藥證檔案轉換為資料庫
#
# 註1：下載及轉檔方式詳見 fas c -h
#
# 註2：藥證原始檔有許多格式不統一之處，程式未必都能順利分析，
# 且藥物有別名問題（例如附子 vs 製附子 vs 炮附子 vs 附子(製)），
# 請檢查錯誤訊息及對原始檔或轉出的資料庫檔做適當修改。
#
# 註3：本專案預先製作的資料庫檔案可查詢 fas s -h 中 -d 指令的預設路徑，
# 可進入該目錄下複製想用的資料庫檔案到任意目錄下使用。
#
fas c 中醫藥許可證_20250101.csv mydb.yaml

# 將下載的中醫藥證檔案轉換為資料庫，篩選只匯入廠商「科達」的品項
fas c 中醫藥許可證_20250101.csv mydb.yaml --vendor 科達

# 在自訂資料庫檔案搜尋
fas s -d mydb.yaml 桂枝湯:9
```

## 開發

下載套件原始檔後於該目錄下執行：

```
# 在 .venv 目錄建立虛擬環境
python -m venv .venv

# 進入此虛擬環境 (Windows)
.venv\Scripts\activate

# 進入此虛擬環境 (Linux)
source .venv/bin/activate

# 安裝套件為編輯模式
pip install -e .[gui]

# 安裝開發相關套件
pip install --group dev

# 檢查原始碼格式
flake8 .

# 執行單元測試
python -m unittest

# 輸出命令除錯資訊，並儲存至檔案 (Windows)
(set PYTHONUTF8=1) && fas -v s 香砂六君子湯:4 四物湯:4 >run.log 2>&1

# 退出此虛擬環境 (Windows)
.venv\Scripts\deactivate

# 退出此虛擬環境 (Linux)
source .venv/bin/deactivate
```
