import os
import re
import pandas as pd

try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

def detect_encoding(file_path):
    """ファイルの文字コードを自動判定する"""
    if HAS_CHARDET:
        with open(file_path, 'rb') as f:
            raw_data = f.read(2048)
            result = chardet.detect(raw_data)
            return result['encoding'] or 'utf-8'
    else:
        for enc in ['utf-8', 'shift_jis', 'cp932', 'euc-jp']:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    f.read(1024)
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        return 'utf-8'

def normalize_date(date_str):
    """日付を YYYY/MM/DD 形式（ゼロ埋め2桁）に正規化する"""
    if pd.isna(date_str):
        return ""
    
    date_str = str(date_str).strip()
    date_str = date_str.replace('-', '/')
    
    try:
        dt = pd.to_datetime(date_str, format='%Y/%m/%d', errors='coerce')
        if pd.isna(dt):
            dt = pd.to_datetime(date_str, errors='coerce')
            
        if not pd.isna(dt):
            return dt.strftime('%Y/%m/%d')
    except Exception:
        pass
        
    return date_str

def normalize_amount(amount_val):
    """金額から記号やカンマを除去して絶対値の数値にする"""
    if pd.isna(amount_val):
        return 0
    amount_str = str(amount_val).strip()
    # 数字とドット以外の文字（￥、円、カンマ、マイナス記号など）をすべて除去して絶対値にする
    cleaned = re.sub(r'[^\d.]', '', amount_str)
    try:
        return int(float(cleaned))
    except ValueError:
        return 0

def convert_to_mf_journal(input_file, output_file='mf_journal.csv'):
    # 1. 文字コード判定と読み込み
    encoding = detect_encoding(input_file)
    print(f"Reading {input_file} with encoding: {encoding}")
    df_in = pd.read_csv(input_file, encoding=encoding)
    
    # 2. シンプルな8列のヘッダーを定義
    mf_headers = [
        "日付", "借方勘定科目", "借方税区分", "借方金額(円)", 
        "貸方勘定科目", "貸方税区分", "貸方金額(円)", "摘要"
    ]
    
    # 出力用データフレームの初期化
    df_out = pd.DataFrame(columns=mf_headers)
    
    # 3. 共通項目のマッピングと正規化
    df_out["日付"] = df_in["date"].apply(normalize_date)
    df_out["摘要"] = df_in["memo"].fillna("")
    
    # 金額の正規化（絶対値に変換）
    amounts = df_in["amount"].apply(normalize_amount)
    df_out["借方金額(円)"] = amounts
    df_out["貸方金額(円)"] = amounts
    
    # 4. amountのマイナス判定と条件分岐ロジックの適用
    for idx, row in df_in.iterrows():
        io_type = str(row["io"]).strip().lower()
        payment_acc = str(row["payment_account"]).strip()
        category_hint = str(row["category_hint"]).strip()
        amount_str = str(row["amount"]).strip()
        
        # amount に「-」が含まれているか判定して逆仕訳にする
        if '-' in amount_str:
            if io_type == 'income':
                io_type = 'expense'
            elif io_type == 'expense':
                io_type = 'income'
        
        # 反転判定後の io_type に基づいて仕訳を生成
        if io_type == 'income':
            df_out.at[idx, "借方勘定科目"] = payment_acc
            df_out.at[idx, "借方税区分"] = "対象外"
            df_out.at[idx, "貸方勘定科目"] = "売上高"
            df_out.at[idx, "貸方税区分"] = "課税売上10%"
        else:
            df_out.at[idx, "借方勘定科目"] = category_hint
            df_out.at[idx, "借方税区分"] = "課税仕入10%"
            df_out.at[idx, "貸方勘定科目"] = payment_acc
            df_out.at[idx, "貸方税区分"] = "対象外"

    # 5. 指定形式（UTF-8 BOM付き）でCSV出力
    df_out.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"Successfully generated: {output_file}")

if __name__ == "__main__":
    input_filename = 'input.csv'
    
    if os.path.exists(input_filename):
        convert_to_mf_journal(input_filename)
    else:
        print(f"Error: {input_filename} を見つけられませんでした。")
