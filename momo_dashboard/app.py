from flask import Flask, render_template, jsonify, request
import sqlite3, pandas as pd, re, os
from xml.etree import ElementTree as ET

def parse_xml_to_df(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    def classify_and_extract(sms):
        body = sms.attrib.get("body", "")
        date = sms.attrib.get("readable_date", "")
        transaction_type = amount = recipient = fee = None
        if "received" in body.lower():
            transaction_type = "Incoming Money"
            m = re.search(r"received (\d[\d,]*) RWF from (.+?) \(", body)
            if m: amount, recipient = int(m[1].replace(",", "")), m[2]
        elif "payment of" in body.lower():
            transaction_type = ("Airtime Bill Payments" if "airtime" in body.lower()
                                else "Cash Power Bill Payments" if "cash power" in body.lower()
                                else "Payments To Code Holders")  # Fixed capitalization
            m = re.search(r"payment of (\d[\d,]*) RWF to (.+?) (\\d+)?", body)
            if m: amount, recipient = int(m[1].replace(",", "")), m[2]
            m_fee = re.search(r"Fee (?:was|paid):? (\d[\d,]*) RWF", body)
            if m_fee: fee = int(m_fee[1].replace(",", ""))
        elif "transferred to" in body.lower():
            transaction_type = "Transfers To Mobile Numbers"  # Fixed capitalization
            m = re.search(r"(\d[\d,]*) RWF transferred to (.+?) \(", body)
            if m: amount, recipient = int(m[1].replace(",", "")), m[2]
            m_fee = re.search(r"Fee was:? (\d[\d,]*) RWF", body)
            if m_fee: fee = int(m_fee[1].replace(",", ""))
        elif "withdrawn" in body.lower():
            transaction_type = "Withdrawals From Agents"  # Fixed capitalization
            m = re.search(r"withdrawn (\d[\d,]*) RWF", body)
            if m: amount = int(m[1].replace(",", ""))
            m_agent = re.search(r"via agent: (.+?) \(", body)
            if m_agent: recipient = m_agent[1]
            m_fee = re.search(r"Fee paid: (\d[\d,]*) RWF", body)
            if m_fee: fee = int(m_fee[1].replace(",", ""))
        elif "bank deposit" in body.lower():
            transaction_type = "Bank Deposits"
            m = re.search(r"bank deposit of (\d[\d,]*) RWF", body)
            if m: amount = int(m[1].replace(",", ""))
        elif "internet bundle" in body.lower():
            transaction_type = "Internet And Voice Bundle Purchases"  # Fixed capitalization
            m = re.search(r"bundle of .+ for (\d[\d,]*) RWF", body)
            if m: amount = int(m[1].replace(",", ""))
        elif "one-time password" in body.lower():
            transaction_type = "OTP Notification"
        elif "by direct payment" in body.lower():
            transaction_type = "Transactions Initiated By Third Parties"  # Fixed capitalization
            m = re.search(r"transaction of (\d[\d,]*) RWF", body)
            if m: amount = int(m[1].replace(",", ""))
            m_to = re.search(r"by (.+?) on your", body)
            if m_to: recipient = m_to[1]
        return {
            "date": date, "transaction_type": transaction_type or "Uncategorized",
            "amount": amount, "recipient": recipient, "fee": fee, "body": body
        }
    return pd.DataFrame([classify_and_extract(s) for s in root.findall("sms")])

def init_db(df, db="momo_transactions.db"):
    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS transactions")
        c.execute('''
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, transaction_type TEXT, amount INTEGER,
                recipient TEXT, fee INTEGER, body TEXT
            )''')
        for _, row in df.iterrows():
            # Remove the title case conversion that was causing issues
            transaction_type = row["transaction_type"].strip() if row["transaction_type"] else "Uncategorized"
            c.execute("INSERT INTO transactions (date, transaction_type, amount, recipient, fee, body) VALUES (?, ?, ?, ?, ?, ?)",
                      (row.date, transaction_type, row.amount, row.recipient, row.fee, row.body))

app = Flask(__name__)
DB = "momo_transactions.db"

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/summary")
def summary():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("""
        SELECT transaction_type, COUNT(*) as count, COALESCE(SUM(amount), 0) as total
        FROM transactions
        GROUP BY transaction_type
    """, conn)
    conn.close()
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/transactions")
def transactions():
    tx_type = request.args.get("type")
    print(f"DEBUG: Received filter request for type: '{tx_type}'")

    try:
        conn = sqlite3.connect(DB)

        if tx_type:
            # First, let's see what exact transaction types we have in the database
            debug_df = pd.read_sql_query("SELECT DISTINCT transaction_type FROM transactions", conn)
            print("DEBUG: Available transaction types in database:")
            for _, row in debug_df.iterrows():
                print(f"  - '{row['transaction_type']}'")

            # Try exact match first
            query = "SELECT * FROM transactions WHERE transaction_type = ?"
            df = pd.read_sql_query(query, conn, params=(tx_type,))
            print(f"DEBUG: Exact match found {len(df)} rows")

            # If no exact match, try case-insensitive
            if len(df) == 0:
                query = "SELECT * FROM transactions WHERE LOWER(transaction_type) = LOWER(?)"
                df = pd.read_sql_query(query, conn, params=(tx_type,))
                print(f"DEBUG: Case-insensitive match found {len(df)} rows")

            # If still no match, try partial match
            if len(df) == 0:
                query = "SELECT * FROM transactions WHERE transaction_type LIKE ?"
                df = pd.read_sql_query(query, conn, params=(f"%{tx_type}%",))
                print(f"DEBUG: Partial match found {len(df)} rows")

        else:
            df = pd.read_sql_query("SELECT * FROM transactions", conn)
            print(f"DEBUG: No filter, returning all {len(df)} rows")

        conn.close()

        # CRITICAL FIX: Handle NaN values before converting to JSON
        df = df.fillna('')  # Replace NaN/None values with empty strings
        # Or alternatively, you could use:
        # df = df.where(pd.notnull(df), None)  # Replace NaN with None, then handle in to_dict

        result = df.to_dict(orient="records")

        # Additional safety: Clean up any remaining NaN values
        for record in result:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None if key in ['amount', 'fee'] else ''

        print(f"DEBUG: Returning {len(result)} transactions")
        return jsonify(result)

    except Exception as e:
        print(f"DEBUG: Error in transactions endpoint: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return jsonify({"error": str(e)}), 500

# Debug endpoints
@app.route("/api/debug/types")
def debug_types():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT DISTINCT transaction_type FROM transactions ORDER BY transaction_type", conn)
    conn.close()
    types_info = []
    for _, row in df.iterrows():
        types_info.append({
            "type": row["transaction_type"],
            "length": len(row["transaction_type"]),
            "repr": repr(row["transaction_type"])  # Shows hidden characters
        })
    return jsonify(types_info)

@app.route("/api/debug/payments")
def debug_payments():
    conn = sqlite3.connect(DB)
    # Get all transactions that might be payments to code holders
    df = pd.read_sql_query("""
        SELECT transaction_type, COUNT(*) as count, body
        FROM transactions
        WHERE transaction_type LIKE '%payment%' OR transaction_type LIKE '%Payment%' OR transaction_type LIKE '%Code%'
        GROUP BY transaction_type
        LIMIT 10
    """, conn)
    conn.close()
    return jsonify(df.to_dict(orient="records"))

if __name__ == "__main__":
    if not os.path.exists(DB):
        df = parse_xml_to_df("modified_sms_v2.xml")
        init_db(df)
    app.run(debug=True)
