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
                                else "Payments to Code Holders")
            m = re.search(r"payment of (\d[\d,]*) RWF to (.+?) (\\d+)?", body)
            if m: amount, recipient = int(m[1].replace(",", "")), m[2]
            m_fee = re.search(r"Fee (?:was|paid):? (\d[\d,]*) RWF", body)
            if m_fee: fee = int(m_fee[1].replace(",", ""))
        elif "transferred to" in body.lower():
            transaction_type = "Transfers to Mobile Numbers"
            m = re.search(r"(\d[\d,]*) RWF transferred to (.+?) \(", body)
            if m: amount, recipient = int(m[1].replace(",", "")), m[2]
            m_fee = re.search(r"Fee was:? (\d[\d,]*) RWF", body)
            if m_fee: fee = int(m_fee[1].replace(",", ""))
        elif "withdrawn" in body.lower():
            transaction_type = "Withdrawals from Agents"
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
            transaction_type = "Internet and Voice Bundle Purchases"
            m = re.search(r"bundle of .+ for (\d[\d,]*) RWF", body)
            if m: amount = int(m[1].replace(",", ""))
        elif "one-time password" in body.lower():
            transaction_type = "OTP Notification"
        elif "by direct payment" in body.lower():
            transaction_type = "Transactions Initiated by Third Parties"
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
        c.execute('''CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, transaction_type TEXT, amount INTEGER,
            recipient TEXT, fee INTEGER, body TEXT
        )''')
        for _, r in df.iterrows():
            c.execute("INSERT INTO transactions (date, transaction_type, amount, recipient, fee, body) VALUES (?, ?, ?, ?, ?, ?)",
                      (r.date, r.transaction_type, r.amount, r.recipient, r.fee, r.body))

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
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/transactions")
def transactions():
    tx_type = request.args.get("type")
    q = "SELECT * FROM transactions"
    if tx_type: q += f" WHERE transaction_type = '{tx_type}'"
    df = pd.read_sql_query(q, sqlite3.connect(DB))
    return jsonify(df.to_dict(orient="records"))

if __name__ == "__main__":
    if not os.path.exists(DB):
        df = parse_xml_to_df("modified_sms_v2.xml")
        init_db(df)
    app.run(debug=True)
