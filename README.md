# MoMo Data Analysis Dashboard

An interactive fullstack web dashboard that analyzes and visualizes mobile money (MoMo) SMS transaction data. Built using **Flask**, **SQLite**, **Chart.js**, and custom HTML/CSS.

---

## Project Structure

```
├── app.py                    
├── modified_sms_v2.xml       
├── momo_transactions.db      
├── requirements.txt          
├── templates/
│   └── index.html            
├── README.md                 
├── AUTHORS                   
├── report.pdf                
```

---

## Features

* Dynamic summary chart of transactions by type
* Filterable list of transaction details
* Auto-cleans and categorizes raw MoMo SMS
* Saves structured data to SQLite
* Frontend styled with MoMo branding and Chart.js visualizations

---

## How to Run

### 1. Clone the Repository

```bash
git clone https://github.com/wamalwasydney/momo-data-analysis.git
cd momo-data-analysis
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Add XML Data File

Ensure `modified_sms_v2.xml` is placed in the root of the project.

### 4. Run the Flask App

```bash
python app.py
```

### 5. View the Dashboard

Access in your browser:

```
http://localhost:5000   (or sandbox port e.g. http://<sandbox-host>:35030)
```

---

## Architecture

* **Backend**: Flask for routing and data processing
* **Database**: SQLite, auto-populated from parsed XML
* **Frontend**: HTML/CSS + Chart.js
* **Visualization**: Transaction volume per category, filterable table view

---

## Video Walkthrough

🎥 [Watch Demo (5 min)](https://youtu.be/YOUR_VIDEO_LINK)

> Covers system overview, architecture, database, and UI demo

---

## Documentation

See `report.pdf` for a detailed write-up of:

* Design approach
* Implementation steps
* Challenges and how they were solved
* Screenshots of the UI

---

## AUTHORS

See the `AUTHORS` file for contributor details.
